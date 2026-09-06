import uuid

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_job_requires_api_key():
    response = client.post(
        "/v1/jobs",
        json={"job_id": str(uuid.uuid4()), "kind": "generate_contract", "jurisdiction_id": str(uuid.uuid4()), "payload": {}},
    )
    assert response.status_code == 401


def test_job_round_trips_with_api_key():
    settings.ai_service_api_key = "test-key"
    job_id = str(uuid.uuid4())
    response = client.post(
        "/v1/jobs",
        headers={"X-API-Key": "test-key"},
        json={"job_id": job_id, "kind": "generate_contract", "jurisdiction_id": str(uuid.uuid4()), "payload": {}},
    )
    assert response.status_code == 202
    assert response.json() == {"job_id": job_id, "status": "running"}
