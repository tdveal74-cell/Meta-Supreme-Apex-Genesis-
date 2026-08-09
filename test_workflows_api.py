"""
Workflows API integration tests.

Runs against Postgres with the mock provider, so a full Council step executes
offline and deterministically. The through-line of these tests is the
approval gate: a workflow may read and reason on its own, and may not write
memory, open a decision, or prepare an export without the owner saying so.
"""

import pytest

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


READ_ONLY = {
    "version": 1,
    "trigger": {"type": "manual", "config": {}},
    "steps": [
        {
            "id": "recall",
            "type": "knowledge_search",
            "config": {"query": "{{ input }}", "limit": 3},
        }
    ],
}


async def _create(client, headers, *, name="New knowledge risk scan", definition=None):
    response = await client.post(
        "/api/v1/workflows",
        headers=headers,
        json={"name": name, "definition": definition or RISK_SCAN},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _second_user(client):
    email = "other-owner@example.com"
    password = "another-strong-password-123"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Other Owner"},
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Definition lifecycle
# ---------------------------------------------------------------------------


async def test_create_returns_a_draft_with_its_approval_steps_named(
    client, auth_headers
):
    workflow = await _create(client, auth_headers)
    assert workflow["status"] == "draft"
    assert workflow["summary"] == {
        "valid": True,
        "error": None,
        "step_count": 2,
        "approval_steps": ["remember"],
        "trigger_type": "manual",
        "awaiting_dispatcher": False,
    }
    assert workflow["run_count"] == 0
    assert workflow["last_run"] is None


async def test_invalid_definition_is_refused_at_save_time(client, auth_headers):
    response = await client.post(
        "/api/v1/workflows",
        headers=auth_headers,
        json={
            "name": "Broken",
            "definition": {
                "version": 1,
                "trigger": {"type": "manual"},
                "steps": [
                    {
                        "id": "council",
                        "type": "council",
                        "config": {"prompt": "{{ later }}"},
                    },
                    {
                        "id": "later",
                        "type": "knowledge_search",
                        "config": {"query": "x"},
                    },
                ],
            },
        },
    )
    assert response.status_code == 422
    assert "not available yet" in response.text


async def test_a_workflow_with_no_steps_cannot_be_activated(client, auth_headers):
    workflow = await _create(
        client,
        auth_headers,
        name="Empty",
        definition={"version": 1, "trigger": {"type": "manual"}, "steps": []},
    )
    response = await client.patch(
        f"/api/v1/workflows/{workflow['id']}",
        headers=auth_headers,
        json={"status": "active"},
    )
    assert response.status_code == 409
    assert "no steps" in response.json()["detail"]


async def test_activation_succeeds_once_the_definition_holds(client, auth_headers):
    workflow = await _create(client, auth_headers)
    response = await client.patch(
        f"/api/v1/workflows/{workflow['id']}",
        headers=auth_headers,
        json={"status": "active"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "active"


async def test_scheduled_triggers_admit_that_nothing_dispatches_them(
    client, auth_headers
):
    workflow = await _create(
        client,
        auth_headers,
        name="Monday brief",
        definition={
            "version": 1,
            "trigger": {"type": "schedule", "config": {"cadence": "weekly:mon:07:00"}},
            "steps": [
                {"id": "recall", "type": "knowledge_search", "config": {"query": "x"}}
            ],
        },
    )
    assert workflow["summary"]["awaiting_dispatcher"] is True


async def test_workflows_are_scoped_to_their_owner(client, auth_headers):
    workflow = await _create(client, auth_headers)
    other = await _second_user(client)

    assert (
        await client.get(f"/api/v1/workflows/{workflow['id']}", headers=other)
    ).status_code == 404
    assert (await client.get("/api/v1/workflows", headers=other)).json() == []


# ---------------------------------------------------------------------------
# Runs and the approval gate
# ---------------------------------------------------------------------------


async def test_a_run_pauses_at_the_effect_and_shows_what_it_would_write(
    client, auth_headers
):
    workflow = await _create(client, auth_headers)
    response = await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs",
        headers=auth_headers,
        json={"input": "EU pricing exposure"},
    )
    assert response.status_code == 201, response.text
    run = response.json()

    assert run["status"] == "awaiting_approval"
    assert run["pending"]["step_id"] == "remember"
    assert run["pending"]["step_type"] == "memory_write"
    # The gate shows the rendered content, not "Noted: {{ input }}".
    assert run["pending"]["preview"]["content"] == "Noted: EU pricing exposure"
    assert [s["step_id"] for s in run["steps"]] == ["recall"]
    assert run["completed_at"] is None

    memories = await client.get("/api/v1/memory", headers=auth_headers)
    assert memories.json() == [], "nothing may be written before approval"


async def test_approval_completes_the_run_and_writes_the_memory(client, auth_headers):
    workflow = await _create(client, auth_headers)
    run = (
        await client.post(
            f"/api/v1/workflows/{workflow['id']}/runs",
            headers=auth_headers,
            json={"input": "EU pricing exposure"},
        )
    ).json()

    response = await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs/{run['id']}/approve",
        headers=auth_headers,
        json={"decisions": {"remember": "approved"}},
    )
    assert response.status_code == 200, response.text
    approved = response.json()

    assert approved["status"] == "completed"
    assert approved["pending"] is None
    assert approved["completed_at"] is not None
    assert [s["step_id"] for s in approved["steps"]] == ["recall", "remember"]

    # The approval is a signed act: who, and when.
    record = approved["approvals"]["remember"]
    assert record["decision"] == "approved"
    assert record["actor_id"]
    assert record["at"]

    memories = (await client.get("/api/v1/memory", headers=auth_headers)).json()
    assert len(memories) == 1
    assert memories[0]["content"] == "Noted: EU pricing exposure"
    assert memories[0]["metadata"]["workflow_run_id"] == run["id"]


async def test_rejection_halts_the_run_and_writes_nothing(client, auth_headers):
    workflow = await _create(client, auth_headers)
    run = (
        await client.post(
            f"/api/v1/workflows/{workflow['id']}/runs",
            headers=auth_headers,
            json={"input": "EU pricing exposure"},
        )
    ).json()

    halted = (
        await client.post(
            f"/api/v1/workflows/{workflow['id']}/runs/{run['id']}/approve",
            headers=auth_headers,
            json={"decisions": {"remember": "rejected"}},
        )
    ).json()

    assert halted["status"] == "halted"
    assert halted["steps"][-1]["status"] == "rejected"
    assert (await client.get("/api/v1/memory", headers=auth_headers)).json() == []

    # The refusal is kept, not deleted.
    history = (
        await client.get(f"/api/v1/workflows/{workflow['id']}/runs", headers=auth_headers)
    ).json()
    assert [r["status"] for r in history] == ["halted"]


async def test_you_cannot_approve_a_step_the_run_is_not_waiting_on(
    client, auth_headers
):
    workflow = await _create(client, auth_headers)
    run = (
        await client.post(
            f"/api/v1/workflows/{workflow['id']}/runs",
            headers=auth_headers,
            json={"input": "EU pricing exposure"},
        )
    ).json()

    response = await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs/{run['id']}/approve",
        headers=auth_headers,
        json={"decisions": {"recall": "approved"}},
    )
    assert response.status_code == 409
    assert "not an approval step" in response.json()["detail"]


