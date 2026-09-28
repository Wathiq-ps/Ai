"""A TestClient that signs POST /v1/jobs the way Laravel's SendAiJob does, so
tests about what a job does aren't also tests about signing (those use a plain
TestClient; see test_job_endpoint.py's signature tests)."""

import json

from fastapi.testclient import TestClient

from app.config import settings
from app.security import sign


class SignedClient(TestClient):
    def post(self, url, *, json=None, headers=None, **kwargs):
        if url != "/v1/jobs" or json is None:
            return super().post(url, json=json, headers=headers, **kwargs)
        raw = _json.dumps(json).encode()
        signed = {"Content-Type": "application/json", "X-Wathiq-Signature": sign(raw, settings.ai_webhook_secret), **(headers or {})}
        return super().post(url, content=raw, headers=signed, **kwargs)


_json = json
