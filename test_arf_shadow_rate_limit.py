"""Real authentication and PostgreSQL regression for ARF request budgets."""

import pytest


@pytest.mark.asyncio
async def test_sixth_immediate_shadow_request_is_throttled(client, auth_headers, monkeypatch):
    """Removing the route's budget guard must make this fail with 404, not 429."""
    monkeypatch.setenv("ARF_SHADOW_READ_ENABLED", "true")
    for _ in range(5):
        response = await client.get(
            "/api/v1/agent-tasks/not-an-owned-task/reliability-shadow", headers=auth_headers
        )
        assert response.status_code == 404, response.text
    response = await client.get(
        "/api/v1/agent-tasks/a-different-task/reliability-shadow", headers=auth_headers
    )
    assert response.status_code == 429, response.text
    assert 1 <= int(response.headers["Retry-After"]) <= 2


async def _owner(client, headers):
    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    return response.json()["id"]


async def _second_account(client):
    email, password = "arf-second@example.com", "isolated-test-password-123"
    response = await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return response.json()["id"], {"Authorization": "Bearer " + login.json()["access_token"]}


@pytest.mark.asyncio
async def test_disabled_or_unauthenticated_requests_do_not_create_budget_rows(client, auth_headers, monkeypatch):
    from sqlalchemy import text

    from app.db.session import AsyncSessionLocal

    monkeypatch.delenv("ARF_SHADOW_READ_ENABLED", raising=False)
    path = "/api/v1/agent-tasks/no-task/reliability-shadow"
    assert (await client.get(path, headers=auth_headers)).status_code == 404
    monkeypatch.setenv("ARF_SHADOW_READ_ENABLED", "true")
    assert (await client.get(path)).status_code == 401
    assert (await client.get(path, headers={"Authorization": "Bearer invalid"})).status_code == 401
    async with AsyncSessionLocal() as db:
        assert (await db.execute(text("SELECT count(*) FROM arf_shadow_rate_limits"))).scalar_one() == 0


@pytest.mark.asyncio
async def test_two_accounts_have_independent_budgets(client, auth_headers, monkeypatch):
    monkeypatch.setenv("ARF_SHADOW_READ_ENABLED", "true")
    _, second_headers = await _second_account(client)
    path = "/api/v1/agent-tasks/no-task/reliability-shadow"
    for headers in (auth_headers, second_headers):
        for _ in range(5):
            assert (await client.get(path, headers=headers)).status_code == 404
        assert (await client.get(path, headers=headers)).status_code == 429


@pytest.mark.asyncio
async def test_new_login_and_forged_owner_ip_or_task_do_not_reset_budget(client, auth_headers, monkeypatch):
    monkeypatch.setenv("ARF_SHADOW_READ_ENABLED", "true")
    other, _ = await _second_account(client)
    path = "/api/v1/agent-tasks/no-task/reliability-shadow"
    for _ in range(5):
        assert (await client.get(path, headers=auth_headers)).status_code == 404
    login = await client.post("/api/v1/auth/login", json={
        "email": "council-tester@example.com", "password": "a-strong-password-123",
    })
    assert login.status_code == 200
    response = await client.get(
        "/api/v1/agent-tasks/different-task/reliability-shadow?owner_id=" + other,
        headers={"Authorization": "Bearer " + login.json()["access_token"],
                 "X-Forwarded-For": "203.0.113.55", "X-Owner-Id": other},
    )
    assert response.status_code == 429
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.asyncio
async def test_throttle_precedes_task_and_evidence_queries(client, auth_headers, monkeypatch):
    from sqlalchemy import event

    from app.db.session import engine

    monkeypatch.setenv("ARF_SHADOW_READ_ENABLED", "true")
    path = "/api/v1/agent-tasks/no-task/reliability-shadow"
    for _ in range(5):
        assert (await client.get(path, headers=auth_headers)).status_code == 404
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())

    event.listen(engine.sync_engine, "before_cursor_execute", capture)
    try:
        response = await client.get(path, headers=auth_headers)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture)
    assert response.status_code == 429
    assert not any("from agent_tasks" in s or "from agent_verifications" in s
                   or "from agent_tool_results" in s for s in statements)


