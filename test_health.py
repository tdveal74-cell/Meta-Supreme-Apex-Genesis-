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


def test_the_apps_api_twin_carries_the_same_readiness_route():
    """apps/api/app/api/v1/health.py is a hand kept copy that no import in
    the suite resolves to (PYTHONPATH puts the root copy first), so a critic
    on 2026-09-15 reverted the twin to the old unconditional ready and every
    test stayed green. This reads both files and compares the readiness
    function body itself, docstring aside, so the copy cannot drift silently."""
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parent

    def readiness_body(path):
        tree = ast.parse((root / path).read_text(encoding="utf-8"))
        fn = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "readiness_check"
        )
        fn.body = [
            node
            for node in fn.body
            if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant))
        ]
        return ast.dump(fn)

    root_body = readiness_body("app/api/v1/health.py")
    assert "SELECT 1" in root_body, "the root route no longer runs SELECT 1"
    assert readiness_body("apps/api/app/api/v1/health.py") == root_body
