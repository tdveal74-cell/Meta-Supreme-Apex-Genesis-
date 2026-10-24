"""Network-isolated tests for the DEVON n8n Action Router adapter."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

ROUTER_JS = Path(__file__).parent / "n8n/devon/action-router/authorise_and_resolve_target.js"
ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


def _configure(monkeypatch, handler):
    from app.services.agent_tasks import n8n_action_client

    monkeypatch.setattr(n8n_action_client, "key", "test-devon-key")
    monkeypatch.setattr(n8n_action_client, "url", "https://n8n.test/webhook/devon-action")
    monkeypatch.setattr(n8n_action_client, "transport", httpx.MockTransport(handler))
    return n8n_action_client


def test_the_allowlist_matches_the_router_ceiling_for_ceiling():
    """A name the router does not know reads as a capability and is refused every time."""
    from services.n8n_actions.client import ACTIONS

    source = ROUTER_JS.read_text(encoding="utf-8")
    block = source[source.index("const TARGETS = {") : source.index("};", source.index("const TARGETS = {"))]
    router = dict(re.findall(r"'([a-z]+\.[a-z]+)':\s*\{[^}]*?max_blast_radius:\s*'([a-z_]+)'", block, re.S))
    assert router, "could not read TARGETS out of the router source"
    assert ACTIONS == router


def _envelope(**overrides):
    from services.n8n_actions.client import N8NActionClient

    kwargs = dict(
        action="airtable.row",
        summary="File one capture row for the cutover proof",
        payload={"airtable": {"table": "Inbox Captures", "fields": {"Title": "Proof"}}},
        area="Systems",
        binding="b" * 64,
        request_id="REQ-ABC123",
        decided_by="Tee",
        decided_at=datetime(2026, 10, 24, 12, tzinfo=timezone.utc),
        requested_at=datetime(2026, 10, 24, 11, tzinfo=timezone.utc),
        expires_at=datetime(2026, 10, 27, 12, tzinfo=timezone.utc),
        card="Write one row.",
        millis=1_793_000_000_000,
    )
    kwargs.update(overrides)
    return N8NActionClient(key="k").build_envelope(**kwargs)


def test_the_envelope_passes_every_router_gate_it_can_be_checked_against():
    env = _envelope()
    assert env["schema_version"] == "1.0.0"
    assert ULID_RE.fullmatch(env["intent_id"])
    assert env["state"] == "AUTHORIZED"
    assert env["approval"]["state"] == "granted"
    assert env["approval"]["expires_at"] == "2026-10-27T12:00:00Z"
    assert env["intent"]["blast_radius"] == "reversible_write"
    assert env["intent"]["payload"]["action"] == "airtable.row"
    key = env["idempotency_key"]
    assert 8 <= len(key) <= 128 and not re.search(r"[\s'\"\\{}]", key)


def test_the_same_binding_gives_the_same_ulid_and_key_with_no_clock_in_it():
    from services.n8n_actions.client import ulid_from

    a = _envelope(millis=None)
    b = _envelope(millis=None)
    assert a["intent_id"] == b["intent_id"]
    assert a["idempotency_key"] == b["idempotency_key"]
    assert _envelope(binding="c" * 64)["intent_id"] != a["intent_id"]
    assert ulid_from("same") == ulid_from("same") and ULID_RE.fullmatch(ulid_from("same"))


@pytest.mark.parametrize(
    "overrides,match",
    [
        ({"action": "shell.run"}, "not on the Action Router allowlist"),
        ({"summary": "do it"}, "at least 8"),
        ({"payload": {"action": "zapier.mcp"}}, "may not set action"),
        ({"payload": {"editforge": {}}}, "may not set editforge"),
    ],
)
def test_build_envelope_refuses(overrides, match):
    from services.n8n_actions.client import N8NActionError

    with pytest.raises(N8NActionError, match=match):
        _envelope(**overrides)


@pytest.mark.asyncio
async def test_dispatch_waits_for_approval_then_posts_once_with_the_key(client, auth_headers, monkeypatch):
    posts = []

    def handler(request: httpx.Request) -> httpx.Response:
        posts.append(request)
        assert request.headers["x-devon-key"] == "test-devon-key"
        body = json.loads(request.content)
        env = body["envelope"]
        assert body["action"] == "airtable.row" == env["intent"]["payload"]["action"]
        assert env["approval"]["state"] == "granted"
        returned = dict(env, state="EXECUTING")
        returned["execution"] = {"execution_id": "4300", "state": "running"}
        returned["artifacts"] = [{"uri": "https://airtable.com/app/tbl/recX", "kind": "airtable_record"}]
        return httpx.Response(200, json=returned)

    _configure(monkeypatch, handler)
    created = await client.post(
        "/api/v1/agent-tasks",
        headers=auth_headers,
        json={
            "goal": "File a capture through n8n",
            "steps": [
                {
                    "title": "Dispatch",
                    "tool": "n8n.dispatch",
                    "arguments": {
                        "action": "airtable.row",
                        "summary": "File one capture row for the proof",
                        "payload": {"airtable": {"table": "Inbox Captures", "fields": {"Title": "Proof"}}},
                        "area": "Systems",
                    },
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["task_id"]
    waiting = await client.post(f"/api/v1/agent-tasks/{task_id}/run", headers=auth_headers, json={})
    assert waiting.json()["task"]["state"] == "waiting_approval"
    assert posts == []

    step = waiting.json()["task"]["plan"]["steps"][0]
    await client.post(
        "/api/v1/devon/approvals/decide",
        headers=auth_headers,
        json={"request_id": step["approval_request_id"], "token": waiting.json()["approval_token"], "decision": "approve"},
    )
    resumed = await client.post(f"/api/v1/agent-tasks/{task_id}/run", headers=auth_headers, json={})
    task = resumed.json()["task"]
    assert task["state"] == "completed", resumed.text
    assert len(posts) == 1
    assert "recX" in task["observations"][0]["output"]
    assert "test-devon-key" not in resumed.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "answer,match",
    [
        ({"refused": True, "reason": "REFUSED: the approval expired"}, "refused: REFUSED: the approval expired"),
        ({"outcome": "executor_returned_nothing_usable", "envelope": {"state": "AUTHORIZED"}}, "no executor confirmed"),
        ([], "unexpected shape"),
    ],
)
async def test_a_refusal_or_an_empty_answer_is_never_reported_done(answer, match):
    from services.n8n_actions.client import N8NActionClient, N8NActionError

    c = N8NActionClient(key="k", url="https://n8n.test/x", transport=httpx.MockTransport(lambda r: httpx.Response(200, json=answer)))
    with pytest.raises(N8NActionError, match=match):
        await c.dispatch(_envelope())


@pytest.mark.asyncio
async def test_an_http_error_from_the_router_is_not_reported_done():
    from services.n8n_actions.client import N8NActionClient, N8NActionError

    c = N8NActionClient(key="k", url="https://n8n.test/x", transport=httpx.MockTransport(lambda r: httpx.Response(403, text="Authorization data is wrong!")))
    with pytest.raises(N8NActionError, match="HTTP 403"):
        await c.dispatch(_envelope())


@pytest.mark.asyncio
async def test_an_unknown_action_is_refused_before_the_approval_is_spent():
    from services.agent_runtime.governance import (
        APPROVAL_METADATA_KEY,
        RUNTIME_REQUESTED_BY,
        approval_binding,
        approval_marker,
    )
    from services.agent_runtime.tools import ToolRegistry
    from services.devon.approval import ApprovalQueue, ApprovalState
    from services.n8n_actions.agent_adapter import N8NActionCapabilityAdapter
    from services.n8n_actions.client import N8NActionClient

    posts = []
    approvals = ApprovalQueue()
    args = {"action": "shell.run", "summary": "Run something on the host", "payload": {}}
    binding = approval_binding(task_id="T", step_id="S", tool_name="n8n.dispatch", arguments=args)
    record, token = approvals.request(title="x", what_happens=f"y {approval_marker(binding)}", requested_by=RUNTIME_REQUESTED_BY)
    approvals.decide(record.request_id, token, "approve")
    registry = ToolRegistry()
    N8NActionCapabilityAdapter(
        N8NActionClient(key="k", url="https://n8n.test/x", transport=httpx.MockTransport(lambda r: posts.append(r) or httpx.Response(200))),
        approvals,
    ).register(registry)
    result = await registry.execute(
        "n8n.dispatch",
        {**args, APPROVAL_METADATA_KEY: {"request_id": record.request_id, "binding": binding, "task_id": "T", "step_id": "S", "tool_name": "n8n.dispatch"}},
    )
    assert result.ok is False and "not on the Action Router allowlist" in result.error
    assert posts == []
    assert approvals.get(record.request_id).state is ApprovalState.APPROVED


def test_the_client_reads_only_the_devon_key(monkeypatch):
    from services.n8n_actions.client import N8NActionClient

    monkeypatch.delenv("DEVON_N8N_ACTION_KEY", raising=False)
    monkeypatch.setenv("N8N_VPS_KEY", "a-different-key")
    assert N8NActionClient().configured is False
    assert N8NActionClient(key="k", url="http://plain.test").configured is False
