import uuid

from app import main
from app.main import app
from tests.signed_client import SignedClient

client = SignedClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_job_round_trips(monkeypatch):
    # The background callback has nowhere to go here; don't wait out its retries.
    monkeypatch.setattr(main, "CALLBACK_BACKOFF_SECONDS", (0, 0))
    monkeypatch.setattr(main.settings, "ai_webhook_secret", "test-secret")
    job_id = str(uuid.uuid4())
    response = client.post(
        "/v1/jobs",
        json={"job_id": job_id, "kind": "generate_contract", "jurisdiction_id": str(uuid.uuid4()), "payload": {}},
    )
    assert response.status_code == 202
    assert response.json() == {
        "job_id": job_id, "status": "running", "respond_within_seconds": main.respond_within_seconds(main.JOBS["generate_contract"]),
    }