async def test_approving_a_finished_run_is_refused(client, auth_headers):
    workflow = await _create(client, auth_headers)
    run = (
        await client.post(
            f"/api/v1/workflows/{workflow['id']}/runs",
            headers=auth_headers,
            json={"input": "EU pricing exposure"},
        )
    ).json()
    await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs/{run['id']}/approve",
        headers=auth_headers,
        json={"decisions": {"remember": "approved"}},
    )

    again = await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs/{run['id']}/approve",
        headers=auth_headers,
        json={"decisions": {"remember": "approved"}},
    )
    assert again.status_code == 409
    assert "not awaiting approval" in again.json()["detail"]


async def test_only_one_run_may_sit_at_a_gate_at_a_time(client, auth_headers):
    workflow = await _create(client, auth_headers)
    await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs",
        headers=auth_headers,
        json={"input": "first"},
    )
    second = await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs",
        headers=auth_headers,
        json={"input": "second"},
    )
    assert second.status_code == 409
    assert "Decide that one first" in second.json()["detail"]


async def test_archived_workflows_refuse_to_run(client, auth_headers):
    workflow = await _create(client, auth_headers)
    await client.patch(
        f"/api/v1/workflows/{workflow['id']}",
        headers=auth_headers,
        json={"status": "archived"},
    )
    response = await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs",
        headers=auth_headers,
        json={"input": "anything"},
    )
    assert response.status_code == 409
    assert "cannot be run" in response.json()["detail"]


