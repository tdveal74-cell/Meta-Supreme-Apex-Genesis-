"""Fix PR 3 from the DEVON and Hermes audit: H6 and GG-1.

The three runtime expansion tools wrote to process-local stores, so an
approved effect with a succeeded receipt existed nowhere the operator looks,
and the handlers never spent the approval, so a stale snapshot replayed them.
Each test runs the audit's own reproduction: a governed task step, the human
ruling, the effect run, then the HTTP surface that has to show the result.
"""

from __future__ import annotations

from app.api.v1.devon import _queue
from services.devon.approval import ApprovalState


async def _run_governed(client, auth_headers, *, goal: str, step: dict):
    created = await client.post(
        "/api/v1/agent-tasks", headers=auth_headers, json={"goal": goal, "steps": [step]}
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["task_id"]

    waiting = await client.post(
        f"/api/v1/agent-tasks/{task_id}/run",
        headers={**auth_headers, "Idempotency-Key": f"approve-{task_id}"},
        json={"max_steps": 5},
    )
    assert waiting.status_code == 200, waiting.text
    token = waiting.json()["approval_token"]
    request_id = waiting.json()["task"]["plan"]["steps"][0]["approval_request_id"]

    decided = await client.post(
        "/api/v1/devon/approvals/decide",
        headers=auth_headers,
        json={"request_id": request_id, "token": token, "decision": "approve"},
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["approved"] is True

    completed = await client.post(
        f"/api/v1/agent-tasks/{task_id}/run",
        headers={**auth_headers, "Idempotency-Key": f"effect-{task_id}"},
        json={"max_steps": 5},
    )
    assert completed.status_code == 200, completed.text
    body = completed.json()
    assert body["task"]["state"] == "completed", body
    return task_id, request_id, body


async def test_runtime_schedule_goal_lands_on_the_durable_schedule_table(
    client, auth_headers
):
    goal = "Run the nightly check from the runtime"
    task_id, request_id, _ = await _run_governed(
        client,
        auth_headers,
        goal="Schedule the nightly check",
        step={
            "title": "Schedule the nightly check",
            "tool": "runtime.schedule_goal",
            "arguments": {"goal": goal, "delay_seconds": 0},
        },
    )
    due = await client.get("/api/v1/agent-expansion/schedules/due", headers=auth_headers)
    assert due.status_code == 200, due.text
    match = [item for item in due.json() if item["goal"] == goal]
    assert len(match) == 1, due.json()
    assert match[0]["schedule_id"].startswith("SCH-")
    assert _queue.get(request_id).state is ApprovalState.CONSUMED

    materialized = await client.post(
        "/api/v1/agent-expansion/schedules/materialize", headers=auth_headers
    )
    assert materialized.status_code == 200, materialized.text
    assert any(
        item["schedule"]["schedule_id"] == match[0]["schedule_id"]
        for item in materialized.json()
    )


async def test_runtime_propose_skill_lands_where_the_human_decides(client, auth_headers):
    goal = "File a receipt from the runtime"
    task_id, request_id, _ = await _run_governed(
        client,
        auth_headers,
        goal="Draft a skill from the last task",
        step={
            "title": "Draft the receipt skill",
            "tool": "runtime.propose_skill",
            "arguments": {
                "task_id": "TASK-SOURCE",
                "goal": goal,
                "observations": ["Asked for the area", "Built the filename"],
            },
        },
    )
    listed = await client.get(
        "/api/v1/agent-expansion/skill-proposals?state=proposed", headers=auth_headers
    )
    assert listed.status_code == 200, listed.text
    match = [item for item in listed.json() if item["source_task_id"] == "TASK-SOURCE"]
    assert len(match) == 1, listed.json()
    assert _queue.get(request_id).state is ApprovalState.CONSUMED

    decided = await client.post(
        f"/api/v1/agent-expansion/skill-proposals/{match[0]['proposal_id']}/decide",
        headers=auth_headers,
        json={"approve": True, "promote": False},
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["proposal"]["state"] == "approved"


async def test_runtime_spawn_subagent_links_a_durable_child(client, auth_headers):
    goal = "Child research from the runtime"
    task_id, request_id, _ = await _run_governed(
        client,
        auth_headers,
        goal="Spawn a research child",
        step={
            "title": "Spawn the research child",
            "tool": "runtime.spawn_subagent",
            "arguments": {"goal": goal, "max_steps": 3},
        },
    )
    assert _queue.get(request_id).state is ApprovalState.CONSUMED

    children = await client.get(
        f"/api/v1/agent-expansion/subagents?parent_task_id={task_id}",
        headers=auth_headers,
    )
    assert children.status_code == 200, children.text
    match = [item for item in children.json() if item["goal"] == goal]
    assert len(match) == 1, children.json()
    assert match[0]["context"]["parent_task_id"] == task_id
    assert match[0]["context"]["max_steps"] == 3
    assert match[0]["state"] != "completed"
