import asyncio
import json
import logging
import time
import uuid
from typing import Literal

import httpx
from fastapi import BackgroundTasks, FastAPI, Request
from pydantic import ValidationError

from app.config import settings
from app.db import get_pool
from app.errors import JobFailed
from app.jobs import JOBS, JobContext, JobKind, JobOutcome, JobRequest
from app.logging_conf import configure_logging, new_trace_id, trace_id_var
from app.providers import get_embedding_provider, get_llm_provider
from app.security import sign_callback
from app.usage import JobUsage, current_usage
from app.wire import ErrorCode, JobCallback, Provenance, Usage

configure_logging()
logger = logging.getLogger("wathiq_ai")

app = FastAPI(title="Wathiq AI Legal Engine")

if not settings.ai_webhook_secret:
    logger.warning("AI_WEBHOOK_SECRET is empty: Laravel will reject every callback this service sends")


@app.middleware("http")
async def trace_and_timing(request: Request, call_next):
    token = trace_id_var.set(new_trace_id())
    start = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.info("%s %s -> latency=%dms", request.method, request.url.path, latency_ms)
        trace_id_var.reset(token)
    return response


@app.get("/health")
async def health():
    return {"status": "ok"}


CALLBACK_ATTEMPTS = 3
CALLBACK_BACKOFF_SECONDS = (2, 5)  # between attempts 1->2 and 2->3

# Job ids already accepted by this process. Laravel retries its POST when it
# times out waiting for our 202, which can land after we'd already accepted —
# a second run would double the tokens and send two callbacks. ponytail:
# per-process memory, same ceiling as BackgroundTasks itself (a restart
# forgets both); capped so a long-lived process can't grow it forever.
_ACCEPTED_CAPACITY = 1024
_accepted_jobs: dict[uuid.UUID, None] = {}


# ponytail: no inbound auth. Laravel calls this over Railway's private network
# (ai.railway.internal); anything that can reach the port can enqueue jobs and
# spend LLM credit. Put an X-API-Key check back (git history: require_api_key
# in app/security.py) before a public domain or a second caller is relied on.
@app.post("/v1/jobs", status_code=202)
async def create_job(job: JobRequest, background_tasks: BackgroundTasks):
    logger.info("received job %s kind=%s", job.job_id, job.kind)
    if job.job_id in _accepted_jobs:
        logger.info("job %s already accepted, not running it again", job.job_id)
    else:
        if len(_accepted_jobs) >= _ACCEPTED_CAPACITY:
            _accepted_jobs.pop(next(iter(_accepted_jobs)))
        _accepted_jobs[job.job_id] = None
        background_tasks.add_task(_run_job, job, JOBS[job.kind])
    return {"job_id": str(job.job_id), "status": "running"}


async def build_job_context() -> JobContext:
    """The resources a job runs against — the connection pool and the provider
    adapters. Built fresh per job, so nothing is shared between two jobs."""
    return JobContext(
        pool=await get_pool(),
        llm=get_llm_provider(),
        embedder=get_embedding_provider(),
    )


async def _with_context(kind: JobKind, job: JobRequest, payload) -> JobOutcome:
    """Acquire, then run — one coroutine, so `wait_for`'s budget covers both."""
    return await kind.run(await build_job_context(), job, payload)


def _payload_errors(exc: ValidationError) -> str:
    """Which field, and why — the message Laravel logs. Never shown to a user."""
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc']) or 'payload'}: {error['msg']}"
        for error in exc.errors()
    )


