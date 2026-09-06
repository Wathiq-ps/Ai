import logging
import sys
import time
import uuid
from contextvars import ContextVar

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")


class TraceIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get()
        return True


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(TraceIdFilter())
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s trace=%(trace_id)s %(name)s: %(message)s"
        )
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


def new_trace_id() -> str:
    return uuid.uuid4().hex[:16]


def now_ms() -> int:
    return int(time.time() * 1000)
