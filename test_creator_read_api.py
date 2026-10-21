"""Real PostgreSQL/API checks for the separate metadata-only machine principal."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

TOKEN = "cwread_" + "A" * 43
HEADERS = {"Authorization": "CreatorRead " + TOKEN}
PREFIX = "/api/v1/creator-workspace"


def _configure(monkeypatch, *, owner_id=None, projects=None, inventory=False):
    now = datetime.now(timezone.utc)
    cfg = {
        "enabled": True,
        "grant_id": str(uuid4()),
        "scope": "inventory" if inventory else "active",
        "key_sha256": hashlib.sha256(TOKEN.encode()).hexdigest(),
        "not_before": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(days=1)).isoformat(),
        "owner_id": None if inventory else owner_id,
        "owner_email": "council-tester@example.com" if inventory else None,
        "projects": {} if inventory else projects,
    }
    monkeypatch.setenv("DEVON_CREATOR_READ_GRANT", json.dumps(cfg))
    return cfg


async def _project(client, headers, name):
    response = await client.post("/api/v1/projects", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _source(client, headers, project_id, title="Source receipt"):
    response = await client.post(
        "/api/v1/knowledge",
        headers=headers,
        json={
            "title": title,
            "content": "PRIVATE_SOURCE_BODY_NOT_FOR_METADATA",
            "project_id": project_id,
            "source_type": "markdown",
            "source_uri": "https://example.com/source?private_token=not_for_response",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _identity(client, headers):
    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["id"]


async def _other(client):
    email, password = "creator-foreign@example.com", "Creator-foreign-test-2026!"
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Foreign fixture"},
    )
    assert response.status_code == 201, response.text
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


async def test_creator_read_is_closed_by_default(client, auth_headers, monkeypatch):
    monkeypatch.delenv("DEVON_CREATOR_READ_GRANT", raising=False)
    response = await client.get(PREFIX + "/status", headers=HEADERS)
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"


async def test_creator_read_inventory_is_owned_metadata_only(client, auth_headers, monkeypatch):
    own = await _project(client, auth_headers, "The Quiet Operator")
    foreign_headers = await _other(client)
    await _project(client, foreign_headers, "Foreign project title")
    _configure(monkeypatch, inventory=True)
    response = await client.get(PREFIX + "/projects", headers=HEADERS)
    assert response.status_code == 200, response.text
    assert [p["id"] for p in response.json()["items"]] == [own]
    assert "Foreign project title" not in response.text
    assert response.json()["publishing_authorized"] is False
    denied = await client.get(
        PREFIX + "/tqo/knowledge", params={"project_id": own}, headers=HEADERS
    )
    assert denied.status_code == 403


async def test_creator_read_real_positive_and_cross_owner_denial(client, auth_headers, monkeypatch):
    owner = await _identity(client, auth_headers)
    own = await _project(client, auth_headers, "The Quiet Operator")
    source = await _source(client, auth_headers, own)
    other = await _other(client)
    foreign = await _project(client, other, "Foreign")
    await _source(client, other, foreign, "FOREIGN_SOURCE")
    _configure(monkeypatch, owner_id=owner, projects={"tqo": [own]})
    ok = await client.get(PREFIX + "/tqo/knowledge", params={"project_id": own}, headers=HEADERS)
    assert ok.status_code == 200, ok.text
    assert [r["id"] for r in ok.json()["items"]] == [source]
    assert ok.json()["source_contents_fetched"] is False
    assert ok.json()["publishing_authorized"] is False
    assert ok.headers["cache-control"] == "no-store"
    assert "PRIVATE_SOURCE_BODY" not in ok.text
    assert "private_token" not in ok.text
    assert "FOREIGN_SOURCE" not in ok.text
    missing = await client.get(
        PREFIX + "/tqo/knowledge", params={"project_id": str(uuid4())}, headers=HEADERS
    )
    denied = await client.get(
        PREFIX + "/tqo/knowledge", params={"project_id": foreign}, headers=HEADERS
    )
    assert denied.status_code == missing.status_code == 404
    assert denied.json() == missing.json()
    # A misprovisioned allowlist still cannot defeat database ownership.
    _configure(monkeypatch, owner_id=owner, projects={"tqo": [foreign]})
    denied = await client.get(
        PREFIX + "/tqo/knowledge", params={"project_id": foreign}, headers=HEADERS
    )
    assert denied.status_code == 404


async def test_creator_read_separates_brands_of_same_owner(client, auth_headers, monkeypatch):
    owner = await _identity(client, auth_headers)
    tqo = await _project(client, auth_headers, "The Quiet Operator")
    acx = await _project(client, auth_headers, "Ascension Caudex")
    await _source(client, auth_headers, acx, "ACX_PRIVATE_MARKER")
    _configure(monkeypatch, owner_id=owner, projects={"tqo": [tqo], "acx": [acx]})
    denied = await client.get(
        PREFIX + "/tqo/knowledge", params={"project_id": acx}, headers=HEADERS
    )
    assert denied.status_code == 404
    assert "ACX_PRIVATE_MARKER" not in denied.text
    accepted = await client.get(
        PREFIX + "/acx/knowledge", params={"project_id": acx}, headers=HEADERS
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["items"][0]["title"] == "ACX_PRIVATE_MARKER"


async def test_creator_read_does_not_replace_user_auth(client, auth_headers, monkeypatch):
    owner = await _identity(client, auth_headers)
    project = await _project(client, auth_headers, "TQO")
    _configure(monkeypatch, owner_id=owner, projects={"tqo": [project]})
    for path in ("/api/v1/projects", "/api/v1/knowledge", "/api/v1/auth/me"):
        response = await client.get(path, headers=HEADERS)
        assert response.status_code == 401, (path, response.status_code)
    response = await client.get(PREFIX + "/status", headers=auth_headers)
    assert response.status_code == 401
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        response = await client.request(
            method, PREFIX + "/tqo/knowledge", params={"project_id": project}, headers=HEADERS
        )
        assert response.status_code == 405


async def test_creator_read_expiry_and_bounds(client, auth_headers, monkeypatch):
    owner = await _identity(client, auth_headers)
    project = await _project(client, auth_headers, "TQO")
    cfg = _configure(monkeypatch, owner_id=owner, projects={"tqo": [project]})
    for params in (
        {"project_id": project, "limit": 21},
        {"project_id": "bad"},
        {"project_id": project, "offset": -1},
    ):
        response = await client.get(PREFIX + "/tqo/knowledge", params=params, headers=HEADERS)
        assert response.status_code == 422
    cfg["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    monkeypatch.setenv("DEVON_CREATOR_READ_GRANT", json.dumps(cfg))
    response = await client.get(PREFIX + "/status", headers=HEADERS)
    assert response.status_code == 401


async def test_creator_read_helper_blocks_real_postgres_update(client, auth_headers):
    import pytest
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    from app.api.v1.creator_workspace import _begin
    from app.db.session import AsyncSessionLocal

    owner = await _identity(client, auth_headers)
    async with AsyncSessionLocal() as session:
        await _begin(session)
        result = await session.execute(text("SHOW transaction_read_only"))
        assert result.scalar_one() == "on"
        result = await session.execute(text("SHOW transaction_isolation"))
        assert result.scalar_one() == "repeatable read"
        with pytest.raises(SQLAlchemyError) as caught:
            await session.execute(
                text(
                    "UPDATE users SET full_name='SHOULD_NOT_COMMIT' WHERE id=CAST(:owner AS uuid)"
                ),
                {"owner": owner},
            )
        assert "read-only" in str(caught.value).lower()
        await session.rollback()
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    assert me.json()["full_name"] != "SHOULD_NOT_COMMIT"


async def test_creator_read_reused_transaction_refused_without_rollback():
    import pytest
    from fastapi import HTTPException
    from sqlalchemy import text

    from app.api.v1.creator_workspace import _begin
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT 1"))
        with pytest.raises(HTTPException) as caught:
            await _begin(session)
        assert caught.value.status_code == 503
        assert session.in_transaction()
        await session.rollback()


async def test_creator_read_inactive_owner_is_denied(client, auth_headers, monkeypatch, db_session):
    from sqlalchemy import text

    owner = await _identity(client, auth_headers)
    project = await _project(client, auth_headers, "The Quiet Operator")
    _configure(monkeypatch, owner_id=owner, projects={"tqo": [project]})
    await db_session.execute(
        text("UPDATE users SET is_active=false WHERE id=CAST(:owner AS uuid)"), {"owner": owner}
    )
    await db_session.commit()
    response = await client.get(
        PREFIX + "/tqo/knowledge", params={"project_id": project}, headers=HEADERS
    )
    assert response.status_code == 401


async def test_creator_read_deleted_project_is_denied(
    client, auth_headers, monkeypatch, db_session
):
    from sqlalchemy import text

    owner = await _identity(client, auth_headers)
    project = await _project(client, auth_headers, "The Quiet Operator")
    _configure(monkeypatch, owner_id=owner, projects={"tqo": [project]})
    await db_session.execute(
        text("UPDATE projects SET status='deleted' WHERE id=CAST(:project AS uuid)"),
        {"project": project},
    )
    await db_session.commit()
    response = await client.get(
        PREFIX + "/tqo/knowledge", params={"project_id": project}, headers=HEADERS
    )
    assert response.status_code == 404


async def test_creator_read_pagination_does_not_silently_claim_completeness(
    client, auth_headers, monkeypatch
):
    owner = await _identity(client, auth_headers)
    project = await _project(client, auth_headers, "The Quiet Operator")
    source_ids = {
        await _source(client, auth_headers, project, "Source " + str(i)) for i in range(3)
    }
    _configure(monkeypatch, owner_id=owner, projects={"tqo": [project]})
    first = await client.get(
        PREFIX + "/tqo/knowledge", params={"project_id": project, "limit": 2}, headers=HEADERS
    )
    second = await client.get(
        PREFIX + "/tqo/knowledge",
        params={"project_id": project, "limit": 2, "offset": 2},
        headers=HEADERS,
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["has_more"] is True
    assert second.json()["has_more"] is False
    combined = [x["id"] for x in first.json()["items"] + second.json()["items"]]
    assert len(combined) == len(set(combined)) == 3
    assert set(combined) == source_ids