async def _run_job(job: JobRequest, kind: JobKind) -> None:
    """Runs after the 202 response is sent (FastAPI BackgroundTasks — no
    separate queue process; ponytail: fine for one AI-service instance, swap
    for a real queue (e.g. Redis/RQ) if this ever needs to survive a process
    restart or run across multiple workers). `kind` carries everything else
    this needs: what a valid payload is, the prompt version provenance records,
    and the budget NFR-1.1 allows. Never raises: every path ends in a signed
    callback POST, or a logged drop."""
    provider, model_id = kind.provenance()
    # Set before the work starts, so every task it spawns (analyze's samples)
    # adds its tokens to this same JobUsage — see app/usage.py.
    usage = JobUsage(job_id=str(job.job_id))
    token = current_usage.set(usage)

    async def send(status: Literal["succeeded", "failed", "timed_out"], **fields) -> None:
        report = usage.as_dict()
        logger.info(
            "job %s stage=total status=%s prompt_tokens=%d completion_tokens=%d ms=%d", job.job_id, status,
            report["prompt_tokens"], report["completion_tokens"], report["latency_ms"],
        )
        await _send_callback(
            job.job_id, job.kind, status=status, provider=provider, model_id=model_id,
            prompt_version=kind.prompt_version, usage=report, **fields,
        )

    budget = kind.timeout()
    try:
        # Validated before anything is acquired, and before the budget starts:
        # a payload that cannot be served costs no connection and no provider
        # client. The context build itself is inside the timed coroutine, since
        # acquiring the pool and the clients is part of NFR-1.1's budget.
        payload = kind.accept(job.payload)
        outcome = await asyncio.wait_for(_with_context(kind, job, payload), timeout=budget)
    except ValidationError as exc:
        await send("failed", error_code=ErrorCode.INVALID_PAYLOAD, error=_payload_errors(exc))
    except TimeoutError:
        # ponytail: a call the timeout cancels mid-flight never returns its
        # usage, so a timed_out job's tokens under-count what the provider
        # bills. Fine for "where does the budget go"; not for billing.
        await send("timed_out", error_code=ErrorCode.TIMEOUT, error=f"exceeded {budget}s budget (NFR-1.1)")
    except JobFailed as exc:
        await send("failed", error_code=exc.code, error=str(exc))
    except Exception as exc:
        logger.exception("job %s (%s) failed unexpectedly", job.job_id, job.kind)
        await send("failed", error_code=ErrorCode.INTERNAL, error=str(exc))
    else:
        await send("succeeded", result=outcome.result, kb_version_id=outcome.kb_version_id)
    finally:
        current_usage.reset(token)


async def _send_callback(
    job_id: uuid.UUID,
    kind: str,
    *,
    status: Literal["succeeded", "failed", "timed_out"],
    provider: str,
    model_id: str,
    prompt_version: str,
    usage: dict,
    kb_version_id: uuid.UUID | None = None,
    result: dict | None = None,
    error: str | None = None,
    error_code: ErrorCode | None = None,
) -> None:
    """POST the JobCallback shape (openapi.yaml) to Laravel, HMAC-signed per
    WATHIQ_AI_SPRINT_PLAN.md's Phase 0 scheme.

    The body is `app.wire.JobCallback` serialised, not a dict written here by
    hand: the field set and the enum values are the ones the wire-contract test
    holds openapi.yaml to. It signs the exact bytes sent — `content=raw_body`,
    never `json=...`, so the signature can't drift from what Laravel actually
    receives on the wire."""
    raw_body = json.dumps(
        JobCallback(
            job_id=job_id,
            kind=kind,
            status=status,
            result=result,
            error=error,
            error_code=error_code,
            provenance=Provenance(
                provider=provider,
                model_id=model_id,
                # ponytail: the model id doubles as its version — DeepSeek's
                # `deepseek-flash` is a moving name (V4 then V4.1 behind it)
                # and we keep nothing finer.
                # Ceiling: two runs months apart can share a model_version
                # while the weights changed. Upgrade: carry the response's
                # system_fingerprint back through LLMProvider.chat.
                model_version=model_id,
                prompt_version=prompt_version,
                kb_version_id=kb_version_id,
            ),
            usage=Usage(**usage),
        ).model_dump(mode="json")
    ).encode()

    for attempt in range(CALLBACK_ATTEMPTS):
        # Re-signed on every attempt: Laravel rejects a signature more than 5
        # minutes old, and its replay index would refuse a reused one.
        headers = {
            "Content-Type": "application/json",
            "X-Wathiq-Signature": sign_callback(raw_body, settings.ai_webhook_secret),
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(settings.laravel_callback_url, content=raw_body, headers=headers)
        except httpx.HTTPError as exc:
            logger.warning("callback for job %s: attempt %d failed (%s)", job_id, attempt + 1, exc)
        else:
            if response.status_code < 400:
                return
            if response.status_code < 500:
                # Laravel read it and said no (bad signature, unknown job) —
                # resending the same body cannot change that answer.
                logger.error("callback for job %s rejected with %d", job_id, response.status_code)
                return
            logger.warning("callback for job %s: attempt %d got %d", job_id, attempt + 1, response.status_code)
        if attempt < CALLBACK_ATTEMPTS - 1:
            await asyncio.sleep(CALLBACK_BACKOFF_SECONDS[attempt])

    # Laravel's own timeout check moves the job to timed_out; nothing more we can do here.
    logger.error("callback delivery failed for job %s after %d attempts", job_id, CALLBACK_ATTEMPTS)
