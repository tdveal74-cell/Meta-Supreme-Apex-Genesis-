"""Small allowlisted Notion REST client for DEVON capability adapters.

The token is configuration, never a tool argument or output. A page can only be
created in a database named in `services.devon.vault.NOTION_DATABASES`, with only
the properties and select options that map lists, and every create is read back
before it is reported, because a 200 from the create call is a claim and the
read back is the receipt.

Notion API version 2022-06-28 is pinned. It addresses a database by its
database id, which is right for the three single source databases in the map.
Written 2026-10-24 against the published API and a mock transport; no call has
been made against the live workspace from this code yet, and the first one is
the proof. A token that authenticates still sees nothing until each database is
shared with the integration, which is the trap `vault.NOTION["known_trap"]`
records.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date
from typing import Any, Dict, Iterable, List, Mapping, Optional

import httpx

from services.devon.vault import NOTION_DATABASES

API_VERSION = "2022-06-28"
MAX_TITLE_CHARS = 200
MAX_TEXT_CHARS = 2_000
"""Notion's own ceiling for one rich text object."""
MAX_BODY_CHARS = 20_000
MAX_ERROR_CHARS = 2_000
_PAGE_ID_RE = re.compile(r"^[0-9a-fA-F]{32}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class NotionRESTError(ValueError):
    """A Notion request cannot proceed safely or the remote API refused it."""


def _bare(identifier: str) -> str:
    return (identifier or "").replace("-", "").strip().lower()


class NotionRESTClient:
    def __init__(
        self,
        *,
        token: Optional[str] = None,
        databases: Optional[Mapping[str, Mapping[str, Any]]] = None,
        base_url: Optional[str] = None,
        timeout_seconds: float = 30.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self.token = (
            token if token is not None else os.getenv("DEVON_NOTION_TOKEN", "")
        ).strip()
        self.databases: Dict[str, Mapping[str, Any]] = dict(
            databases if databases is not None else NOTION_DATABASES
        )
        self.base_url = (
            base_url or os.getenv("DEVON_NOTION_API_URL") or "https://api.notion.com"
        ).rstrip("/")
        self.timeout_seconds = max(1.0, min(float(timeout_seconds), 120.0))
        self.transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.token and self.databases)

    @property
    def database_names(self) -> List[str]:
        return sorted(self.databases)

    def require_database(self, name: str) -> Mapping[str, Any]:
        key = (name or "").strip().lower()
        spec = self.databases.get(key)
        if spec is None:
            known = ", ".join(self.database_names) or "none"
            raise NotionRESTError(
                f"database is not allowlisted for DEVON: {name!r}. Known: {known}"
            )
        return spec

    def build_page(
        self,
        database: str,
        *,
        title: str,
        properties: Optional[Mapping[str, Any]] = None,
        body: str = "",
    ) -> Dict[str, Any]:
        """Build the create body without sending it. Pure, so it can be tested.

        Every refusal names the property and the value, because "invalid
        properties" with no name is the error Notion itself returns and it cost
        a guessing round each time.
        """
        spec = self.require_database(database)
        clean_title = " ".join((title or "").split())
        if not clean_title:
            raise NotionRESTError("title is empty")
        if len(clean_title) > MAX_TITLE_CHARS:
            raise NotionRESTError(
                f"title is {len(clean_title)} characters; the limit is {MAX_TITLE_CHARS}"
            )
        allowed: Mapping[str, Any] = spec["properties"]
        payload_props: Dict[str, Any] = {
            spec["title_property"]: {"title": [_text(clean_title)]}
        }
        for name, value in dict(properties or {}).items():
            if name not in allowed:
                raise NotionRESTError(
                    f"property {name!r} is not writable in {database}. "
                    f"Writable: {', '.join(sorted(allowed))}"
                )
            kind, options = allowed[name]
            payload_props[name] = _property(name, kind, options, value)

        clean_body = (body or "").strip()
        if len(clean_body) > MAX_BODY_CHARS:
            raise NotionRESTError(
                f"body is {len(clean_body)} characters; the limit is {MAX_BODY_CHARS}"
            )
        page: Dict[str, Any] = {
            "parent": {"database_id": spec["database_id"]},
            "properties": payload_props,
        }
        if clean_body:
            page["children"] = _paragraphs(clean_body)
        return page

    async def create_page(
        self,
        database: str,
        *,
        title: str,
        properties: Optional[Mapping[str, Any]] = None,
        body: str = "",
    ) -> Dict[str, Any]:
        spec = self.require_database(database)
        page = self.build_page(database, title=title, properties=properties, body=body)
        created = await self._request("POST", "/v1/pages", json_body=page)
        page_id = str(created.get("id") or "")
        if not page_id:
            raise NotionRESTError(
                "Notion answered the create without a page id, so nothing can be "
                "confirmed. Do not assume the page exists."
            )
        readback = await self._request("GET", f"/v1/pages/{page_id}")
        parent = readback.get("parent") if isinstance(readback.get("parent"), dict) else {}
        if _bare(str(parent.get("database_id") or "")) != _bare(spec["database_id"]):
            raise NotionRESTError(
                f"page {page_id} was created but reads back under parent "
                f"{parent!r}, not {database}. Check it by hand before trusting it."
            )
        return {
            "database": database.strip().lower(),
            "page_id": page_id,
            "url": readback.get("url") or created.get("url"),
            "created_time": readback.get("created_time"),
            "title": " ".join(title.split()),
            "read_back": True,
        }

    async def read_page(self, page_id: str) -> Dict[str, Any]:
        clean = _bare(page_id)
        if not _PAGE_ID_RE.fullmatch(clean):
            raise NotionRESTError("page_id must be a 32 character Notion id")
        data = await self._request("GET", f"/v1/pages/{clean}")
        parent = data.get("parent") if isinstance(data.get("parent"), dict) else {}
        parent_id = _bare(str(parent.get("database_id") or ""))
        names = [
            name for name, spec in self.databases.items()
            if _bare(spec["database_id"]) == parent_id
        ]
        if not names:
            raise NotionRESTError(
                "that page is not in an allowlisted DEVON database, so it is not read"
            )
        return {
            "database": names[0],
            "page_id": data.get("id"),
            "url": data.get("url"),
            "created_time": data.get("created_time"),
            "last_edited_time": data.get("last_edited_time"),
            "archived": data.get("archived"),
            "properties": _plain_properties(data.get("properties") or {}),
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.configured:
            raise NotionRESTError(
                "Notion adapter is not configured. Set DEVON_NOTION_TOKEN and share "
                "each database with the integration."
            )
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": API_VERSION,
            "Content-Type": "application/json",
            "User-Agent": "DEVON-Agent-Runtime",
        }
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout_seconds,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                response = await client.request(method.upper(), path, json=json_body)
        except httpx.HTTPError as exc:
            raise NotionRESTError(f"Notion transport error: {exc}") from exc

        if not 200 <= response.status_code < 300:
            message = _error_message(response)
            hint = ""
            if response.status_code == 404:
                hint = " A 404 from a valid id usually means the database is not shared with the integration."
            raise NotionRESTError(
                f"Notion API {response.status_code} for {method.upper()} {path}: {message}{hint}"
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise NotionRESTError("Notion API returned non-JSON data") from exc
        if not isinstance(data, dict):
            raise NotionRESTError("Notion API returned an unexpected response shape")
        return data


def _text(content: str) -> Dict[str, Any]:
    return {"type": "text", "text": {"content": content}}


def _chunks(value: str, size: int = MAX_TEXT_CHARS) -> Iterable[str]:
    for start in range(0, len(value), size):
        yield value[start : start + size]


def _paragraphs(body: str) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    for paragraph in [p.strip() for p in body.split("\n\n") if p.strip()]:
        for piece in _chunks(paragraph):
            blocks.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [_text(piece)]},
                }
            )
    if len(blocks) > 100:
        raise NotionRESTError(
            f"body makes {len(blocks)} blocks; Notion takes at most 100 in one create"
        )
    return blocks


