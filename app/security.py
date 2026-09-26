import hashlib
import hmac
import time


def sign_callback(raw_body: bytes, secret: str, timestamp: int | None = None) -> str:
    """HMAC scheme per WATHIQ_AI_SPRINT_PLAN.md's Phase 0 section: t=<ts>,v1=<hex digest>."""
    ts = timestamp if timestamp is not None else int(time.time())
    signed_payload = f"{ts}.".encode() + raw_body
    digest = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"
