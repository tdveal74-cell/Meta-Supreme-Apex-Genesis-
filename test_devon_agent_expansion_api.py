"""End-to-end coverage for Hermes expansion HTTP surface."""

import pytest


@pytest.mark.asyncio
async def test_schedule_create_due_and_materialize(client, auth_headers):
    created = await client.post(
        "/api/v1/agent-expansion/schedules",
        headers=auth_headers,
        json={"goal": "Run the nightly check", "delay_seconds": 0},
    )
    assert created.status_code == 201, created.text
    schedule_id = created.json()["schedule_id"]
    assert schedule_id.startswith("SCH-")

    due = await client.get(
        "/api/v1/agent-expansion/schedules/due", headers=auth_headers
    )
    assert due.status_code == 200, due.text
    assert any(item["schedule_id"] == schedule_id for item in due.json())

    materialize = await client.post(
        "/api/v1/agent-expansion/schedules/materialize",
        headers=auth_headers,
    )
    assert materialize.status_code == 200, materialize.text
    body = materialize.json()
    assert len(body) >= 1
    match = next(item for item in body if item["schedule"]["schedule_id"] == schedule_id)
    assert match["schedule"]["task_id"]
    assert match["task"]["task_id"] == match["schedule"]["task_id"]
    assert match["task"]["context"]["schedule_id"] == schedule_id

    # Second materialize must not create duplicate tasks for the same schedule.
    again = await client.post(
        "/api/v1/agent-expansion/schedules/materialize",
        headers=auth_headers,
    )
    assert again.status_code == 200
    assert all(
        item["schedule"]["schedule_id"] != schedule_id for item in again.json()
    )


@pytest.mark.asyncio
async def test_skill_propose_approve_and_promote(client, auth_headers):
    proposed = await client.post(
        "/api/v1/agent-expansion/skill-proposals",
        headers=auth_headers,
        json={
            "task_id": "TASK-DEMO",
            "goal": "File an episode idea",
            "observations": ["Tagged Podcast", "Filed to Idea stage"],
        },
    )
    assert proposed.status_code == 201, proposed.text
    proposal_id = proposed.json()["proposal_id"]
    assert proposed.json()["state"] == "proposed"

    decided = await client.post(
        f"/api/v1/agent-expansion/skill-proposals/{proposal_id}/decide",
        headers=auth_headers,
        json={"approve": True, "promote": True},
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["proposal"]["state"] == "approved"
    assert decided.json()["skill"] is not None
    assert decided.json()["skill"]["name"]

    skills = await client.get(
        "/api/v1/agent-tasks/learning/skills", headers=auth_headers
    )
    assert skills.status_code == 200
    assert any(
        item["name"] == decided.json()["skill"]["name"] for item in skills.json()
    )


@pytest.mark.asyncio
async def test_skill_reject_does_not_promote(client, auth_headers):
    proposed = await client.post(
        "/api/v1/agent-expansion/skill-proposals",
        headers=auth_headers,
        json={
            "task_id": "TASK-REJECT",
            "goal": "Bad pattern",
            "observations": [],
        },
    )
    proposal_id = proposed.json()["proposal_id"]
    decided = await client.post(
        f"/api/v1/agent-expansion/skill-proposals/{proposal_id}/decide",
        headers=auth_headers,
        json={"approve": False, "promote": True},
    )
    assert decided.status_code == 200
    assert decided.json()["proposal"]["state"] == "rejected"
    assert decided.json()["skill"] is None


@pytest.mark.asyncio
async def test_subagent_spawn_links_parent(client, auth_headers):
    parent = await client.post(
        "/api/v1/agent-tasks",
        headers=auth_headers,
        json={
            "goal": "Parent research",
            "context": {"area": "Systems"},
            "steps": [
                {
                    "title": "Inspect",
                    "tool": "operator.read",
                    "arguments": {"command": "pwd"},
                }
            ],
        },
    )
    assert parent.status_code == 201, parent.text
    parent_id = parent.json()["task_id"]

    child = await client.post(
        "/api/v1/agent-expansion/subagents",
        headers=auth_headers,
        json={
            "parent_task_id": parent_id,
            "goal": "Child dig into allowlist",
            "max_steps": 4,
            "inherit_context_keys": ["area"],
        },
    )
    assert child.status_code == 201, child.text
    body = child.json()
    assert body["context"]["parent_task_id"] == parent_id
    assert body["context"]["subagent_id"].startswith("SUB-")
    assert body["context"]["area"] == "Systems"
    assert body["goal"] == "Child dig into allowlist"
