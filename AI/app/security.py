import hashlib
import hmac
import time

from fastapi import Header, HTTPException

from app.config import settings


def require_api_key(x_api_key: str = Header(default="")) -> None:
    if not settings.ai_service_api_key or not hmac.compare_digest(
        x_api_key, settings.ai_service_api_key
    ):
        raise HTTPException(status_code=401, detail="invalid API key")


def sign_callback(raw_body: bytes, secret: str, timestamp: int | None = None) -> str:
    """HMAC scheme per WATHIQ_AI_SPRINT_PLAN.md's Phase 0 section: t=<ts>,v1=<hex digest>."""
    ts = timestamp if timestamp is not None else int(time.time())
    signed_payload = f"{ts}.".encode() + raw_body
    digest = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"