@pytest.mark.asyncio
async def test_normal_devon_reads_are_not_throttled_by_arf_budget(client, auth_headers, monkeypatch):
    monkeypatch.setenv("ARF_SHADOW_READ_ENABLED", "true")
    path = "/api/v1/agent-tasks/no-task/reliability-shadow"
    for _ in range(5):
        await client.get(path, headers=auth_headers)
    assert (await client.get(path, headers=auth_headers)).status_code == 429
    for _ in range(8):
        assert (await client.get("/api/v1/agent-tasks", headers=auth_headers)).status_code == 200


@pytest.mark.asyncio
async def test_concurrent_connections_cannot_claim_the_same_remaining_allowance(client, auth_headers):
    import asyncio
    import math
    import time

    from app.services.arf_shadow_rate_limit import ShadowRateLimitExceeded, consume_shadow_budget

    owner = await _owner(client, auth_headers)
    ready = asyncio.Event()

    async def attempt():
        await ready.wait()
        try:
            await consume_shadow_budget(owner)
            return "admitted"
        except ShadowRateLimitExceeded:
            return "limited"

    tasks = [asyncio.create_task(attempt()) for _ in range(16)]
    start = time.monotonic()
    ready.set()
    outcomes = await asyncio.gather(*tasks)
    elapsed = time.monotonic() - start
    admitted = outcomes.count("admitted")
    assert admitted >= 5
    assert admitted <= 5 + math.floor(elapsed / 2), (outcomes, elapsed)
    assert outcomes.count("limited") > 0, (outcomes, elapsed)


@pytest.mark.asyncio
async def test_budget_schedules_exact_two_second_refill_and_caps_idle_burst(client, auth_headers):
    from sqlalchemy import text

    from app.db.session import AsyncSessionLocal
    from app.services.arf_shadow_rate_limit import ShadowRateLimitExceeded, consume_shadow_budget

    owner = await _owner(client, auth_headers)
    await consume_shadow_budget(owner)
    async with AsyncSessionLocal() as db:
        first = (await db.execute(text("SELECT next_slot_at FROM arf_shadow_rate_limits WHERE owner_id = :o"), {"o": owner})).scalar_one()
    for _ in range(4):
        await consume_shadow_budget(owner)
    async with AsyncSessionLocal() as db:
        fifth = (await db.execute(text("SELECT next_slot_at FROM arf_shadow_rate_limits WHERE owner_id = :o"), {"o": owner})).scalar_one()
    assert (fifth - first).total_seconds() == 8
    with pytest.raises(ShadowRateLimitExceeded):
        await consume_shadow_budget(owner)
    async with AsyncSessionLocal.begin() as db:
        await db.execute(text("UPDATE arf_shadow_rate_limits SET next_slot_at = clock_timestamp() - INTERVAL '1 day' WHERE owner_id = :o"), {"o": owner})
    for _ in range(5):
        await consume_shadow_budget(owner)
    with pytest.raises(ShadowRateLimitExceeded):
        await consume_shadow_budget(owner)


@pytest.mark.asyncio
async def test_blocked_requests_do_not_extend_the_refill_deadline(client, auth_headers):
    from sqlalchemy import text

    from app.db.session import AsyncSessionLocal
    from app.services.arf_shadow_rate_limit import ShadowRateLimitExceeded, consume_shadow_budget

    owner = await _owner(client, auth_headers)
    async with AsyncSessionLocal.begin() as db:
        deadline = (await db.execute(text("INSERT INTO arf_shadow_rate_limits VALUES (:o, clock_timestamp() + INTERVAL '1 minute') RETURNING next_slot_at"), {"o": owner})).scalar_one()
    for _ in range(5):
        with pytest.raises(ShadowRateLimitExceeded) as failure:
            await consume_shadow_budget(owner)
        assert 1 <= failure.value.retry_after <= 52
    async with AsyncSessionLocal() as db:
        stored = (await db.execute(text("SELECT next_slot_at FROM arf_shadow_rate_limits WHERE owner_id = :o"), {"o": owner})).scalar_one()
    assert stored == deadline