async def test_a_workflow_with_a_pending_gate_cannot_be_deleted(client, auth_headers):
    workflow = await _create(client, auth_headers)
    await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs",
        headers=auth_headers,
        json={"input": "EU pricing exposure"},
    )
    blocked = await client.delete(
        f"/api/v1/workflows/{workflow['id']}", headers=auth_headers
    )
    assert blocked.status_code == 409

    run = (
        await client.get(
            f"/api/v1/workflows/{workflow['id']}/runs", headers=auth_headers
        )
    ).json()[0]
    await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs/{run['id']}/approve",
        headers=auth_headers,
        json={"decisions": {"remember": "rejected"}},
    )
    assert (
        await client.delete(f"/api/v1/workflows/{workflow['id']}", headers=auth_headers)
    ).status_code == 204


async def test_runs_are_scoped_to_the_workflow_owner(client, auth_headers):
    workflow = await _create(client, auth_headers)
    run = (
        await client.post(
            f"/api/v1/workflows/{workflow['id']}/runs",
            headers=auth_headers,
            json={"input": "EU pricing exposure"},
        )
    ).json()
    other = await _second_user(client)

    assert (
        await client.get(
            f"/api/v1/workflows/{workflow['id']}/runs/{run['id']}", headers=other
        )
    ).status_code == 404
    assert (
        await client.post(
            f"/api/v1/workflows/{workflow['id']}/runs/{run['id']}/approve",
            headers=other,
            json={"decisions": {"remember": "approved"}},
        )
    ).status_code == 404


# ---------------------------------------------------------------------------
# Council step, token accounting, catalog
# ---------------------------------------------------------------------------


async def test_a_council_step_runs_unattended_and_is_metered(client, auth_headers):
    workflow = await _create(
        client,
        auth_headers,
        name="Council only",
        definition={
            "version": 1,
            "trigger": {"type": "manual"},
            "steps": [
                {
                    "id": "assess",
                    "type": "council",
                    "config": {"prompt": "Assess the risk in: {{ input }}"},
                }
            ],
        },
    )
    run = (
        await client.post(
            f"/api/v1/workflows/{workflow['id']}/runs",
            headers=auth_headers,
            json={"input": "a competitor moved to usage-based pricing"},
        )
    ).json()

    assert run["status"] == "completed"
    step = run["steps"][0]
    assert step["status"] == "completed"
    assert step["summary"]
    assert step["data"]["agents_consulted"]
    assert run["token_usage"]["total_tokens"] > 0
    assert run["latency_ms"] >= 0


async def test_list_view_carries_the_last_run(client, auth_headers):
    workflow = await _create(client, auth_headers)
    await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs",
        headers=auth_headers,
        json={"input": "EU pricing exposure"},
    )
    listed = (await client.get("/api/v1/workflows", headers=auth_headers)).json()
    assert len(listed) == 1
    assert listed[0]["run_count"] == 1
    assert listed[0]["last_run"]["status"] == "awaiting_approval"
    assert listed[0]["last_run"]["pending_step_id"] == "remember"


async def test_step_catalog_is_the_single_source_of_approval_semantics(
    client, auth_headers
):
    catalog = (
        await client.get("/api/v1/workflows/step-types", headers=auth_headers)
    ).json()
    by_type = {s["type"]: s for s in catalog["step_types"]}

    assert by_type["knowledge_search"]["requires_approval"] is False
    assert by_type["council"]["requires_approval"] is False
    assert by_type["memory_write"]["requires_approval"] is True
    assert by_type["decision_draft"]["requires_approval"] is True
    assert by_type["export"]["requires_approval"] is True
    assert catalog["approval_required"] is True
    # Schedule and event triggers are storable but nothing fires them yet.
    assert catalog["dispatchable_triggers"] == ["manual"]


# ---------------------------------------------------------------------------
# Idempotency and pagination
# ---------------------------------------------------------------------------


