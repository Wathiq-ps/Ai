import hashlib
import hmac
import re
import time

# How far a signature's timestamp may be from now, either way — Laravel's
# AiCallbackController uses the same 300s for the callbacks we send it.
TOLERANCE_SECONDS = 300

_HEADER = re.compile(r"t=(\d+),v1=([0-9a-f]{64})")


def sign(raw_body: bytes, secret: str, timestamp: int | None = None) -> str:
    """X-Wathiq-Signature: t=<unix>,v1=<hex HMAC-SHA256(secret, "<t>.<raw body>")>.

    One scheme, both directions: our callbacks to Laravel, and Laravel's job
    requests to us (verify below). ponytail: one shared secret for both — the
    two bodies can't stand in for each other (a callback has no `payload`, a
    job request no `status`, and each side refuses the other's shape); give
    each direction its own secret if that ever stops being true."""
    ts = timestamp if timestamp is not None else int(time.time())
    digest = hmac.new(secret.encode(), f"{ts}.".encode() + raw_body, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


def verify(header: str | None, raw_body: bytes, secret: str, now: int | None = None) -> bool:
    """True only for a signature by `secret` over exactly these bytes, made
    within TOLERANCE_SECONDS. An empty secret verifies nothing."""
    match = _HEADER.fullmatch(header or "")
    if not secret or match is None:
        return False
    ts = int(match.group(1))
    if abs((now if now is not None else int(time.time())) - ts) > TOLERANCE_SECONDS:
        return False
    return hmac.compare_digest(sign(raw_body, secret, ts), header)
