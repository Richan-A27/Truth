import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.verification import VerificationResponse

# starting the app loads real ML models via the lifespan handler
pytestmark = pytest.mark.integration


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _fake_response(run_id: uuid.UUID) -> VerificationResponse:
    return VerificationResponse(
        run_id=run_id,
        trust_score=80,
        verdict_label="likely_true",
        explanation="Mocked explanation.",
        claims=[],
        created_at=datetime.now(timezone.utc),
    )


def test_verify_rejects_empty_content(client):
    resp = client.post("/verify", json={"content": ""})
    assert resp.status_code == 400


def test_verify_rejects_too_short_content(client):
    resp = client.post("/verify", json={"content": "short"})
    assert resp.status_code == 400


def test_verify_returns_response_shape(client, monkeypatch):
    run_id = uuid.uuid4()

    async def fake_run_verification(content, source_url, session):
        return _fake_response(run_id)

    monkeypatch.setattr("app.api.routes_verify.run_verification", fake_run_verification)

    resp = client.post("/verify", json={"content": "This is a long enough test claim to pass validation."})
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == str(run_id)
    assert body["trust_score"] == 80
    assert body["verdict_label"] == "likely_true"


def test_get_verify_returns_404_for_unknown_run(client):
    resp = client.get(f"/verify/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
