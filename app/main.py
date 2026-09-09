import json
import logging
import time
import uuid

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, Request
from pydantic import BaseModel

from app.config import settings
from app.db import get_pool
from app.generate_contract import GenerationFailed, generate_contract
from app.logging_conf import configure_logging, new_trace_id, trace_id_var
from app.providers import get_embedding_provider, get_llm_provider
from app.security import require_api_key, sign_callback

configure_logging()
logger = logging.getLogger("wathiq_ai")

app = FastAPI(title="Wathiq AI Legal Engine")


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
    kind: str
    jurisdiction_id: uuid.UUID
    payload: dict


# ponytail: bump manually when the drafting prompt changes materially — no
# registry, this string is just what lands in provenance.prompt_version.
GENERATE_CONTRACT_PROMPT_VERSION = "generate_contract-v1"


@app.post("/v1/jobs", status_code=202, dependencies=[Depends(require_api_key)])
async def create_job(job: JobRequest, background_tasks: BackgroundTasks):
    logger.info("received job %s kind=%s", job.job_id, job.kind)
    if job.kind == "generate_contract":
        background_tasks.add_task(_run_generate_contract, job)
    else:
        # analyze_contract/answer_query/summarize: not built yet (Sprint 6+).
        # Laravel gets no callback for these today and the job stays
        # dispatched — known gap, not this endpoint's job to paper over.
        logger.warning("job %s kind=%s has no worker yet", job.job_id, job.kind)
    return {"job_id": str(job.job_id), "status": "running"}


async def _run_generate_contract(job: JobRequest) -> None:
    """Runs after the 202 response is sent (FastAPI BackgroundTasks — no
    separate queue process; ponytail: fine for one AI-service instance, swap
    for a real queue (e.g. Redis/RQ) if this ever needs to survive a process
    restart or run across multiple workers). Never raises: every failure path
    ends in a signed callback POST, or a logged drop if even that fails."""
    provider = "deepseek" if settings.deepseek_api_key else "fake"
    model_id = settings.chat_model if settings.deepseek_api_key else "fake"

    try:
        payload = job.payload
        missing = [k for k in ("contract_type", "parties", "property") if k not in payload]
        if missing:
            raise GenerationFailed(f"payload missing required field(s): {missing}")

        pool = await get_pool()
        result = await generate_contract(
            pool,
            get_llm_provider(),
            get_embedding_provider(),
            jurisdiction_id=job.jurisdiction_id,
            contract_type=payload["contract_type"],
            parties=payload["parties"],
            property=payload["property"],
            language=payload.get("language", "ar"),
        )
    except Exception as exc:
        if not isinstance(exc, GenerationFailed):
            logger.exception("job %s (generate_contract) failed unexpectedly", job.job_id)
        await _send_callback(
            job.job_id, "generate_contract", status="failed", error=str(exc),
            provider=provider, model_id=model_id, kb_version_id=None,
        )
        return

    await _send_callback(
        job.job_id,
        "generate_contract",
        status="succeeded",
        result={
            "body": result.body,
            "clauses": [{"clause_kind": c.clause_kind, "content": c.content} for c in result.clauses],
            "citations": [
                {
                    "source_id": str(c.source_id),
                    "article_ref": c.article_ref,
                    "chunk_id": str(c.chunk_id),
                    "excerpt": c.excerpt,
                }
                for c in result.citations
            ],
        },
        provider=provider,
        model_id=model_id,
        kb_version_id=str(result.kb_version_id),
    )


async def _send_callback(
    job_id: uuid.UUID,
    kind: str,
    *,
    status: str,
    provider: str,
    model_id: str,
    kb_version_id: str | None,
    result: dict | None = None,
    error: str | None = None,
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
            "provenance": {
                "provider": provider,
                "model_id": model_id,
                "prompt_version": GENERATE_CONTRACT_PROMPT_VERSION,
                "kb_version_id": kb_version_id,
            },
        }
    ).encode()
    signature = sign_callback(raw_body, settings.ai_webhook_secret)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                settings.laravel_callback_url,
                content=raw_body,
                headers={"Content-Type": "application/json", "X-Wathiq-Signature": signature},
            )
            response.raise_for_status()
    except httpx.HTTPError:
        # ponytail: no retry/redelivery here — Laravel's ops.webhook_deliveries
        # dedupes on its side but there's nothing on ours to resend a dropped
        # callback yet. Fine for MVP; add a retry queue if this proves flaky.
        logger.exception("callback delivery failed for job %s", job_id)