def _property(name: str, kind: str, options: tuple, value: Any) -> Dict[str, Any]:
    if kind == "select":
        choice = str(value or "").strip()
        if choice not in options:
            raise NotionRESTError(
                f"{name} must be one of {', '.join(options)}; got {value!r}"
            )
        return {"select": {"name": choice}}
    if kind == "multi_select":
        items = value if isinstance(value, (list, tuple)) else [value]
        chosen = [str(item or "").strip() for item in items if str(item or "").strip()]
        unknown = [item for item in chosen if item not in options]
        if unknown:
            raise NotionRESTError(
                f"{name} takes only {', '.join(options)}; got {', '.join(unknown)}"
            )
        return {"multi_select": [{"name": item} for item in dict.fromkeys(chosen)]}
    if kind == "rich_text":
        text = str(value or "").strip()
        if len(text) > MAX_TEXT_CHARS:
            raise NotionRESTError(
                f"{name} is {len(text)} characters; the limit is {MAX_TEXT_CHARS}"
            )
        return {"rich_text": [_text(text)] if text else []}
    if kind == "date":
        raw = str(value or "").strip()
        if not _DATE_RE.fullmatch(raw):
            raise NotionRESTError(f"{name} must be a date as YYYY-MM-DD; got {value!r}")
        try:
            date.fromisoformat(raw)
        except ValueError as exc:
            raise NotionRESTError(f"{name} is not a real date: {raw}") from exc
        return {"date": {"start": raw}}
    raise NotionRESTError(f"{name} has type {kind}, which this adapter does not write")


def _plain_properties(properties: Mapping[str, Any]) -> Dict[str, Any]:
    """Flatten Notion's property objects into values a model can read."""
    plain: Dict[str, Any] = {}
    for name, prop in properties.items():
        if not isinstance(prop, dict):
            continue
        kind = prop.get("type")
        raw = prop.get(kind) if kind else None
        if kind in ("title", "rich_text") and isinstance(raw, list):
            plain[name] = "".join(str(part.get("plain_text") or "") for part in raw if isinstance(part, dict))
        elif kind == "select":
            plain[name] = raw.get("name") if isinstance(raw, dict) else None
        elif kind == "multi_select" and isinstance(raw, list):
            plain[name] = [item.get("name") for item in raw if isinstance(item, dict)]
        elif kind == "date":
            plain[name] = raw.get("start") if isinstance(raw, dict) else None
        elif kind in ("created_time", "last_edited_time", "checkbox", "number", "url"):
            plain[name] = raw
    return plain


def _error_message(response: httpx.Response) -> str:
    try:
        data = response.json()
        if isinstance(data, dict):
            message = str(data.get("message") or json.dumps(data, ensure_ascii=False))
        else:
            message = str(data)
    except ValueError:
        message = response.text
    return message[:MAX_ERROR_CHARS]
