"""Basic health endpoint tests."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Meta Supreme Apex Genesis"
    assert data["status"] == "operational"


def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


async def test_ready_answers_ready_only_after_the_database_answered(client):
    """The readiness route runs SELECT 1 and says which checks it ran."""
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["database"] == "ok"
    # Nothing probes the providers yet, and the route says so instead of
    # reporting a check that never ran.
    assert data["checks"]["ai_providers"] == "unchecked"


async def test_ready_answers_503_when_the_database_does_not(client, monkeypatch):
    """A dead database is not ready, whatever the process itself is doing."""
    from app.api.v1 import health as health_module

    class _DeadSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, *_args, **_kwargs):
            raise ConnectionRefusedError("no database")

    monkeypatch.setattr(health_module, "AsyncSessionLocal", lambda: _DeadSession())
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "not_ready"
    assert data["checks"]["database"] == "error: ConnectionRefusedError"
