"""Regression tests for DEVON's read-only Graphify Second Brain seam."""
from __future__ import annotations

import json

import httpx
import pytest

from services.agent_runtime.contracts import ToolRisk
from services.agent_runtime.tools import ToolRegistry
from services.graphify.agent_adapter import GraphifyCapabilityAdapter
from services.graphify.client import (
    GraphifyMCPClient, GraphifyUnavailable, REPOSITORY,
)


class FakeGraphify:
    async def query_graph(self, question):
        return {"context": "def approval_guard(): pass", "truncated": False, "commit": "abc123"}


@pytest.mark.asyncio
async def test_graphify_tool_is_read_only_and_untrusted():
    registry = ToolRegistry()
    GraphifyCapabilityAdapter(lambda: FakeGraphify()).register(registry)
    spec = registry.require("graphify.query_graph")
    assert spec.risk == ToolRisk.READ
    assert not spec.approval_required
    assert spec.parameters == ("question",)
    reply = await registry.execute("graphify.query_graph", {"question": "where is approval guard?"})
    assert reply.ok
    message = json.loads(reply.output)
    assert message["kind"] == "untrusted_external_code_evidence"
    assert message["instructions"].startswith("None.")
    assert message["repository"] == REPOSITORY
    assert message["index_commit"] == "abc123"
    assert reply.metadata["authority"] == "source-only"
    assert "remember" not in [x["name"] for x in registry.describe()]


@pytest.mark.asyncio
async def test_graphify_tool_rejects_unknown_args_without_calling_client():
    called = []

    class Never:
        async def query_graph(self, question):
            called.append(question)
            return {"context": "should not run"}

    registry = ToolRegistry()
    GraphifyCapabilityAdapter(lambda: Never()).register(registry)
    outcome = await registry.execute(
        "graphify.query_graph", {"question": "approval", "repository_id": "other/repo"}
    )
    assert not outcome.ok
    assert not called


@pytest.mark.asyncio
async def test_graphify_credentials_are_explicit_and_disabled_by_default(monkeypatch):
    monkeypatch.delenv("DEVON_GRAPHIFY_ENABLED", raising=False)
    monkeypatch.delenv("DEVON_GRAPHIFY_ACCESS_TOKEN", raising=False)
    with pytest.raises(GraphifyUnavailable, match="not connected"):
        await GraphifyMCPClient().query_graph("show approval callers")


@pytest.mark.asyncio
async def test_graphify_mcp_json_handshake_and_fixed_repository(monkeypatch):
    monkeypatch.setenv("DEVON_GRAPHIFY_ENABLED", "true")
    requests = []

    def responder(request: httpx.Request):
        assert request.url == "https://api.graphify.com/mcp"
        assert request.headers["authorization"] == "Bearer fake-token"
        payload = json.loads(request.content)
        requests.append(payload)
        if payload["method"] == "initialize":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {
                "protocolVersion": "2025-03-26", "capabilities": {}, "serverInfo": {"name": "graphify", "version": "1"}
            }}, headers={"Mcp-Session-Id": "session-1"})
        assert request.headers["mcp-session-id"] == "session-1"
        if payload["method"] == "notifications/initialized":
            return httpx.Response(202)
        assert payload["method"] == "tools/call"
        assert payload["params"]["name"] == "query_graph"
        assert payload["params"]["arguments"]["repository_id"] == REPOSITORY
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 2, "result": {
            "structuredContent": {"result": {
                "context": "ApprovalQueue in services/devon/approval.py",
                "freshness": {"commit": "a1b2c3"},
            }},
            "isError": False,
        }})

    reader = GraphifyMCPClient(
        token="fake-token", transport=httpx.MockTransport(responder)
    )
    outcome = await reader.query_graph("where is ApprovalQueue?")
    assert outcome["commit"] == "a1b2c3"
    assert "ApprovalQueue" in outcome["context"]
    assert [q["method"] for q in requests] == [
        "initialize", "notifications/initialized", "tools/call"
    ]
    assert "fake-token" not in str(outcome)


@pytest.mark.asyncio
async def test_graphify_mcp_sse_response(monkeypatch):
    monkeypatch.setenv("DEVON_GRAPHIFY_ENABLED", "1")

    def responder(request: httpx.Request):
        payload = json.loads(request.content)
        if payload["method"] == "initialize":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {"ok": True}})
        if payload["method"] == "notifications/initialized":
            return httpx.Response(202)
        body = json.dumps({"jsonrpc": "2.0", "id": 2, "result": {
            "content": [{"type": "text", "text": "file.py:L22"}]
        }})
        return httpx.Response(200, text=f"event: message\ndata: {body}\n\n", headers={
            "content-type": "text/event-stream"
        })

    reader = GraphifyMCPClient(token="fake-token", transport=httpx.MockTransport(responder))
    outcome = await reader.query_graph("find callers")
    assert outcome["context"] == "file.py:L22"


@pytest.mark.asyncio
async def test_graphify_auth_error_is_fail_closed(monkeypatch):
    monkeypatch.setenv("DEVON_GRAPHIFY_ENABLED", "1")
    def responder(request: httpx.Request):
        return httpx.Response(401, text="DO NOT LEAK SECRET")

    reader = GraphifyMCPClient(token="fake-token", transport=httpx.MockTransport(responder))
    with pytest.raises(GraphifyUnavailable) as failure:
        await reader.query_graph("find callers")
    assert "SECRET" not in str(failure.value)
