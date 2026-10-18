"""Graphify hosted MCP reader for DEVON (never a writer).

The connection requires a separately provisioned, renewable service-owned OAuth
access token. ChatGPT's Graphify login and a repository .mcp.json do not
authenticate DEVON. No auth values enter arguments, logs, or tool outputs.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any, Optional

import httpx

ENDPOINT = "https://api.graphify.com/mcp"
REPOSITORY = "tdveal74-cell/Meta-Supreme-Apex-Genesis-"
PROTOCOL = "2025-03-26"
MAX_QUESTION_CHARS = 1200
MAX_CONTEXT_CHARS = 8000
MAX_RESPONSE_BYTES = 256 * 1024
MAX_REQUEST_SECONDS = 20.0


class GraphifyUnavailable(RuntimeError):
    """Connection absent or remote graph read failed; never silently empty."""


def _rpc_response(response: httpx.Response, expected_id: int) -> dict[str, Any]:
    """Decode MCP JSON and streamable HTTP SSE without treating text as instructions."""
    if response.status_code == 401:
        raise GraphifyUnavailable("Graphify service authentication expired or refused")
    if response.status_code >= 400:
        raise GraphifyUnavailable(f"Graphify service refused request (HTTP {response.status_code})")
    if response.status_code == 202 or not response.content:
        return {}
    typ = response.headers.get("content-type", "")
    try:
        if "text/event-stream" in typ:
            # SSE data fields join with newlines within an event, not per line.
            messages, fields = [], []
            for line in response.text.splitlines() + [""]:
                if not line:
                    if fields:
                        messages.append(json.loads("\n".join(fields)))
                        fields = []
                elif line.startswith("data:"):
                    fields.append(line[5:].removeprefix(" "))
            results = [m for m in messages if isinstance(m, dict)
                       and m.get("id") == expected_id
                       and ("result" in m or "error" in m)]
            if len(results) != 1:
                raise ValueError("missing or ambiguous MCP result event")
            value = results[0]
        else:
            value = response.json()
        if not isinstance(value, dict):
            raise ValueError("unexpected MCP response shape")
        if (value.get("jsonrpc") != "2.0" or type(value.get("id")) is not int
                or value["id"] != expected_id
                or ("result" in value) == ("error" in value)):
            raise ValueError("invalid MCP response envelope")
        return value
    except (ValueError, json.JSONDecodeError) as exc:
        raise GraphifyUnavailable("Graphify returned an unreadable MCP response") from exc


class GraphifyMCPClient:
    def __init__(
        self,
        *,
        token: Optional[str] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self._token = (token if token is not None else os.getenv("DEVON_GRAPHIFY_ACCESS_TOKEN", "")).strip()
        self._enabled = os.getenv("DEVON_GRAPHIFY_ENABLED", "").lower() in {"1", "true", "yes", "on"}
        self._transport = transport

    @property
    def configured(self) -> bool:
        return bool(self._enabled and self._token)

    async def query_graph(self, question: str) -> dict[str, str | bool]:
        clean = (question or "").strip()
        if not clean or len(clean) > MAX_QUESTION_CHARS:
            raise GraphifyUnavailable("Graphify question must contain 1–1200 characters")
        if not self.configured:
            raise GraphifyUnavailable("Graphify is not connected to DEVON: service OAuth or feature flag missing")

        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": PROTOCOL,
        }
        async with asyncio.timeout(MAX_REQUEST_SECONDS), httpx.AsyncClient(
            timeout=20.0, follow_redirects=False, transport=self._transport
        ) as client:
            async def post(payload: dict[str, Any], *, session: str = "") -> tuple[dict[str, Any], str]:
                req_headers = dict(headers)
                if session:
                    req_headers["Mcp-Session-Id"] = session
                async with client.stream("POST", ENDPOINT, json=payload, headers=req_headers) as response:
                    if response.status_code != 200:
                        if response.status_code == 401:
                            raise GraphifyUnavailable("Graphify service authentication expired or refused")
                        raise GraphifyUnavailable("Graphify MCP request refused")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                            raise GraphifyUnavailable("Graphify response exceeds byte limit")
                        body.extend(chunk)
                        if "text/event-stream" in response.headers.get("content-type", ""):
                            # A server may keep SSE open after replying. Stop on the
                            # matching complete event instead of waiting for EOF.
                            frames = bytes(body).replace(b"\r\n", b"\n").split(b"\n\n")[:-1]
                            for frame in frames:
                                data = b"\n".join(line[5:].lstrip(b" ") for line in frame.split(b"\n") if line.startswith(b"data:"))
                                if not data:
                                    continue
                                try:
                                    event = json.loads(data)
                                except ValueError as exc:
                                    raise GraphifyUnavailable("Graphify returned an unreadable MCP response") from exc
                                if isinstance(event, dict) and event.get("id") == payload["id"] and ("result" in event or "error" in event):
                                    buffered = httpx.Response(200, headers=response.headers, content=frame + b"\n\n")
                                    return _rpc_response(buffered, payload["id"]), response.headers.get("mcp-session-id", session)
                    buffered = httpx.Response(200, headers=response.headers, content=bytes(body))
                    return _rpc_response(buffered, payload["id"]), response.headers.get("mcp-session-id", session)

            try:
                hello, session = await post({
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": PROTOCOL,
                        "capabilities": {},
                        "clientInfo": {"name": "DEVON Second Brain (read-only)", "version": "1.0"},
                    },
                })
                if ("error" in hello or not isinstance(hello.get("result"), dict)
                        or hello["result"].get("protocolVersion") != PROTOCOL
                        or not isinstance(hello["result"].get("capabilities"), dict)
                        or not isinstance(hello["result"]["capabilities"].get("tools"), dict)):
                    raise GraphifyUnavailable("Graphify MCP initialize refused")
                initialized_headers = dict(headers)
                if session:
                    initialized_headers["Mcp-Session-Id"] = session
                async with client.stream(
                    "POST", ENDPOINT, headers=initialized_headers,
                    json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                ) as initialized:
                    if initialized.status_code != 202:
                        raise GraphifyUnavailable("Graphify initialized notification refused")
                # query_graph may write memory with workspace trail capture enabled.
                # Refuse unknown/write-capable declarations before sending the question.
                listing, _ = await post({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, session=session)
                listed = listing.get("result")
                if (not isinstance(listed, dict) or listed.get("nextCursor")
                        or not isinstance(listed.get("tools"), list)):
                    raise GraphifyUnavailable("Graphify read-only capability could not be verified")
                matches = [tool for tool in listed["tools"]
                           if isinstance(tool, dict) and tool.get("name") == "query_graph"]
                if len(matches) != 1 or not isinstance(matches[0].get("annotations"), dict) or matches[0]["annotations"].get("readOnlyHint") is not True:
                    raise GraphifyUnavailable("Graphify query is not explicitly read-only; trail capture may write memory")
                answer, _ = await post({
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "query_graph",
                        "arguments": {
                            "repository_id": REPOSITORY,
                            "question": clean,
                            "budget": 3500,
                            "k": 8,
                        },
                    },
                }, session=session)
            except (httpx.RequestError, TimeoutError) as exc:
                raise GraphifyUnavailable("Graphify transport unavailable") from exc

        if "error" in answer:
            raise GraphifyUnavailable("Graphify MCP query returned an error")
        result = answer.get("result")
        if not isinstance(result, dict) or result.get("isError"):
            raise GraphifyUnavailable("Graphify MCP query was not successful")

        payload = result.get("structuredContent")
        if payload is None:
            content = result.get("content")
            if not isinstance(content, list):
                raise GraphifyUnavailable("Graphify returned no structured code evidence")
            texts = [item.get("text") for item in content
                     if isinstance(item, dict) and item.get("type") == "text"]
            if len(texts) != 1 or not isinstance(texts[0], str):
                raise GraphifyUnavailable("Graphify returned ambiguous code evidence")
            try:
                payload = json.loads(texts[0])
            except ValueError as exc:
                raise GraphifyUnavailable("Graphify returned no indexed commit provenance") from exc
        if isinstance(payload, dict):
            payload = payload.get("result", payload)
        if not isinstance(payload, dict):
            raise GraphifyUnavailable("Graphify returned invalid code evidence")
        context = payload.get("context")
        freshness = payload.get("freshness")
        commit = freshness.get("commit") if isinstance(freshness, dict) else None
        if not isinstance(context, str) or not context.strip():
            raise GraphifyUnavailable("Graphify returned no readable code context")
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-fA-F]{7,40}", commit):
            raise GraphifyUnavailable("Graphify returned no valid indexed commit")
        for field in ("repository", "repository_id"):
            if field in payload and payload[field] != REPOSITORY:
                raise GraphifyUnavailable("Graphify returned evidence for another repository")
        return {
            "context": context[:MAX_CONTEXT_CHARS],
            "truncated": len(context) > MAX_CONTEXT_CHARS or bool(payload.get("truncated", False)),
            "commit": commit,
        }
