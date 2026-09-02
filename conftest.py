"""
Shared test fixtures.

Environment is pinned BEFORE any app import:
- DATABASE_URL points at a dedicated test database (created on demand,
  schema applied from database/schemas/*.sql)
- DEFAULT_AI_PROVIDER=mock so the full Council runs offline and
  deterministically with zero API keys.
"""

import os
import pathlib

# --- Pin environment before app.* is imported anywhere -----------------------
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/meta_supreme_test",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["DEFAULT_AI_PROVIDER"] = "mock"
os.environ["ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "false"
os.environ["DEVON_APPROVAL_STORE"] = "postgres"
# Registration is closed by default behind DEVON_REGISTRATION_KEY. The suite
# opens it with a known key, and the `client` fixture sends that key on every
# request so the seven tests that register directly keep working unchanged.
TEST_REGISTRATION_KEY = "test-registration-key-not-for-production-0123456789"
os.environ["DEVON_REGISTRATION_KEY"] = TEST_REGISTRATION_KEY

import pytest  # noqa: E402

# `asyncpg` and `httpx` are imported inside the fixtures that need them, not
# here. A large part of this suite — the engine and the cadence arithmetic —
# is deliberately pure, and importing a database driver at collection time
# would make those tests unrunnable without Postgres installed. They are the
# tests most worth running early and in the most places.
#
#     pip install pytest pytest-asyncio
#     bash scripts/verify-offline.sh

# Walk up to the directory that actually holds `database/schemas`, rather than
# counting parents. This file was flattened here from a nested location where
# `parents[3]` was the repo root; at the root it indexes past the filesystem
# root and raises IndexError, so collection died before a single test ran.
def _find_repo_root(start: pathlib.Path) -> pathlib.Path:
    for candidate in (start, *start.parents):
        if (candidate / "database" / "schemas").is_dir():
            return candidate
    # No schemas anywhere: the offline suites do not need them, so fall back to
    # this file's directory rather than failing collection for every test.
    return start


_REPO_ROOT = _find_repo_root(pathlib.Path(__file__).resolve().parent)
_SCHEMA_DIR = _REPO_ROOT / "database" / "schemas"
_BASELINE_SCHEMA = _SCHEMA_DIR / "001_initial_schema.sql"

#: Applied on every session start, in order, after the baseline. Each is
#: written to be re-runnable (IF NOT EXISTS / DROP … IF EXISTS) so a test
#: database created before a schema change picks the change up instead of
#: failing with a missing column.
_INCREMENTAL_SCHEMAS = (
    "002_workflow_runs.sql",
    "003_schedule_dispatch.sql",
    "004_federated_knowledge_waist.sql",
    "005_agent_runtime_persistence.sql",
    "006_devon_approval_store.sql",
    "007_agent_task_execution_leases.sql",
    "008_agent_effect_receipts.sql",
    "009_agent_hermes_expansion.sql",
    "010_agent_subagent_links.sql",
    "011_passkeys.sql",
    "012_live_state_ledger.sql",
    "013_approval_consumption.sql",
    "014_artifact_body.sql",
    "015_devon_approval_owner.sql",
    "017_provider_usage.sql",
)

_DSN = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
_ADMIN_DSN = _DSN.rsplit("/", 1)[0] + "/postgres"
_TEST_DB_NAME = _DSN.rsplit("/", 1)[1]

# Tables wiped between tests (order respects FKs; agents and executors stay
# seeded, the latter by 012_live_state_ledger.sql).
_DATA_TABLES = (
    "provider_usage",
    "universal_receipts",
    "learning_candidates",
    "verifications",
    "errors",
    "systems",
    "artifacts",
    "approvals",
    "actions",
    "events",
    "intents",
    "passkey_challenges",
    "passkey_credentials",
    "devon_approvals",
    "agent_effect_receipts",
    "agent_effect_intents",
    "agent_subagent_links",
    "agent_schedules",
    "agent_skill_proposals",
    "agent_task_runs",
    "agent_task_checkpoints",
    "agent_tasks",
    "agent_runtime_memories",
    "agent_runtime_skills",
    "agent_runs",
    "messages",
    "conversations",
    "feedback",
    "decisions",
    "memories",
    "embeddings",
    "knowledge_items",
    "workflow_runs",
    "workflows",
    "audit_logs",
    "projects",
    "organization_members",
    "organizations",
    "users",
)


async def _ensure_test_database() -> None:
    import asyncpg

    admin = await asyncpg.connect(dsn=_ADMIN_DSN)
    try:
        exists = await admin.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", _TEST_DB_NAME
        )
        if not exists:
            await admin.execute(f'CREATE DATABASE "{_TEST_DB_NAME}"')
    finally:
        await admin.close()

    conn = await asyncpg.connect(dsn=_DSN)
    try:
        has_schema = await conn.fetchval(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'users'"
        )
        if not has_schema:
            await conn.execute(_BASELINE_SCHEMA.read_text())
        for name in _INCREMENTAL_SCHEMAS:
            await conn.execute((_SCHEMA_DIR / name).read_text())
    finally:
        await conn.close()


# Neither database fixture is `autouse`. They are pulled in by `client` and
# `db_session`, which every database-touching test already requests, so
# isolation is unchanged — but a test that needs no database now costs no
# database. That is what lets the engine suite run anywhere Python runs.
@pytest.fixture(scope="session")
async def _test_database():
    """Create the test database and apply the schema once per session."""
    await _ensure_test_database()
    yield


@pytest.fixture
async def _clean_tables(_test_database):
    """Isolate tests: wipe data tables after each test (agents stay seeded)."""
    import asyncpg

    yield
    conn = await asyncpg.connect(dsn=_DSN)
    try:
        await conn.execute(
            "TRUNCATE " + ", ".join(_DATA_TABLES) + " RESTART IDENTITY CASCADE"
        )
    finally:
        await conn.close()


@pytest.fixture
async def client(_clean_tables):
    """HTTP client bound to the FastAPI app (no network)."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"X-Devon-Registration-Key": TEST_REGISTRATION_KEY},
    ) as c:
        yield c


@pytest.fixture
async def db_session(_clean_tables):
    """
    A session for tests that exercise the service layer directly.

    Rolled back rather than committed: the dispatcher and sweep tests assert
    on in-session state, and `_clean_tables` truncates afterwards anyway.
    """
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def auth_headers(client):
    """Register + login a fresh user; returns Authorization headers."""
    email = "council-tester@example.com"
    password = "a-strong-password-123"
    register = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Council Tester"},
    )
    assert register.status_code == 201, register.text
    login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