async def test_a_retried_run_with_the_same_key_returns_the_original(
    client, auth_headers
):
    workflow = await _create(
        client, auth_headers, name="Read only", definition=READ_ONLY
    )
    headers = {**auth_headers, "Idempotency-Key": "run-once-please"}

    first = await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs",
        headers=headers,
        json={"input": "EU pricing exposure"},
    )
    assert first.status_code == 201

    second = await client.post(
        f"/api/v1/workflows/{workflow['id']}/runs",
        headers=headers,
        json={"input": "EU pricing exposure"},
    )
    assert second.status_code == 200, "a replay is not a creation"
    assert second.json()["id"] == first.json()["id"]

    history = (
        await client.get(
            f"/api/v1/workflows/{workflow['id']}/runs", headers=auth_headers
        )
    ).json()
    assert len(history) == 1


async def test_a_different_key_starts_a_genuinely_new_run(client, auth_headers):
    workflow = await _create(
        client, auth_headers, name="Read only", definition=READ_ONLY
    )
    for key in ("first-attempt", "second-attempt"):
        response = await client.post(
            f"/api/v1/workflows/{workflow['id']}/runs",
            headers={**auth_headers, "Idempotency-Key": key},
            json={"input": "EU pricing exposure"},
        )
        assert response.status_code == 201

    history = (
        await client.get(
            f"/api/v1/workflows/{workflow['id']}/runs", headers=auth_headers
        )
    ).json()
    assert len(history) == 2


async def test_keys_do_not_leak_between_workflows(client, auth_headers):
    """The key is unique per workflow, not globally."""
    a = await _create(client, auth_headers, name="A", definition=READ_ONLY)
    b = await _create(client, auth_headers, name="B", definition=READ_ONLY)
    headers = {**auth_headers, "Idempotency-Key": "shared"}

    assert (
        await client.post(
            f"/api/v1/workflows/{a['id']}/runs", headers=headers, json={"input": "x"}
        )
    ).status_code == 201
    assert (
        await client.post(
            f"/api/v1/workflows/{b['id']}/runs", headers=headers, json={"input": "x"}
        )
    ).status_code == 201


async def test_without_a_key_a_read_only_workflow_really_does_run_twice(
    client, auth_headers
):
    """Documents the behaviour the header exists to prevent.

    The awaiting-gate guard cannot catch this case: the first run never
    stopped, so there is nothing for the second to collide with.
    """
    workflow = await _create(
        client, auth_headers, name="Read only", definition=READ_ONLY
    )
    for _ in range(2):
        response = await client.post(
            f"/api/v1/workflows/{workflow['id']}/runs",
            headers=auth_headers,
            json={"input": "EU pricing exposure"},
        )
        assert response.status_code == 201

    history = (
        await client.get(
            f"/api/v1/workflows/{workflow['id']}/runs", headers=auth_headers
        )
    ).json()
    assert len(history) == 2


async def test_run_history_pages_without_dropping_or_repeating_rows(
    client, auth_headers
):
    workflow = await _create(
        client, auth_headers, name="Read only", definition=READ_ONLY
    )
    for i in range(5):
        await client.post(
            f"/api/v1/workflows/{workflow['id']}/runs",
            headers={**auth_headers, "Idempotency-Key": f"run-{i}"},
            json={"input": f"input {i}"},
        )

    page_one = (
        await client.get(
            f"/api/v1/workflows/{workflow['id']}/runs?limit=2&offset=0",
            headers=auth_headers,
        )
    ).json()
    page_two = (
        await client.get(
            f"/api/v1/workflows/{workflow['id']}/runs?limit=2&offset=2",
            headers=auth_headers,
        )
    ).json()

    assert len(page_one) == 2 and len(page_two) == 2
    ids = [r["id"] for r in page_one + page_two]
    assert len(set(ids)) == 4, "pages overlapped — the sort is not stable"


async def test_workflow_list_pages(client, auth_headers):
    for i in range(3):
        await _create(client, auth_headers, name=f"Workflow {i}")
    first = (
        await client.get("/api/v1/workflows?limit=2&offset=0", headers=auth_headers)
    ).json()
    second = (
        await client.get("/api/v1/workflows?limit=2&offset=2", headers=auth_headers)
    ).json()
    assert len(first) == 2 and len(second) == 1
    assert not {w["id"] for w in first} & {w["id"] for w in second}


@pytest.mark.parametrize("path", ["", "/step-types"])
async def test_workflow_endpoints_require_authentication(client, path):
    assert (await client.get(f"/api/v1/workflows{path}")).status_code == 401
