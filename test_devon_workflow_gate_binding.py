"""Fix PR 10 from the DEVON and Hermes audit, H14: the workflow gate.

The approval bound to a step id, and the pending view re-rendered from the
live definition, so a definition swapped while a run waited at the gate
executed under the approval given to the previewed payload. PATCH now
refuses a definition change while a run awaits approval, the run seals a
hash of the rendered pending payload when it pauses, and approval refuses
when the live rendering no longer matches the seal or the hash the
approver names.
"""

from __future__ import annotations

import copy

from sqlalchemy import update

from app.models.workflow import Workflow

RISK_SCAN = {
    "version": 1,
    "trigger": {"type": "manual", "config": {}},
    "steps": [
        {
            "id": "recall",
            "type": "knowledge_search",
            "config": {"query": "{{ input }}", "limit": 3},
        },
        {
            "id": "remember",
            "type": "memory_write",
            "config": {"content": "Noted: {{ input }}", "importance": 6},
        },
    ],
}


async def _paused_run(client, auth_headers):
    created = await client.post(
        "/api/v1/workflows",
        headers=auth_headers,
        json={"name": "Gate binding", "definition": RISK_SCAN},
    )
    assert created.status_code == 201, created.text
    workflow = created.json()
    started = await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs",
        headers=auth_headers,
        json={"input": "EU pricing exposure"},
    )
    assert started.status_code == 201, started.text
    run = started.json()
    assert run["status"] == "awaiting_approval"
    assert run["pending"]["preview"]["content"] == "Noted: EU pricing exposure"
    return workflow, run


async def _swap_definition_behind_the_gate(db_session, workflow_id: str, definition: dict):
    """The bypass: a definition changed by any path other than PATCH."""
    await db_session.execute(
        update(Workflow).where(Workflow.id == workflow_id).values(definition=definition)
    )
    await db_session.commit()


async def test_patch_refuses_a_definition_change_while_a_run_waits(client, auth_headers):
    workflow, run = await _paused_run(client, auth_headers)
    swapped = copy.deepcopy(RISK_SCAN)
    swapped["steps"][1]["config"]["content"] = "Swapped: {{ input }}"
    refused = await client.patch(
        f"/api/v1/workflows/{workflow['id']}",
        headers=auth_headers,
        json={"definition": swapped},
    )
    assert refused.status_code == 409, refused.text
    assert "awaiting approval" in refused.json()["detail"]

    renamed = await client.patch(
        f"/api/v1/workflows/{workflow['id']}",
        headers=auth_headers,
        json={"name": "Gate binding, renamed"},
    )
    assert renamed.status_code == 200, renamed.text

    still = await client.get(
        f"/api/v1/workflows/{workflow['id']}/runs/{run['id']}", headers=auth_headers
    )
    assert still.status_code == 200, still.text
    assert still.json()["pending"]["preview"]["content"] == "Noted: EU pricing exposure"
    assert still.json()["pending"]["payload_sha256"] == run["pending"]["payload_sha256"]


async def test_a_definition_swapped_behind_the_gate_cannot_execute(
    client, auth_headers, db_session
):
    """The audit's first case, through the bypass: the text is swapped, the
    approval names the same step id, and nothing may be written."""
    workflow, run = await _paused_run(client, auth_headers)
    swapped = copy.deepcopy(RISK_SCAN)
    swapped["steps"][1]["config"]["content"] = "Swapped: {{ input }}"
    await _swap_definition_behind_the_gate(db_session, workflow["id"], swapped)

    approved = await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs/{run['id']}/approve",
        headers=auth_headers,
        json={"decisions": {"remember": "approved"}},
    )
    assert approved.status_code == 409, approved.text
    assert "no longer renders what was previewed" in approved.json()["detail"]
    memories = await client.get("/api/v1/memory", headers=auth_headers)
    assert memories.json() == [], "nothing may be written under the old approval"


