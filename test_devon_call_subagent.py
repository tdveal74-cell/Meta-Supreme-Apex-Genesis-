"""runtime.call_subagent: a child runs now and its answer returns to the parent.

Ruled by Tee 2026-10-24 ("He needs to be able to call subagents too", then
"Both"). The child is planned and run inside the parent's step, takes its read
steps itself, and stops before any step that would raise a card, so no write
happens from inside another task's step and no single-use token lands in the
parent's observation log.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.api.v1.devon import _queue
from services.devon.approval import ApprovalState


class _PlanProvider:
    """Answers the child's planning call with a fixed plan."""

    name = "fake-planner"
    default_model = "fake"

    def __init__(self, steps):
        self.steps = steps

    async def complete(self, request):
        return SimpleNamespace(text=json.dumps({"steps": self.steps, "completion_criteria": []}))


def _plan(monkeypatch, steps):
    import app.services.agent_tasks as agent_tasks

    monkeypatch.setattr(agent_tasks, "get_provider", lambda: _PlanProvider(steps))


async def _call(client, auth_headers, goal="Find out what the child knows"):
    created = await client.post(
        "/api/v1/agent-tasks",
        headers=auth_headers,
        json={
            "goal": "Parent that delegates",
            "steps": [
                {
                    "title": "Delegate",
                    "tool": "runtime.call_subagent",
                    "arguments": {"goal": goal, "max_steps": 4},
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["task_id"]
    waiting = await client.post(f"/api/v1/agent-tasks/{task_id}/run", headers=auth_headers, json={})
    assert waiting.json()["task"]["state"] == "waiting_approval"
    step = waiting.json()["task"]["plan"]["steps"][0]
    decided = await client.post(
        "/api/v1/devon/approvals/decide",
        headers=auth_headers,
        json={"request_id": step["approval_request_id"], "token": waiting.json()["approval_token"], "decision": "approve"},
    )
    assert decided.json()["approved"] is True
    resumed = await client.post(f"/api/v1/agent-tasks/{task_id}/run", headers=auth_headers, json={})
    assert resumed.status_code == 200, resumed.text
    return task_id, step["approval_request_id"], resumed.json()


@pytest.mark.asyncio
async def test_a_child_with_only_read_steps_runs_and_its_answer_returns(client, auth_headers, monkeypatch):
    _plan(
        monkeypatch,
        [
            {
                "title": "Ask the council",
                "tool": "council.consult",
                "arguments": {"question": "Is the Inbox the right home for a weekly review idea?"},
                "reason": "context",
                "expected_outcome": "an answer",
            }
        ],
    )
    task_id, request_id, body = await _call(client, auth_headers)
    assert _queue.get(request_id).state is ApprovalState.CONSUMED
    assert body["task"]["state"] == "completed", body
    observation = body["task"]["observations"][0]
    assert observation["ok"] is True
    answer = json.loads(observation["output"])
    assert answer["state"] == "completed"
    assert answer["parent_task_id"] == task_id
    assert answer["answers"] and answer["answers"][0]["ok"] is True

    children = await client.get(f"/api/v1/agent-expansion/subagents?parent_task_id={task_id}", headers=auth_headers)
    assert [c["task_id"] for c in children.json()] == [answer["child_task_id"]]


@pytest.mark.asyncio
async def test_a_child_stops_before_a_write_and_raises_no_card(client, auth_headers, monkeypatch):
    _plan(
        monkeypatch,
        [
            {
                "title": "File the idea",
                "tool": "notion.create_page",
                "arguments": {"database": "inbox", "title": "Weekly review"},
                "reason": "capture",
                "expected_outcome": "a page",
            }
        ],
    )
    pending_before = {r.request_id for r in _queue.pending()}
    task_id, _, body = await _call(client, auth_headers)
    observation = body["task"]["observations"][0]
    assert observation["ok"] is False
    child_id = json.loads(observation["output"])["child_task_id"]
    assert f"POST /api/v1/agent-tasks/{child_id}/run" in observation["error"]
    assert "approval_token" not in json.dumps(body["task"])
    # No card was raised from inside the parent's step.
    raised = {r.request_id for r in _queue.pending()} - pending_before
    assert raised == set(), raised

    # Running the child directly raises its card the normal way, token included.
    direct = await client.post(f"/api/v1/agent-tasks/{child_id}/run", headers=auth_headers, json={})
    assert direct.json()["task"]["state"] == "waiting_approval"
    assert direct.json()["approval_token"]


@pytest.mark.asyncio
async def test_a_chain_deeper_than_the_limit_is_refused(monkeypatch):
    import app.services.agent_tasks as agent_tasks

    chain = {
        "TASK-C": {"parent_task_id": "TASK-B"},
        "TASK-B": {"parent_task_id": "TASK-A"},
        "TASK-A": {},
    }

    async def get_task(_session, *, owner_id, task_id):
        ctx = chain.get(task_id)
        return None if ctx is None else SimpleNamespace(context=ctx)

    spawned = []

    async def write_subagent(**kwargs):
        spawned.append(kwargs)
        return {"task_id": "never"}

    monkeypatch.setattr(agent_tasks.agent_tasks_service, "get_task", get_task)
    monkeypatch.setattr(agent_tasks, "_write_subagent", write_subagent)
    with pytest.raises(ValueError, match="3 deep; the limit is 2"):
        await agent_tasks._call_subagent(
            owner_id="u", parent_task_id="TASK-C", goal="g", max_steps=1,
            inherit_context_keys=[], max_depth=2,
        )
    assert spawned == []


@pytest.mark.asyncio
async def test_without_a_runner_the_tool_refuses_and_keeps_the_approval():
    from services.agent_runtime.expansion_tools import CALL_TOOL, ExpansionToolAdapter
    from services.agent_runtime.governance import (
        APPROVAL_METADATA_KEY,
        RUNTIME_REQUESTED_BY,
        approval_binding,
        approval_marker,
    )
    from services.agent_runtime.tools import ToolRegistry
    from services.devon.approval import ApprovalQueue

    approvals = ApprovalQueue()
    args = {"goal": "Look something up"}
    binding = approval_binding(task_id="T", step_id="S", tool_name=CALL_TOOL, arguments=args)
    record, token = approvals.request(title="x", what_happens=f"y {approval_marker(binding)}", requested_by=RUNTIME_REQUESTED_BY)
    approvals.decide(record.request_id, token, "approve")
    registry = ToolRegistry()
    ExpansionToolAdapter(approvals=approvals).register(registry)
    result = await registry.execute(
        CALL_TOOL,
        {**args, APPROVAL_METADATA_KEY: {"request_id": record.request_id, "binding": binding, "task_id": "T", "step_id": "S", "tool_name": CALL_TOOL}},
    )
    assert result.ok is False and "approval was not spent" in result.error
    assert approvals.get(record.request_id).state is ApprovalState.APPROVED


@pytest.mark.asyncio
async def test_a_child_cannot_inherit_its_parent_link_and_skip_a_depth_level(client, auth_headers):
    """The critic's finding: inherit_context_keys=["parent_task_id"] rewrote the link.

    Driven through the same spawn_subagent_task that runtime.call_subagent uses,
    at depth one, where the parent's context carries a parent_task_id to steal.
    """
    root = await client.post("/api/v1/agent-tasks", headers=auth_headers,
                             json={"goal": "Root", "steps": [{"title": "Ask", "tool": "council.consult", "arguments": {"question": "Anything?"}}]})
    root_id = root.json()["task_id"]
    child = await client.post("/api/v1/agent-expansion/subagents", headers=auth_headers,
                              json={"parent_task_id": root_id, "goal": "Child", "max_steps": 3})
    child_id = child.json()["task_id"]
    grandchild = await client.post("/api/v1/agent-expansion/subagents", headers=auth_headers,
                                   json={"parent_task_id": child_id, "goal": "Grandchild that tries to climb", "max_steps": 2,
                                         "inherit_context_keys": ["parent_task_id", "subagent_id", "max_steps", "owner_id"]})
    assert grandchild.status_code == 201, grandchild.text
    ctx = grandchild.json()["context"]
    assert ctx["parent_task_id"] == child_id, ctx
    assert ctx["max_steps"] == 2
    assert ctx["subagent_id"] != child.json()["context"]["subagent_id"]
