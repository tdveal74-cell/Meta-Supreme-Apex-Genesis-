"""Graphify hosted MCP reader for DEVON (never a writer).

The connection requires a separately provisioned, renewable service-owned OAuth
access token. ChatGPT's Graphify login and a repository .mcp.json do not
authenticate DEVON. No auth values enter arguments, logs, or tool outputs.
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional

import httpx

ENDPOINT = "https://api.graphify.com/mcp"
REPOSITORY = "tdveal74-cell/Meta-Supreme-Apex-Genesis-"
PROTOCOL = "2025-03-26"
MAX_QUESTION_CHARS = 1200
MAX_CONTEXT_CHARS = 8000


class GraphifyUnavailable(RuntimeError):
    """Connection absent or remote graph read failed; never silently empty."""


def _rpc_response(response: httpx.Response) -> dict[str, Any]:
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
            messages = []
            for line in response.text.splitlines():
                if line.startswith("data:"):
                    data = line[5:].strip()
                    if data and data != "[DONE]":
                        messages.append(json.loads(data))
            results = [m for m in messages if isinstance(m, dict) and ("result" in m or "error" in m)]
            if not results:
                raise ValueError("missing MCP result event")
            return results[-1]
        value = response.json()
        if not isinstance(value, dict):
            raise ValueError("unexpected MCP response shape")
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
        async with httpx.AsyncClient(
            timeout=20.0, follow_redirects=False, transport=self._transport
        ) as client:
            async def post(payload: dict[str, Any], *, session: str = "") -> tuple[dict[str, Any], str]:
                req_headers = dict(headers)
                if session:
                    req_headers["Mcp-Session-Id"] = session
                response = await client.post(ENDPOINT, json=payload, headers=req_headers)
                return _rpc_response(response), response.headers.get("mcp-session-id", session)

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
                if "error" in hello or "result" not in hello:
                    raise GraphifyUnavailable("Graphify MCP initialize refused")
                initialized_headers = dict(headers)
                if session:
                    initialized_headers["Mcp-Session-Id"] = session
                init_response = await client.post(
                    ENDPOINT,
                    headers=initialized_headers,
                    json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                )
                _rpc_response(init_response)
                answer, _ = await post({
                    "jsonrpc": "2.0",
                    "id": 2,
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
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                raise GraphifyUnavailable("Graphify transport unavailable") from exc

        if "error" in answer:
            raise GraphifyUnavailable("Graphify MCP query returned an error")
        result = answer.get("result")
        if not isinstance(result, dict) or result.get("isError"):
            raise GraphifyUnavailable("Graphify MCP query was not successful")

        structured = result.get("structuredContent")
        if isinstance(structured, dict):
            payload = structured.get("result", structured)
            context = payload.get("context") if isinstance(payload, dict) else None
            commit = payload.get("freshness", {}).get("commit", "") if isinstance(payload, dict) else ""
        else:
            context, commit = None, ""
        if context is None:
            content = result.get("content", [])
            context = "\n".join(
                str(item.get("text", ""))
                for item in content if isinstance(item, dict) and item.get("type") == "text"
            )
        if not isinstance(context, str) or not context.strip():
            raise GraphifyUnavailable("Graphify returned no readable code context")
        return {
            "context": context[:MAX_CONTEXT_CHARS],
            "truncated": len(context) > MAX_CONTEXT_CHARS,
            "commit": str(commit)[:64],
        }
