import uuid

from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_job_round_trips(monkeypatch):
    # The background callback has nowhere to go here; don't wait out its retries.
    monkeypatch.setattr(main, "CALLBACK_BACKOFF_SECONDS", (0, 0))
    job_id = str(uuid.uuid4())
    response = client.post(
        "/v1/jobs",
        json={"job_id": job_id, "kind": "generate_contract", "jurisdiction_id": str(uuid.uuid4()), "payload": {}},
    )
    assert response.status_code == 202
    assert response.json() == {
        "job_id": job_id, "status": "running", "respond_within_seconds": main.respond_within_seconds(main.JOBS["generate_contract"]),
    }
