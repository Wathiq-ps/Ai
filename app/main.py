import asyncio
import json
import logging
import time
import uuid
from typing import Literal

import httpx
from fastapi import BackgroundTasks, FastAPI, Request
from pydantic import BaseModel

from app.analyze_contract import RISK_RUBRIC_VERSION, AnalysisFailed, analyze_contract
from app.config import settings
from app.db import get_pool
from app.errors import JobFailed
from app.generate_contract import (
    DRAFTABLE_CONTRACT_TYPES,
    GenerationFailed,
    generate_contract,
)
from app.logging_conf import configure_logging, new_trace_id, trace_id_var
from app.providers import get_embedding_provider, get_llm_provider
from app.reindex import reindex
from app.security import sign_callback
from app.usage import JobUsage, current_usage

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


class JobRequest(BaseModel):
    job_id: uuid.UUID
    # Only the kinds that have a worker. Anything else (answer_query/summarize
    # are Phase 3) is a 422, not a 202 that never calls back.
    kind: Literal["generate_contract", "analyze_contract", "reindex"]
    jurisdiction_id: uuid.UUID
    payload: dict


# ponytail: bump manually when a prompt changes materially — no registry,
# these strings are just what lands in provenance.prompt_version.
GENERATE_CONTRACT_PROMPT_VERSION = "generate_contract-v4"
ANALYZE_CONTRACT_PROMPT_VERSION = "analyze_contract-v1"
REINDEX_PROMPT_VERSION = "reindex-v1"  # no prompt; provenance wants a version string

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
        background_tasks.add_task(_RUNNERS[job.kind], job)
    return {"job_id": str(job.job_id), "status": "running"}


def _llm_provenance() -> tuple[str, str]:
    if settings.deepseek_api_key:
        return "deepseek", settings.chat_model
    return "fake", "fake"


async def _run_job(job: JobRequest, work, *, provider: str, model_id: str, prompt_version: str,
                   timeout: float | None) -> None:
    """Runs after the 202 response is sent (FastAPI BackgroundTasks — no
    separate queue process; ponytail: fine for one AI-service instance, swap
    for a real queue (e.g. Redis/RQ) if this ever needs to survive a process
    restart or run across multiple workers). `work` returns (result, kb_version_id).
    Never raises: every path ends in a signed callback POST, or a logged drop."""
    # Set before the work starts, so every task it spawns (analyze's samples)
    # adds its tokens to this same JobUsage — see app/usage.py.
    usage = JobUsage(job_id=str(job.job_id))
    token = current_usage.set(usage)

    async def send(status: str, **fields) -> None:
        report = usage.as_dict()
        logger.info(
            "job %s stage=total status=%s prompt_tokens=%d completion_tokens=%d ms=%d", job.job_id, status,
            report["prompt_tokens"], report["completion_tokens"], report["latency_ms"],
        )
        await _send_callback(
            job.job_id, job.kind, status=status, provider=provider, model_id=model_id,
            prompt_version=prompt_version, usage=report, **fields,
        )

    try:
        result, kb_version_id = await asyncio.wait_for(work(), timeout=timeout)
    except TimeoutError:
        # ponytail: a call the timeout cancels mid-flight never returns its
        # usage, so a timed_out job's tokens under-count what the provider
        # bills. Fine for "where does the budget go"; not for billing.
        await send("timed_out", error_code="timeout", error=f"exceeded {timeout}s budget (NFR-1.1)")
    except JobFailed as exc:
        await send("failed", error_code=exc.code, error=str(exc))
    except Exception as exc:
        logger.exception("job %s (%s) failed unexpectedly", job.job_id, job.kind)
        await send("failed", error_code="internal", error=str(exc))
    else:
        await send("succeeded", result=result, kb_version_id=str(kb_version_id))
    finally:
        current_usage.reset(token)


async def _run_generate_contract(job: JobRequest) -> None:
    async def work():
        payload = job.payload
        missing = [k for k in ("contract_type", "parties", "property") if k not in payload]
        if missing:
            raise GenerationFailed(f"payload missing required field(s): {missing}", "invalid_payload")
        if payload["contract_type"] not in DRAFTABLE_CONTRACT_TYPES:
            raise GenerationFailed(
                f"drafting a {payload['contract_type']!r} contract is not supported yet",
                "unsupported_contract_type",
            )
        result = await generate_contract(
            await get_pool(),
            get_llm_provider(),
            get_embedding_provider(),
            jurisdiction_id=job.jurisdiction_id,
            contract_type=payload["contract_type"],
            parties=payload["parties"],
            property=payload["property"],
            terms=payload.get("terms"),
            language=payload.get("language", "ar"),
        )
        return {
            "body": result.body,
            "clauses": [{"clause_kind": c.clause_kind, "content": c.content} for c in result.clauses],
            "citations": [_citation_json(c) for c in result.citations],
        }, result.kb_version_id

    provider, model_id = _llm_provenance()
    await _run_job(
        job, work, provider=provider, model_id=model_id,
        prompt_version=GENERATE_CONTRACT_PROMPT_VERSION, timeout=settings.job_timeout_seconds,
    )


