"""Regression tests for DEVON's read-only Graphify Second Brain seam."""
from __future__ import annotations

import json

import httpx
import pytest

from services.agent_runtime.contracts import ToolRisk
from services.agent_runtime.tools import ToolRegistry
from services.graphify.agent_adapter import GraphifyCapabilityAdapter
from services.graphify.client import (
    REPOSITORY,
    GraphifyMCPClient,
    GraphifyUnavailable,
)


class FakeGraphify:
    async def query_graph(self, question):
        return {"context": "def approval_guard(): pass", "truncated": False, "commit": "abc1234"}


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
    assert message["index_commit"] == "abc1234"
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
                "protocolVersion": "2025-03-26", "capabilities": {"tools": {}}, "serverInfo": {"name": "graphify", "version": "1"}
            }}, headers={"Mcp-Session-Id": "session-1"})
        assert request.headers["mcp-session-id"] == "session-1"
        if payload["method"] == "notifications/initialized":
            return httpx.Response(202)
        if payload["method"] == "tools/list":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 2, "result": {
                "tools": [{"name": "query_graph", "annotations": {"readOnlyHint": True}}]
            }})
        assert payload["method"] == "tools/call"
        assert payload["params"]["name"] == "query_graph"
        assert payload["params"]["arguments"]["repository_id"] == REPOSITORY
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 3, "result": {
            "structuredContent": {"result": {
                "context": "ApprovalQueue in services/devon/approval.py",
                "freshness": {"commit": "a1b2c3d"},
            }},
            "isError": False,
        }})

    reader = GraphifyMCPClient(
        token="fake-token", transport=httpx.MockTransport(responder)
    )
    outcome = await reader.query_graph("where is ApprovalQueue?")
    assert outcome["commit"] == "a1b2c3d"
    assert "ApprovalQueue" in outcome["context"]
    assert [q["method"] for q in requests] == [
        "initialize", "notifications/initialized", "tools/list", "tools/call"
    ]
    assert "fake-token" not in str(outcome)


@pytest.mark.asyncio
async def test_graphify_mcp_sse_response(monkeypatch):
    monkeypatch.setenv("DEVON_GRAPHIFY_ENABLED", "1")

    def responder(request: httpx.Request):
        payload = json.loads(request.content)
        if payload["method"] == "initialize":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}}}})
        if payload["method"] == "notifications/initialized":
            return httpx.Response(202)
        if payload["method"] == "tools/list":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 2, "result": {
                "tools": [{"name": "query_graph", "annotations": {"readOnlyHint": True}}]
            }})
        body = json.dumps({"jsonrpc": "2.0", "id": 3, "result": {
            "content": [{"type": "text", "text": json.dumps({"context": "file.py:L22", "freshness": {"commit": "abcdef1"}})}]
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


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["write_hint", "missing_hint", "wrong_id", "wrong_protocol", "wrong_rpc", "no_commit", "wrong_repo", "oversize", "redirect", "rpc_error", "empty_context", "malformed_sse", "notification_error"])
async def test_adversarial_responses_refuse_without_leaking(monkeypatch, case):
    monkeypatch.setenv("DEVON_GRAPHIFY_ENABLED", "1")
    calls = []

    def responder(request):
        rpc = json.loads(request.content)
        calls.append(rpc["method"])
        def reply(result):
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": rpc.get("id"), "result": result})
        if case == "redirect":
            return httpx.Response(307, headers={"location": "https://other.example/steal"})
        if rpc["method"] == "initialize":
            if case == "wrong_id":
                return httpx.Response(200, json={"jsonrpc": "2.0", "id": 99, "result": {}})
            if case == "wrong_rpc":
                return httpx.Response(200, json={"jsonrpc": "1.0", "id": 1, "result": {}})
            return reply({"protocolVersion": "unsupported" if case == "wrong_protocol" else "2025-03-26", "capabilities": {"tools": {}}})
        if rpc["method"] == "notifications/initialized":
            return httpx.Response(500 if case == "notification_error" else 202)
        if rpc["method"] == "tools/list":
            annotations = {} if case == "missing_hint" else {"readOnlyHint": case != "write_hint"}
            return reply({"tools": [{"name": "query_graph", "annotations": annotations}]})
        assert rpc["params"]["arguments"]["repository_id"] == REPOSITORY
        if case == "rpc_error":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 3, "error": {"message": "fake-secret"}})
        if case == "malformed_sse":
            return httpx.Response(200, text="data: invalid\n\n", headers={"content-type": "text/event-stream"})
        payload = {"context": "file.py:L22", "freshness": {"commit": "abcdef1"}}
        if case == "no_commit":
            payload["freshness"] = {}
        if case == "empty_context":
            payload["context"] = ""
        if case == "wrong_repo":
            payload["repository_id"] = "other/repo"
        if case == "oversize":
            payload["context"] = "x" * 300000
        return reply({"structuredContent": payload})

    with pytest.raises(GraphifyUnavailable) as failure:
        await GraphifyMCPClient(token="fake-secret", transport=httpx.MockTransport(responder)).query_graph("find approval")
    assert "fake-secret" not in str(failure.value)
    if case in {"write_hint", "missing_hint", "wrong_id", "wrong_protocol", "wrong_rpc", "redirect", "notification_error"}:
        assert "tools/call" not in calls


@pytest.mark.asyncio
@pytest.mark.parametrize("question", ["", " ", "x" * 1201])
async def test_invalid_question_never_connects(monkeypatch, question):
    monkeypatch.setenv("DEVON_GRAPHIFY_ENABLED", "true")
    def never(request):
        raise AssertionError("invalid question reached network")
    with pytest.raises(GraphifyUnavailable):
        await GraphifyMCPClient(token="fake", transport=httpx.MockTransport(never)).query_graph(question)


def test_multiline_sse_matches_request_and_rejects_wrong_id():
    from services.graphify.client import _rpc_response
    body = 'data: {"jsonrpc":"2.0",\ndata: "id":3,"result":{"ok":true}}\n\n'
    response = httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})
    assert _rpc_response(response, 3)["result"]["ok"]
    with pytest.raises(GraphifyUnavailable):
        _rpc_response(response, 4)


@pytest.mark.asyncio
async def test_sse_returns_before_open_stream_eof(monkeypatch):
    monkeypatch.setenv("DEVON_GRAPHIFY_ENABLED", "true")
    class OpenStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: {"jsonrpc":"2.0","id":3,"result":{"structuredContent":{"context":"file.py:L22","freshness":{"commit":"abcdef1"}}}}\n\n'
            raise AssertionError("client waited beyond matching event")
    def responder(request):
        rpc = json.loads(request.content)
        if rpc["method"] == "initialize":
            value = {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}}}
        elif rpc["method"] == "notifications/initialized":
            return httpx.Response(202)
        elif rpc["method"] == "tools/list":
            value = {"tools": [{"name": "query_graph", "annotations": {"readOnlyHint": True}}]}
        else:
            return httpx.Response(200, stream=OpenStream(), headers={"content-type": "text/event-stream"})
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": rpc["id"], "result": value})
    result = await GraphifyMCPClient(token="fake", transport=httpx.MockTransport(responder)).query_graph("find approval")
    assert result["commit"] == "abcdef1"
