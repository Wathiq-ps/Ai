# Railway deploy (Sprint 4 item 8). uv's own image so the lockfile is honoured
# exactly; no venv activation needed — `uv run` resolves it.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app
COPY corpus ./corpus

# Railway injects $PORT. Single worker: the drafting/analysis jobs run as
# FastAPI BackgroundTasks in-process, so a second worker would just be a
# second, unshared job runner (see app/main.py's note on swapping in a queue).
ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}"]
