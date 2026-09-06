import logging
import time
import uuid

from fastapi import Depends, FastAPI, Request
from pydantic import BaseModel

from app.logging_conf import configure_logging, new_trace_id, trace_id_var
from app.security import require_api_key

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


@app.post("/v1/jobs", status_code=202, dependencies=[Depends(require_api_key)])
async def create_job(job: JobRequest):
    # Phase 1C/1D wire the actual LangGraph agents in here. For now this just
    # proves the auth + request shape round-trips (1A acceptance: smoke job).
    logger.info("received job %s kind=%s", job.job_id, job.kind)
    return {"job_id": str(job.job_id), "status": "running"}
