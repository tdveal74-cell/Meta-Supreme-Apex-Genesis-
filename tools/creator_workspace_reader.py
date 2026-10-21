"""Bounded metadata-only DEVON client. No user JWT, source body or write endpoint.

The CLI reads a dedicated service credential from a protected local file. It
never prints it, follows redirects, writes a knowledge cache, or calls a model.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

BASE = "https://api-production-5644.up.railway.app/api/v1/creator-workspace"
KEY_FILE = Path("/etc/creator-workspace/devon-read.key")
CONFIG_FILE = Path("/etc/creator-workspace/devon-read-client.json")
MAX_BYTES = 128 * 1024
BRANDS = frozenset(("tsws", "tqo", "nco-forge", "editforge", "whatbroke", "acx"))
CONFIG_FIELDS = frozenset(
    ("schema", "enabled", "api_base", "grant_id", "scope", "owner_id", "projects", "expires_at")
)
Transport = Callable[[str, dict[str, str]], tuple[int, str, bytes]]


class ReaderHold(ValueError):
    """No fallback to private source files, another identity, or a writable API."""


def _hold(message="Creator Workspace metadata read refused"):
    raise ReaderHold(message)


def _uuid(value):
    if not isinstance(value, str):
        _hold()
    try:
        canonical = str(UUID(value))
    except (ValueError, AttributeError, TypeError):
        _hold()
    if canonical != value:
        _hold()
    return value


def _instant(value):
    if not isinstance(value, str) or len(value) > 40:
        _hold()
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None or result.utcoffset() is None:
            _hold()
        return result.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        _hold()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _hold()
        result[key] = value
    return result


def _projects(value):
    if not isinstance(value, dict) or not set(value) <= BRANDS:
        _hold()
    seen = set()
    result = {}
    for brand, ids in value.items():
        if not isinstance(ids, (list, tuple)) or not 1 <= len(ids) <= 10:
            _hold()
        checked = [_uuid(x) for x in ids]
        if len(set(checked)) != len(checked) or seen.intersection(checked):
            _hold()
        seen.update(checked)
        result[brand] = sorted(checked)
    return result


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _transport(url: str, headers: dict[str, str]) -> tuple[int, str, bytes]:
    if not url.startswith(BASE + "/"):
        _hold()
    request = Request(url, headers=headers, method="GET")
    opener = build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=8) as response:
            return (
                response.status,
                response.headers.get("Content-Type", ""),
                response.read(MAX_BYTES + 1),
            )
    except HTTPError as exc:
        return exc.code, "", b""


def _key(path: Path) -> str:
    if not path.is_absolute():
        _hold()
    for component in (path, *path.parents):
        if component.is_symlink():
            _hold("Dedicated credential path is not permitted")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_mode & 0o077
            or info.st_nlink != 1
            or info.st_size > 80
        ):
            _hold("Dedicated credential file is not protected")
        value = os.read(fd, 81).decode("ascii").strip()
    finally:
        os.close(fd)
    if re.fullmatch(r"cwread_[A-Za-z0-9_-]{43}", value) is None:
        _hold("Dedicated credential has invalid form")
    return value


def _source_uri(value):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 2000 or any(ord(x) < 32 for x in value):
        _hold()
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            return None
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    except ValueError:
        _hold()


class Reader:
    def __init__(self, cfg: dict, *, key_file: Path = KEY_FILE, transport: Transport = _transport):
        if (
            not isinstance(cfg, dict)
            or set(cfg) != CONFIG_FIELDS
            or cfg.get("schema") != "creator-workspace-reader-v1"
            or cfg.get("enabled") is not True
            or cfg.get("api_base") != BASE
        ):
            _hold("Metadata connection is disabled or invalid")
        self.grant_id = _uuid(cfg["grant_id"])
        self.expiry = _instant(cfg["expires_at"])
        if self.expiry <= datetime.now(timezone.utc):
            _hold("Metadata grant has expired")
        self.scope = cfg["scope"]
        self.projects = _projects(cfg["projects"])
        if self.scope == "active":
            self.owner_id = _uuid(cfg["owner_id"])
            if not self.projects:
                _hold()
        elif self.scope == "inventory":
            if cfg["owner_id"] is not None or self.projects:
                _hold()
            self.owner_id = None
        else:
            _hold()
        self._key_file = key_file
        self._transport = transport

    def _get(self, suffix: str):
        if self.expiry <= datetime.now(timezone.utc):
            _hold("Metadata grant has expired")
        try:
            token = _key(self._key_file)
            code, typ, body = self._transport(
                BASE + suffix,
                {
                    "Authorization": "CreatorRead " + token,
                    "Accept": "application/json",
                    "Cache-Control": "no-store",
                },
            )
            if code != 200:
                _hold("Metadata endpoint refused the request")
            if typ.split(";", 1)[0].strip().lower() != "application/json":
                _hold()
            if not isinstance(body, bytes) or len(body) > MAX_BYTES:
                _hold()
            value = json.loads(body.decode("utf-8"), object_pairs_hook=_unique)
            if not isinstance(value, dict):
                _hold()
            return value
        except ReaderHold:
            raise
        except Exception:
            raise ReaderHold("Metadata connection unavailable") from None

    def status(self):
        raw = self._get("/status")
        if (
            raw.get("principal") != "CREATOR_WORKSPACE_METADATA_READER"
            or raw.get("grant_id") != self.grant_id
            or raw.get("scope") != self.scope
            or any(
                raw.get(k) is not False
                for k in ("knowledge_writes", "provider_calls", "publishing_authorized")
            )
            or _projects(raw.get("project_scopes")) != self.projects
        ):
            _hold("Metadata authorization scope does not match")
        owner = _uuid(raw.get("owner_id"))
        if self.owner_id is not None and owner != self.owner_id:
            _hold("Metadata authorization owner does not match")
        expiry = _instant(raw.get("expires_at"))
        if expiry <= datetime.now(timezone.utc):
            _hold("Metadata authorization expired")
        return {
            "grant_id": self.grant_id,
            "owner_id": owner,
            "scope": self.scope,
            "expires_at": expiry.isoformat(),
            "project_scopes": self.projects,
            "knowledge_writes": False,
            "provider_calls": False,
            "publishing_authorized": False,
        }

    @staticmethod
    def _bounds(limit, offset, maximum):
        if (
            type(limit) is not int
            or type(offset) is not int
            or not 1 <= limit <= maximum
            or not 0 <= offset <= 5000
        ):
            _hold("Metadata request bounds refused")

    @staticmethod
    def _envelope(raw, limit, offset):
        if (
            raw.get("source_contents_fetched") is not False
            or raw.get("publishing_authorized") is not False
            or type(raw.get("offset")) is not int
            or raw["offset"] != offset
            or type(raw.get("has_more")) is not bool
            or not isinstance(raw.get("items"), list)
            or len(raw["items"]) > limit
        ):
            _hold("Metadata response contract refused")
        ids = [_uuid(row.get("id")) if isinstance(row, dict) else _hold() for row in raw["items"]]
        if len(set(ids)) != len(ids):
            _hold("Duplicate metadata identity refused")

    def inventory(self, *, limit=20, offset=0):
        if self.scope != "inventory":
            _hold("Inventory scope is not authorized")
        self._bounds(limit, offset, 50)
        status = self.status()
        raw = self._get("/projects?" + urlencode({"limit": limit, "offset": offset}))
        self._envelope(raw, limit, offset)
        if raw.get("scope") != "inventory" or raw.get("owner_id") != status["owner_id"]:
            _hold("Inventory owner mismatch")
        items = []
        for row in raw["items"]:
            if (
                not isinstance(row.get("name"), str)
                or len(row["name"]) > 300
                or not isinstance(row.get("status"), str)
            ):
                _hold()
            items.append({"id": row["id"], "name": row["name"], "status": row["status"][:32]})
        return {
            "state": "LIVE_OWNED_PROJECT_INVENTORY",
            "owner_id": status["owner_id"],
            "grant_id": self.grant_id,
            "items": items,
            "offset": offset,
            "has_more": raw["has_more"],
            "source_contents_fetched": False,
            "publishing_authorized": False,
        }

    def metadata(self, *, brand: str, project_id: str, limit=10, offset=0):
        if self.scope != "active" or project_id not in self.projects.get(brand, ()):
            _hold("Explicit brand and owned-project scope required")
        self._bounds(limit, offset, 20)
        self.status()
        raw = self._get(
            "/"
            + brand
            + "/knowledge?"
            + urlencode({"project_id": project_id, "limit": limit, "offset": offset})
        )
        self._envelope(raw, limit, offset)
        if (
            raw.get("brand") != brand
            or raw.get("project_id") != project_id
            or raw.get("grant_id") != self.grant_id
            or raw.get("provenance_state") != "METADATA_ONLY_ORIGINAL_SOURCE_NOT_READ"
        ):
            _hold("Metadata response scope refused")
        items = []
        for row in raw["items"]:
            if (
                row.get("project_id") != project_id
                or row.get("status") != "ready"
                or not isinstance(row.get("title"), str)
                or len(row["title"]) > 300
                or not isinstance(row.get("source_type"), str)
                or len(row["source_type"]) > 32
            ):
                _hold("Out-of-scope or malformed metadata item")
            for key in ("created_at", "updated_at"):
                _instant(row.get(key))
            items.append(
                {
                    key: row[key]
                    for key in (
                        "id",
                        "project_id",
                        "title",
                        "source_type",
                        "status",
                        "created_at",
                        "updated_at",
                    )
                }
            )
            items[-1]["source_uri"] = _source_uri(row.get("source_uri"))
        return {
            "state": "LIVE_METADATA_CANDIDATES_ONLY",
            "brand": brand,
            "project_id": project_id,
            "grant_id": self.grant_id,
            "items": items,
            "offset": offset,
            "has_more": raw["has_more"],
            "source_contents_fetched": False,
            "source_claims_verified": False,
            "publishing_authorized": False,
            "shareable_across_brands": False,
        }


def main():
    parser = argparse.ArgumentParser(
        description="Read-only scoped DEVON metadata, not source bodies"
    )
    parser.add_argument("--config", type=Path, default=CONFIG_FILE)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("status")
    sub.add_parser("inventory")
    p = sub.add_parser("metadata")
    p.add_argument("--brand", choices=sorted(BRANDS), required=True)
    p.add_argument("--project-id", required=True)
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()
    try:
        if args.config.is_symlink() or args.config.stat().st_size > 16000:
            _hold()
        cfg = json.loads(args.config.read_text(encoding="utf-8"), object_pairs_hook=_unique)
        reader = Reader(cfg)
        if args.action == "status":
            result = reader.status()
        elif args.action == "inventory":
            result = reader.inventory()
        else:
            result = reader.metadata(
                brand=args.brand, project_id=args.project_id, limit=args.limit, offset=args.offset
            )
        print(json.dumps(result, indent=2))
        return 0
    except (ReaderHold, OSError, ValueError, TypeError, KeyError):
        print(
            json.dumps(
                {
                    "state": "HOLD",
                    "reason": "Verified metadata connection unavailable",
                    "source_contents_fetched": False,
                    "publishing_authorized": False,
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