async def _run_analyze_contract(job: JobRequest) -> None:
    async def work():
        payload = job.payload
        if not payload.get("content"):
            raise AnalysisFailed("payload missing required field: content", "invalid_payload")
        # Self-consistency voting is on by default now that a sample is cheap
        # (deepseek-chat, no reasoning tokens): 3 samples measured 36s end to
        # end against the 60s budget (NFR-1.1), and they buy both stability
        # (mean pairwise Jaccard 0.48->0.58) and a cleaner findings list. A
        # caller in a hurry can drop to 1. Clamped either way so a stray value
        # can't blow the timeout.
        samples = max(1, min(3, int(payload.get("samples", 3))))
        result = await analyze_contract(
            await get_pool(),
            get_llm_provider(),
            get_embedding_provider(),
            jurisdiction_id=job.jurisdiction_id,
            content=payload["content"],
            contract_type=payload.get("contract_type"),
            samples=samples,
        )
        return {
            # The checklist is emitted alongside findings, not instead of them:
            # every non-`present` verdict is already mirrored as a
            # missing_clause finding, so a consumer that only reads findings[]
            # is unaffected. Read coverage[] when you want the clauses that
            # were checked and found fine — findings[] cannot tell you that.
            "coverage": [
                {
                    "clause_kind": c.clause_kind,
                    "status": c.status,
                    "note": c.note,
                    "citations": [_citation_json(x) for x in c.citations],
                }
                for c in result.coverage
            ],
            "findings": [
                {
                    "kind": f.kind,
                    "clause_kind": f.clause_kind,
                    "severity": f.severity,
                    "title_ar": f.title_ar,
                    "title_en": f.title_en,
                    "description": f.description,
                    "suggested_text": f.suggested_text,
                    "citations": [_citation_json(c) for c in f.citations],
                    "confidence": f.confidence,
                }
                for f in result.findings
            ],
            "risk_score": result.risk_score,
            "risk_rubric_version": RISK_RUBRIC_VERSION,
            "summary_ar": result.summary_ar,
            "summary_en": result.summary_en,
            "confidence": result.confidence,
        }, result.kb_version_id

    provider, model_id = _llm_provenance()
    await _run_job(
        job, work, provider=provider, model_id=model_id,
        prompt_version=ANALYZE_CONTRACT_PROMPT_VERSION, timeout=settings.job_timeout_seconds,
    )


async def _run_reindex(job: JobRequest) -> None:
    """UC-080. Rebuilds this jurisdiction's kb_version from what is already in
    knowledge.documents; the payload only carries optional tag/notes — the AI
    service cannot create or verify sources (see app/reindex.py). Not bounded
    by the 60s budget: a full-corpus rebuild takes minutes."""
    embedding_model = settings.embedding_model if settings.openrouter_api_key else "fake"

    async def work():
        kb_version_id, documents = await reindex(
            await get_pool(),
            get_embedding_provider(),
            jurisdiction_id=job.jurisdiction_id,
            embedding_model=embedding_model,
            tag=job.payload.get("tag"),
            notes=job.payload.get("notes"),
        )
        return {"kb_version_id": str(kb_version_id), "documents": documents}, kb_version_id

    await _run_job(
        job, work, provider="openrouter" if settings.openrouter_api_key else "fake",
        model_id=embedding_model, prompt_version=REINDEX_PROMPT_VERSION, timeout=None,
    )


_RUNNERS = {
    "generate_contract": _run_generate_contract,
    "analyze_contract": _run_analyze_contract,
    "reindex": _run_reindex,
}


def _citation_json(c) -> dict:
    return {
        "source_id": str(c.source_id),
        "article_ref": c.article_ref,
        "chunk_id": str(c.chunk_id),
        "excerpt": c.excerpt,
    }


async def _send_callback(
    job_id: uuid.UUID,
    kind: str,
    *,
    status: str,
    provider: str,
    model_id: str,
    prompt_version: str,
    usage: dict,
    kb_version_id: str | None = None,
    result: dict | None = None,
    error: str | None = None,
    error_code: str | None = None,
) -> None:
    """POST the JobCallback shape (openapi.yaml) to Laravel, HMAC-signed per
    WATHIQ_AI_SPRINT_PLAN.md's Phase 0 scheme. Signs the exact bytes sent —
    `content=raw_body`, never `json=...`, so the signature can't drift from
    what Laravel actually receives on the wire."""
    raw_body = json.dumps(
        {
            "job_id": str(job_id),
            "kind": kind,
            "status": status,
            "result": result,
            "error": error,
            "error_code": error_code,
            "provenance": {
                "provider": provider,
                "model_id": model_id,
                # ponytail: the model id doubles as its version — DeepSeek's
                # `deepseek-chat` is a moving alias and we keep nothing finer.
                # Ceiling: two runs months apart can share a model_version
                # while the weights changed. Upgrade: carry the response's
                # system_fingerprint back through LLMProvider.chat.
                "model_version": model_id,
                "prompt_version": prompt_version,
                "kb_version_id": kb_version_id,
            },
            "usage": usage,
        }
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
