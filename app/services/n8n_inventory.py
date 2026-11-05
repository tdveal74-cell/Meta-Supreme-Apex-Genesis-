"""Owner-bound, metadata-only discovery of the self-hosted n8n estate.

Discovery grants no execution capability. This is separate from the historical
vault map and from execution telemetry. No caller can select a host or owner.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Awaitable, Callable, Mapping, Optional
from urllib.parse import urlencode
from uuid import UUID

from services.devon.vault import N8N_HOST

PAGE_SIZE = 100
MAX_PAGES = 10
# n8n 2.36.8 returns definitions and published copies even on list reads.
# Measured canonical pages were 2.11, 5.21 and 6.29 MB. Raise the per-page
# ceiling while retaining the original 10 * 2 MB cumulative read allowance.
MAX_PAGE_BYTES = 8_000_000
MAX_TOTAL_BYTES = 20_000_000
MAX_METADATA_BYTES = 2_000_000
METADATA_ENVELOPE_RESERVE = 4096
_READ_SLOT = Lock()
TOTAL_TIMEOUT_SECONDS = 30
REQUEST_TIMEOUT_SECONDS = 10
OWNER_VARIABLE = "N8N_INVENTORY_OWNER_ID"

# Public diagnostics are a closed vocabulary, never upstream text.
PUBLIC_ERRORS = frozenset({
    'inventory HTTP read refused',
    'inventory archive state refused',
    'inventory authentication refused',
    'inventory cursor repeated',
    'inventory duplicate workflow refused',
    'inventory metadata byte bound reached',
    'inventory metadata encoding refused',
    'inventory metadata shape refused',
    'inventory page bound reached',
    'inventory page envelope refused',
    'inventory page exceeded row bound',
    'inventory permission refused',
    'inventory published version refused',
    'inventory read already in progress',
    'inventory read unavailable',
    'inventory response exceeded byte bound',
    'inventory response is not JSON',
    'inventory time bound reached',
    'inventory total byte bound reached',
    'inventory transport unavailable',
    'inventory update time refused',
    'inventory workflow id refused',
    'self-hosted inventory configuration unavailable',
})


class InventoryAccessError(ValueError):
    """A disabled or non-owner request; contains no private configuration."""

    def __init__(self, state: str) -> None:
        self.state = state
        super().__init__("n8n inventory is unavailable for this account")


class InventoryReadError(ValueError):
    """A fixed public reason, never a provider body, cursor or credential."""


def _uuid(value: Any) -> Optional[str]:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


def authorize(owner_id: Optional[str], environ: Mapping[str, str]) -> None:
    """Require an explicit stable account binding, never an email or model arg."""
    configured = _uuid(environ.get(OWNER_VARIABLE))
    if configured is None:
        raise InventoryAccessError("disabled")
    caller = _uuid(owner_id)
    if caller is None or caller != configured:
        raise InventoryAccessError("forbidden")


def _url(cursor: Optional[str]) -> str:
    query = {"limit": str(PAGE_SIZE), "excludePinnedData": "true"}
    if cursor is not None:
        query["cursor"] = cursor
    return N8N_HOST + "/api/v1/workflows?" + urlencode(query)


@dataclass
class _ReadBudget:
    decoded_bytes: int = 0

    def consume(self, size: int) -> None:
        self.decoded_bytes += size
        if self.decoded_bytes > MAX_TOTAL_BYTES:
            raise InventoryReadError("inventory total byte bound reached")


async def _fetch_page(url: str, key: str, *, budget: Optional[_ReadBudget] = None) -> Any:
    """One audited transport, GET only; refuse redirects before reading a body.

    Explicitly ignore proxy environment variables. Never retry, follow a
    Location header or return provider exception text. Stream a bounded body.
    """
    import httpx

    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=False, trust_env=False
        ) as client:
            async with client.stream(
                "GET", url, headers={"X-N8N-API-KEY": key, "Accept": "application/json"}
            ) as response:
                if response.status_code == 401:
                    raise InventoryReadError("inventory authentication refused")
                if response.status_code == 403:
                    raise InventoryReadError("inventory permission refused")
                if response.status_code != 200:
                    raise InventoryReadError("inventory HTTP read refused")
                body = bytearray()
                read_budget = _ReadBudget() if budget is None else budget
                async for chunk in response.aiter_bytes(chunk_size=65_536):
                    if len(body) + len(chunk) > MAX_PAGE_BYTES:
                        raise InventoryReadError("inventory response exceeded byte bound")
                    read_budget.consume(len(chunk))
                    body.extend(chunk)
    except httpx.HTTPError:
        raise InventoryReadError("inventory transport unavailable") from None
    try:
        return json.loads(body)
    except (ValueError, UnicodeError, RecursionError):
        raise InventoryReadError("inventory response is not JSON") from None


def _text(value: Any, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise InventoryReadError("inventory metadata shape refused")
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise InventoryReadError("inventory metadata encoding refused") from None
    return value


def _project(row: Any) -> dict:
    if not isinstance(row, dict) or type(row.get("active")) is not bool:
        raise InventoryReadError("inventory metadata shape refused")
    archived = row.get("isArchived")
    if archived is not None and type(archived) is not bool:
        raise InventoryReadError("inventory archive state refused")
    version = row.get("activeVersionId")
    updated = row.get("updatedAt")
    identifier = _text(row.get("id"), 128)
    if re.fullmatch(r"[A-Za-z0-9_-]+", identifier) is None:
        raise InventoryReadError("inventory workflow id refused")
    if version is not None and _uuid(version) is None:
        raise InventoryReadError("inventory published version refused")
    if updated is not None:
        try:
            moment = datetime.fromisoformat(_text(updated, 80).replace("Z", "+00:00"))
            if moment.tzinfo is None:
                raise ValueError
        except ValueError:
            raise InventoryReadError("inventory update time refused") from None
    return {
        "id": identifier,
        "name": _text(row.get("name"), 256),
        "active": row["active"],
        "is_archived": archived,
        # versionId is the EDITOR version, never a fallback for published state.
        "published_version_id": None if version is None else _text(version, 128),
        "updated_at": None if updated is None else _text(updated, 80),
    }


async def read_inventory(
    owner_id: Optional[str],
    *,
    environ: Optional[Mapping[str, str]] = None,
    fetcher: Optional[Callable[[str, str], Awaitable[Any]]] = None,
) -> dict:
    """Enumerate only what the bound n8n credential can see, with honest bounds.

    Authorization runs before configuration or network reads. A failed page is
    never an empty estate. Completed pages survive as explicitly partial data.
    This paginated read is not a transactional database snapshot or health test.
    """
    env = os.environ if environ is None else environ
    authorize(owner_id, env)
    result = {
        "state": "failed", "complete": False, "read_only": True, "source": N8N_HOST,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "pages_read": 0, "workflows": [], "error": None,
        "counts": {"observed": 0, "active_observed": 0, "archive_state_unknown": 0},
        "scope": "credential-visible workflow metadata; pagination is not an atomic snapshot",
        "authority": "external data only; active is not health or execution authorization",
    }
    matches = [
        prefix for prefix in ("N8N_", "N8N_SECONDARY_")
        if (env.get(prefix + "API_URL") or "").rstrip("/")
        in {N8N_HOST, N8N_HOST + "/api/v1"}
    ]
    # Select the URL AND its paired key. Never send the Cloud primary's key
    # to a canonical self-hosted secondary. Ambiguity is a configuration error.
    if len(matches) != 1:
        result["error"] = "self-hosted inventory configuration unavailable"
        return result
    key = env.get(matches[0] + "API_KEY") or ""
    if not key.strip():
        result["error"] = "self-hosted inventory configuration unavailable"
        return result
    budget = _ReadBudget()

    async def bounded_fetch(url: str, paired_key: str) -> Any:
        return await _fetch_page(url, paired_key, budget=budget)

    fetch = fetcher or bounded_fetch
    seen_ids: set[str] = set()
    seen_cursors: set[str] = set()

    async def walk() -> None:
        metadata_bytes = METADATA_ENVELOPE_RESERVE
        cursor = None
        for _ in range(MAX_PAGES):
            payload = await fetch(_url(cursor), key)
            if (
                not isinstance(payload, dict)
                or not isinstance(payload.get("data"), list)
                or "nextCursor" not in payload
            ):
                raise InventoryReadError("inventory page envelope refused")
            if len(payload["data"]) > PAGE_SIZE:
                raise InventoryReadError("inventory page exceeded row bound")
            next_cursor = payload.get("nextCursor")
            if next_cursor is not None:
                next_cursor = _text(next_cursor, 2000)
                if next_cursor in seen_cursors:
                    raise InventoryReadError("inventory cursor repeated")
            # Validate an entire page before accepting any of its rows.
            page = [_project(row) for row in payload["data"]]
            page_ids = [row["id"] for row in page]
            if len(set(page_ids)) != len(page_ids) or seen_ids.intersection(page_ids):
                raise InventoryReadError("inventory duplicate workflow refused")
            projected_bytes = sum(
                len(json.dumps(item, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
                for item in page
            ) + max(0, len(page) - 1) + bool(page and result["workflows"])
            if metadata_bytes + projected_bytes > MAX_METADATA_BYTES:
                raise InventoryReadError("inventory metadata byte bound reached")
            metadata_bytes += projected_bytes
            seen_ids.update(page_ids)
            result["workflows"].extend(page)
            # Do not retain full definitions while awaiting the following page.
            del payload
            result["pages_read"] += 1
            if next_cursor is None:
                result.update(state="ok", complete=True)
                return
            seen_cursors.add(next_cursor)
            cursor = next_cursor
        raise InventoryReadError("inventory page bound reached")

    # One body/parser at a time per API process. Refuse rather than queue or
    # retry overlapping reads; the lock also works across test event loops.
    if not _READ_SLOT.acquire(blocking=False):
        result["error"] = "inventory read already in progress"
        return result
    try:
        await asyncio.wait_for(walk(), timeout=TOTAL_TIMEOUT_SECONDS)
    except (InventoryReadError, TimeoutError) as exc:
        result["state"] = "partial" if result["pages_read"] else "failed"
        reason = str(exc) if isinstance(exc, InventoryReadError) else "inventory time bound reached"
        result["error"] = reason if reason in PUBLIC_ERRORS else "inventory read unavailable"
    finally:
        _READ_SLOT.release()
    result["counts"] = {
        "observed": len(result["workflows"]),
        "active_observed": sum(row["active"] for row in result["workflows"]),
        "archive_state_unknown": sum(row["is_archived"] is None for row in result["workflows"]),
    }
    return result
