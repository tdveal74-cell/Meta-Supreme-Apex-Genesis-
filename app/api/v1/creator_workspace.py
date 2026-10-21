"""Opt-in, GET-only metadata access for an explicitly delegated machine grant.

No personal JWT is accepted here. Ordinary user routes do not accept this
principal. Every database operation occurs in one read-only transaction.
"""

from __future__ import annotations

import os
from typing import Annotated, Literal
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.security.creator_read import (
    ENV_NAME,
    CreatorReadGrant,
    GrantRefused,
    authenticate_grant,
)

router = APIRouter(prefix="/creator-workspace", tags=["Creator Workspace"])
Brand = Literal["tsws", "tqo", "nco-forge", "editforge", "whatbroke", "acx"]
_NO_STORE = {"Cache-Control": "no-store"}


def _refuse(code: int, detail: str) -> None:
    raise HTTPException(status_code=code, detail=detail, headers=_NO_STORE)


def require_creator_grant(
    authorization: Annotated[str | None, Header()] = None,
) -> CreatorReadGrant:
    raw = os.getenv(ENV_NAME, "")
    if not raw:
        _refuse(503, "Creator Workspace read access is not enabled")
    try:
        return authenticate_grant(raw, authorization)
    except GrantRefused:
        _refuse(401, "Creator Workspace authorization refused")


Grant = Annotated[CreatorReadGrant, Depends(require_creator_grant)]
Db = Annotated[AsyncSession, Depends(get_db)]


async def _begin(db: AsyncSession) -> None:
    # This route has no CurrentUser dependency and expects an unused session.
    # Never roll back an unknown caller's transaction to make a guard pass.
    if db.in_transaction():
        _refuse(503, "Read-only transaction unavailable")
    await db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
    await db.execute(text("SET LOCAL statement_timeout = '3000ms'"))


async def _owner(db: AsyncSession, grant: CreatorReadGrant) -> str:
    if grant.scope == "inventory":
        query = "SELECT id FROM users WHERE lower(email) = :email AND is_active = true"
        params = {"email": grant.owner_email}
    else:
        query = "SELECT id FROM users WHERE id = CAST(:owner_id AS uuid) AND is_active = true"
        params = {"owner_id": grant.owner_id}
    result = await db.execute(text(query), params)
    rows = result.mappings().all()
    # Ambiguous case-insensitive emails cannot select an arbitrary account.
    if len(rows) != 1:
        _refuse(401, "Creator Workspace account unavailable")
    return str(rows[0]["id"])


def _source_uri(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 2000 or any(ord(c) < 32 for c in value):
        return None
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            return None
        # Query strings and fragments can contain bearer credentials.
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    except ValueError:
        return None


@router.get("/status")
async def delegated_status(grant: Grant, db: Db, response: Response):
    await _begin(db)
    owner = await _owner(db, grant)
    response.headers.update(_NO_STORE)
    return {
        "principal": "CREATOR_WORKSPACE_METADATA_READER",
        "grant_id": grant.grant_id,
        "owner_id": owner,
        "scope": grant.scope,
        "expires_at": grant.expires_at,
        "project_scopes": grant.project_map(),
        "knowledge_writes": False,
        "provider_calls": False,
        "publishing_authorized": False,
    }


@router.get("/projects")
async def inventory_projects(
    grant: Grant,
    db: Db,
    response: Response,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0, le=5000),
):
    if grant.scope != "inventory":
        _refuse(403, "Inventory grant required")
    await _begin(db)
    owner = await _owner(db, grant)
    result = await db.execute(
        text(
            "SELECT p.id, p.name, p.status FROM projects p JOIN users u ON u.id=p.owner_id "
            "WHERE p.owner_id=CAST(:owner_id AS uuid) AND u.is_active=true "
            "AND p.status != 'deleted' ORDER BY p.id LIMIT :limit OFFSET :offset"
        ),
        {"owner_id": owner, "limit": limit + 1, "offset": offset},
    )
    rows = result.mappings().all()
    response.headers.update(_NO_STORE)
    return {
        "scope": "inventory",
        "owner_id": owner,
        "items": [
            {"id": str(x["id"]), "name": str(x["name"])[:300], "status": str(x["status"])[:32]}
            for x in rows[:limit]
        ],
        "offset": offset,
        "has_more": len(rows) > limit,
        "source_contents_fetched": False,
        "publishing_authorized": False,
    }


@router.get("/{brand}/knowledge")
async def brand_knowledge_metadata(
    brand: Brand,
    project_id: UUID,
    grant: Grant,
    db: Db,
    response: Response,
    limit: int = Query(10, ge=1, le=20),
    offset: int = Query(0, ge=0, le=5000),
):
    if grant.scope != "active":
        _refuse(403, "Active project grant required")
    project = str(project_id)
    if not grant.allows(brand, project):
        _refuse(404, "Project unavailable")
    await _begin(db)
    owner = await _owner(db, grant)
    params = {"owner_id": owner, "project_id": project, "limit": limit + 1, "offset": offset}
    exists = await db.execute(
        text(
            "SELECT p.id FROM projects p JOIN users u ON u.id=p.owner_id "
            "WHERE p.id=CAST(:project_id AS uuid) AND p.owner_id=CAST(:owner_id AS uuid) "
            "AND p.status != 'deleted' AND u.is_active=true"
        ),
        {"owner_id": owner, "project_id": project},
    )
    if len(exists.mappings().all()) != 1:
        _refuse(404, "Project unavailable")
    result = await db.execute(
        text(
            "SELECT k.id, k.project_id, k.title, k.source_type, k.source_uri, "
            "k.status, k.created_at, k.updated_at FROM knowledge_items k "
            "JOIN projects p ON p.id=k.project_id JOIN users u ON u.id=p.owner_id "
            "WHERE k.owner_id=CAST(:owner_id AS uuid) AND p.owner_id=k.owner_id "
            "AND k.project_id=CAST(:project_id AS uuid) AND u.is_active=true "
            "AND p.status != 'deleted' AND k.status='ready' "
            "ORDER BY k.updated_at DESC, k.id LIMIT :limit OFFSET :offset"
        ),
        params,
    )
    rows = result.mappings().all()
    fields = ("created_at", "updated_at")
    items = [
        {
            "id": str(x["id"]),
            "project_id": str(x["project_id"]),
            "title": str(x["title"])[:300],
            "source_type": str(x["source_type"])[:32],
            "source_uri": _source_uri(x["source_uri"]),
            "status": "ready",
            **{key: x[key] for key in fields},
        }
        for x in rows[:limit]
    ]
    response.headers.update(_NO_STORE)
    return {
        "brand": brand,
        "project_id": project,
        "grant_id": grant.grant_id,
        "items": items,
        "offset": offset,
        "has_more": len(rows) > limit,
        "source_contents_fetched": False,
        "publishing_authorized": False,
        "provenance_state": "METADATA_ONLY_ORIGINAL_SOURCE_NOT_READ",
    }