@pytest.mark.asyncio
async def test_new_python_worker_does_not_reset_durable_budget(client, auth_headers):
    import asyncio
    import os
    import sys

    from sqlalchemy import text

    from app.db.session import AsyncSessionLocal

    owner = await _owner(client, auth_headers)
    async with AsyncSessionLocal.begin() as db:
        await db.execute(text("INSERT INTO arf_shadow_rate_limits VALUES (:o, clock_timestamp() + INTERVAL '1 minute')"), {"o": owner})
    code = """
import asyncio, sys
from app.db.session import engine
from app.services.arf_shadow_rate_limit import consume_shadow_budget, ShadowRateLimitExceeded
async def main():
    try:
        await consume_shadow_budget(sys.argv[1])
    except ShadowRateLimitExceeded:
        print('DURABLE_BUDGET_PRESERVED')
    else:
        raise AssertionError('worker restart reset account budget')
    finally:
        await engine.dispose()
asyncio.run(main())
"""
    env = dict(os.environ)
    env["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    for _ in range(2):
        proc = await asyncio.create_subprocess_exec(sys.executable, "-c", code, owner,
            env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
        assert proc.returncode == 0, stderr.decode()[-1000:]
        assert stdout.strip() == b"DURABLE_BUDGET_PRESERVED"


@pytest.mark.asyncio
async def test_missing_accounting_table_refuses_without_leaking_database_details(client, auth_headers, monkeypatch):
    from sqlalchemy import text

    from app.db.session import AsyncSessionLocal

    monkeypatch.setenv("ARF_SHADOW_READ_ENABLED", "true")
    async with AsyncSessionLocal.begin() as db:
        await db.execute(text("ALTER TABLE arf_shadow_rate_limits RENAME TO arf_shadow_rate_limits_test_unavailable"))
    try:
        response = await client.get("/api/v1/agent-tasks/no-task/reliability-shadow", headers=auth_headers)
        assert response.status_code == 503
        assert response.json()["detail"] == "ARF diagnostic protection unavailable"
        assert "arf_shadow_rate_limits" not in response.text
        assert "SELECT" not in response.text
        assert response.headers["Retry-After"] == "2"
    finally:
        async with AsyncSessionLocal.begin() as db:
            await db.execute(text("ALTER TABLE arf_shadow_rate_limits_test_unavailable RENAME TO arf_shadow_rate_limits"))


@pytest.mark.asyncio
async def test_busy_accounting_table_times_out_closed_then_recovers(client, auth_headers, monkeypatch):
    from sqlalchemy import text

    from app.db.session import AsyncSessionLocal

    monkeypatch.setenv("ARF_SHADOW_READ_ENABLED", "true")
    path = "/api/v1/agent-tasks/no-task/reliability-shadow"
    async with AsyncSessionLocal() as db:
        await db.execute(text("LOCK TABLE arf_shadow_rate_limits IN ACCESS EXCLUSIVE MODE"))
        response = await client.get(path, headers=auth_headers)
        assert response.status_code == 503
        await db.rollback()
    assert (await client.get(path, headers=auth_headers)).status_code == 404


@pytest.mark.asyncio
async def test_account_deletion_removes_only_its_security_counter(client, auth_headers):
    from sqlalchemy import text

    from app.db.session import AsyncSessionLocal
    from app.services.arf_shadow_rate_limit import consume_shadow_budget

    first = await _owner(client, auth_headers)
    second, _ = await _second_account(client)
    await consume_shadow_budget(first)
    await consume_shadow_budget(second)
    async with AsyncSessionLocal.begin() as db:
        await db.execute(text("DELETE FROM users WHERE id = :o"), {"o": first})
        owners = (await db.execute(text("SELECT owner_id::text FROM arf_shadow_rate_limits"))).scalars().all()
    assert owners == [second]


@pytest.mark.asyncio
async def test_invalid_internal_account_identifier_fails_closed():
    from app.services.arf_shadow_rate_limit import ShadowRateLimitUnavailable, consume_shadow_budget

    for owner in ("", "owner-provided-in-query", None):
        with pytest.raises(ShadowRateLimitUnavailable):
            await consume_shadow_budget(owner)
