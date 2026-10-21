"""Strict, default-closed grants for a separate metadata-only machine principal.

This principal cannot authenticate as a DEVON user. It is accepted only by the
creator-workspace GET routes. No user token, passkey, signing key or shared
DEVON_SERVICE_KEY is read, generated or reused here.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Mapping
from uuid import UUID

BRANDS = frozenset(("tsws", "tqo", "nco-forge", "editforge", "whatbroke", "acx"))
MAX_LIFETIME = timedelta(days=30)
ENV_NAME = "DEVON_CREATOR_READ_GRANT"
_FIELDS = frozenset(
    (
        "enabled",
        "grant_id",
        "scope",
        "key_sha256",
        "not_before",
        "expires_at",
        "owner_id",
        "owner_email",
        "projects",
    )
)


class GrantRefused(ValueError):
    """Generic refusal; never includes configuration or credential values."""


def _deny() -> None:
    raise GrantRefused("Creator Workspace read authorization unavailable or refused")


def _uuid(value: object) -> str:
    if not isinstance(value, str):
        _deny()
    try:
        parsed = UUID(value)
    except (ValueError, TypeError, AttributeError):
        _deny()
    if str(parsed) != value:
        _deny()
    return value


def _time(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        _deny()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _deny()
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _deny()
    try:
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        _deny()


def _unique(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            _deny()
        result[key] = value
    return result


@dataclass(frozen=True)
class CreatorReadGrant:
    grant_id: str
    scope: str
    owner_id: str | None
    owner_email: str | None = field(repr=False)
    projects: tuple[tuple[str, tuple[str, ...]], ...]
    expires_at: datetime

    def allows(self, brand: str, project_id: str) -> bool:
        return self.scope == "active" and project_id in dict(self.projects).get(brand, ())

    def project_map(self) -> Mapping[str, tuple[str, ...]]:
        return dict(self.projects)


def authenticate_grant(
    raw: str, authorization: str | None, *, now: datetime | None = None
) -> CreatorReadGrant:
    """Validate an operator-provisioned, bounded grant without any DB or network call."""
    if not isinstance(raw, str) or not 2 <= len(raw) <= 12000:
        _deny()
    try:
        cfg = json.loads(raw, object_pairs_hook=_unique)
    except (ValueError, TypeError, RecursionError):
        _deny()
    if not isinstance(cfg, dict) or set(cfg) != _FIELDS or cfg["enabled"] is not True:
        _deny()
    if not isinstance(authorization, str) or len(authorization) > 128:
        _deny()
    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "creatorread":
        _deny()
    token = parts[1]
    if re.fullmatch(r"cwread_[A-Za-z0-9_-]{43}", token) is None:
        _deny()
    digest = cfg["key_sha256"]
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        _deny()
    if not secrets.compare_digest(hashlib.sha256(token.encode("ascii")).hexdigest(), digest):
        _deny()
    start, end = _time(cfg["not_before"]), _time(cfg["expires_at"])
    instant = now if now is not None else datetime.now(timezone.utc)
    if (
        instant.tzinfo is None
        or not start <= instant < end
        or not timedelta(0) < end - start <= MAX_LIFETIME
    ):
        _deny()
    grant_id = _uuid(cfg["grant_id"])
    scope = cfg["scope"]
    projects = cfg["projects"]
    if scope not in ("inventory", "active") or not isinstance(projects, dict):
        _deny()
    if scope == "inventory":
        email = cfg["owner_email"]
        if (
            cfg["owner_id"] is not None
            or projects
            or not isinstance(email, str)
            or len(email) > 254
            or email != email.lower()
            or re.fullmatch(
                r"[a-z0-9.!#$%&\'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,63}",
                email,
            )
            is None
        ):
            _deny()
        return CreatorReadGrant(grant_id, scope, None, email, (), end)
    owner_id = _uuid(cfg["owner_id"])
    if cfg["owner_email"] is not None or not projects or not set(projects) <= BRANDS:
        _deny()
    seen: set[str] = set()
    parsed = []
    for brand, ids in sorted(projects.items()):
        if not isinstance(ids, list) or not 1 <= len(ids) <= 10:
            _deny()
        checked = tuple(_uuid(item) for item in ids)
        if len(set(checked)) != len(checked) or seen.intersection(checked):
            _deny()
        seen.update(checked)
        parsed.append((brand, checked))
    return CreatorReadGrant(grant_id, scope, owner_id, None, tuple(parsed), end)
