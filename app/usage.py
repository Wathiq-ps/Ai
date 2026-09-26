"""Per-job token and timing accounting — the callback's `usage` block
(openapi.yaml `Usage`) and the `stage=` log lines.

main._run_job puts one JobUsage in a ContextVar; the LLM provider adds each
chat call's tokens to it and the agents time their stages against it, so
neither a usage object nor the job id is threaded through every signature.
asyncio tasks copy the context, but the copy still points at the same
JobUsage, so analyze's concurrent samples all add to one total."""

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

logger = logging.getLogger("wathiq_ai")


@dataclass
class JobUsage:
    job_id: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    started: float = field(default_factory=time.perf_counter)

    def as_dict(self) -> dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "latency_ms": int((time.perf_counter() - self.started) * 1000),
        }


current_usage: ContextVar[JobUsage | None] = ContextVar("current_usage", default=None)


def add_tokens(prompt_tokens: int, completion_tokens: int) -> None:
    """No-op outside a job (unit tests, eval scripts)."""
    usage = current_usage.get()
    if usage is not None:
        usage.prompt_tokens += prompt_tokens
        usage.completion_tokens += completion_tokens


@contextmanager
def stage(name: str, **tags) -> Iterator[None]:
    """Logs `job <id> stage=<name> [k=v ...] ms=<n>` when the block exits,
    raised or cancelled included — a timed-out job's stage lines are what
    say where its budget went."""
    start = time.perf_counter()
    try:
        yield
    finally:
        usage = current_usage.get()
        extra = "".join(f" {k}={v}" for k, v in tags.items())
        ms = int((time.perf_counter() - start) * 1000)
        logger.info("job %s stage=%s%s ms=%d", usage.job_id if usage else "-", name, extra, ms)