async def test_a_step_retyped_behind_the_gate_cannot_execute(client, auth_headers, db_session):
    """The audit's second case: the same step id becomes a different effect."""
    workflow, run = await _paused_run(client, auth_headers)
    retyped = copy.deepcopy(RISK_SCAN)
    retyped["steps"][1] = {
        "id": "remember",
        "type": "decision_draft",
        "config": {"question": "Noted: {{ input }}", "recommendation": "{{ input }}"},
    }
    await _swap_definition_behind_the_gate(db_session, workflow["id"], retyped)

    approved = await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs/{run['id']}/approve",
        headers=auth_headers,
        json={"decisions": {"remember": "approved"}},
    )
    assert approved.status_code == 409, approved.text


async def test_the_approver_can_name_the_payload_it_saw(client, auth_headers):
    workflow, run = await _paused_run(client, auth_headers)
    assert len(run["pending"]["payload_sha256"]) == 64
    assert run["pending"]["diverged"] is False
    not_hex = await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs/{run['id']}/approve",
        headers=auth_headers,
        json={"decisions": {"remember": "approved"}, "expected_payload_sha256": "z" * 64},
    )
    assert not_hex.status_code == 422, not_hex.text
    wrong = await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs/{run['id']}/approve",
        headers=auth_headers,
        json={"decisions": {"remember": "approved"}, "expected_payload_sha256": "0" * 64},
    )
    assert wrong.status_code == 409, wrong.text
    assert "not the one this run is waiting on" in wrong.json()["detail"]

    right = await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs/{run['id']}/approve",
        headers=auth_headers,
        json={
            "decisions": {"remember": "approved"},
            "expected_payload_sha256": run["pending"]["payload_sha256"],
        },
    )
    assert right.status_code == 200, right.text
    assert right.json()["status"] == "completed"
    memories = await client.get("/api/v1/memory", headers=auth_headers)
    assert [m["content"] for m in memories.json()] == ["Noted: EU pricing exposure"]



async def test_patch_with_the_unchanged_definition_passes_at_the_gate(client, auth_headers):
    """Codex on the first cut: the guard fired on the presence of a definition,
    so a client resending the current one with a rename was refused. Only a
    changed definition is refused."""
    workflow, run = await _paused_run(client, auth_headers)
    resent = await client.patch(
        f"/api/v1/workflows/{workflow['id']}",
        headers=auth_headers,
        json={"definition": copy.deepcopy(RISK_SCAN), "name": "Gate binding, resent"},
    )
    assert resent.status_code == 200, resent.text
    assert resent.json()["name"] == "Gate binding, resent"

    right = await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs/{run['id']}/approve",
        headers=auth_headers,
        json={
            "decisions": {"remember": "approved"},
            "expected_payload_sha256": run["pending"]["payload_sha256"],
        },
    )
    assert right.status_code == 200, right.text
    assert right.json()["status"] == "completed"


async def test_a_stale_run_can_be_rejected_but_not_approved(client, auth_headers, db_session):
    """Codex on the first cut: a run whose definition changed behind the gate
    refused every decision, and with PATCH, delete and a second run all
    refused while it waited, the owner could not close it without the
    database. Rejection closes it; approval stays refused."""
    workflow, run = await _paused_run(client, auth_headers)
    swapped = copy.deepcopy(RISK_SCAN)
    swapped["steps"][1]["config"]["content"] = "Swapped: {{ input }}"
    await _swap_definition_behind_the_gate(db_session, workflow["id"], swapped)

    approved = await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs/{run['id']}/approve",
        headers=auth_headers,
        json={"decisions": {"remember": "approved"}},
    )
    assert approved.status_code == 409, approved.text
    assert "Reject this run" in approved.json()["detail"]

    rejected = await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs/{run['id']}/approve",
        headers=auth_headers,
        json={"decisions": {"remember": "rejected"}},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "halted"
    memories = await client.get("/api/v1/memory", headers=auth_headers)
    assert memories.json() == [], "a rejection executes nothing"

    # With the stale run closed, the owner can change the definition and run again.
    repaired = await client.patch(
        f"/api/v1/workflows/{workflow['id']}",
        headers=auth_headers,
        json={"definition": swapped},
    )
    assert repaired.status_code == 200, repaired.text
    again = await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs",
        headers=auth_headers,
        json={"input": "EU pricing exposure"},
    )
    assert again.status_code == 201, again.text
    assert again.json()["pending"]["preview"]["content"] == "Swapped: EU pricing exposure"



TWO_GATES = {
    "version": 1,
    "trigger": {"type": "manual", "config": {}},
    "steps": [
        {
            "id": "remember",
            "type": "memory_write",
            "config": {"content": "Noted: {{ input }}", "importance": 6},
        },
        {
            "id": "draft",
            "type": "decision_draft",
            "config": {"question": "Decide: {{ input }}", "recommendation": "{{ input }}"},
        },
    ],
}


async def test_a_later_gate_cannot_be_decided_blind(client, auth_headers, db_session):
    """The critic's attack on the first cut: the seal bound the pending step,
    but a later effect step named in the same call executed unpreviewed,
    with whatever the definition said by then."""
    created = await client.post(
        "/api/v1/workflows",
        headers=auth_headers,
        json={"name": "Two gates", "definition": TWO_GATES},
    )
    assert created.status_code == 201, created.text
    workflow = created.json()
    started = await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs",
        headers=auth_headers,
        json={"input": "EU pricing exposure"},
    )
    assert started.status_code == 201, started.text
    run = started.json()
    assert run["pending"]["step_id"] == "remember"

    swapped = copy.deepcopy(TWO_GATES)
    swapped["steps"][1]["config"]["question"] = "SWAPPED never previewed: {{ input }}"
    await _swap_definition_behind_the_gate(db_session, workflow["id"], swapped)

    blind = await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs/{run['id']}/approve",
        headers=auth_headers,
        json={"decisions": {"remember": "approved", "draft": "approved"}},
    )
    assert blind.status_code == 409, blind.text
    assert "has not been previewed yet" in blind.json()["detail"]
    memories = await client.get("/api/v1/memory", headers=auth_headers)
    assert memories.json() == [], "the refusal executed nothing, not even the pending step"


async def test_the_pending_view_shows_the_seal_and_names_divergence(
    client, auth_headers, db_session
):
    workflow, run = await _paused_run(client, auth_headers)
    sealed = run["pending"]["payload_sha256"]
    swapped = copy.deepcopy(RISK_SCAN)
    swapped["steps"][1]["config"]["content"] = "Swapped: {{ input }}"
    await _swap_definition_behind_the_gate(db_session, workflow["id"], swapped)

    view = await client.get(
        f"/api/v1/workflows/{workflow['id']}/runs/{run['id']}", headers=auth_headers
    )
    assert view.status_code == 200, view.text
    pending = view.json()["pending"]
    assert pending["diverged"] is True
    assert pending["payload_sha256"] == sealed, "the view carries the seal, not the live hash"
    assert pending["preview"]["content"] == "Swapped: EU pricing exposure"


async def test_a_definition_that_stops_holding_behind_the_gate_is_409_not_500(
    client, auth_headers, db_session
):
    workflow, run = await _paused_run(client, auth_headers)
    broken = copy.deepcopy(RISK_SCAN)
    broken["steps"][1]["config"]["memory_type"] = "core"
    await _swap_definition_behind_the_gate(db_session, workflow["id"], broken)

    approved = await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs/{run['id']}/approve",
        headers=auth_headers,
        json={"decisions": {"remember": "approved"}},
    )
    assert approved.status_code == 409, approved.text
    assert "no longer holds" in approved.json()["detail"]
    rejected = await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs/{run['id']}/approve",
        headers=auth_headers,
        json={"decisions": {"remember": "rejected"}},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "halted"
