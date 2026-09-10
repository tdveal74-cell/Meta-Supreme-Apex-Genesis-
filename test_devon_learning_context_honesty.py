"""The devon_learning payload may never conflate its three empty cases.

WHY THIS FILE EXISTS

Every agent task's planning context carries `devon_learning`
(app/services/agent_tasks.py:246) and the planner serialises the whole context
into the prompt (services/agent_runtime/planner.py:176). The payload used to be
two bare lists, so `memories: []` meant "nothing stored", "nothing matched this
goal" or "the read did not happen", and the model was handed no way to tell
which.

CORRECTION, 2026-09-10, and it is the reason to read this paragraph carefully.
This said "the write paths have no production caller either, so in practice the
lists were always empty". That is FALSE and an adversary caught it with one grep.
`POST /api/v1/agent-tasks/learning/memories` calls `remember()`
(app/api/v1/agent_tasks.py:267) and `PUT .../learning/skills/{name}` calls
`upsert_skill()`; both are registered through
`api_router.include_router(agent_tasks.router)` (app/api/v1/router.py:56) and
both are exercised by test_devon_agent_tasks_api.py. They were live, registered,
tested HTTP routes. An operator with a token could fill the store and the planner
would have received real rows.

The true claim is the narrower one, and it is the one worth making: there was no
WEB surface on either route, so nothing a person could open wrote to the store or
read it back. That is what this panel changed. The overstatement did not change a
line of code, and it is corrected here rather than quietly deleted, because
stating a stronger claim than the check supports is the failure the first law in
CLAUDE.md is about.

These are pure functions and an in-process store: no PostgreSQL, no session, no
network. That is deliberate, so the guard can run in the standalone CI lane
alongside test_workflow_engine.py rather than only in the api job.
"""

from __future__ import annotations

import pytest

from services.agent_runtime import (
    AgentRuntime,
    PlanStep,
    StaticPlanner,
    ToolCall,
    ToolRegistry,
    ToolRisk,
    ToolSpec,
)
from services.agent_runtime.learning import InMemoryLearningStore
from services.agent_runtime.learning_context import (
    STATUS_EMPTY,
    STATUS_NO_MATCH,
    STATUS_POPULATED,
    STATUS_UNAVAILABLE,
    learning_payload,
    unavailable_learning,
)


def test_an_empty_store_says_it_was_read_and_is_empty() -> None:
    payload = learning_payload(memories=[], skills=[], memories_stored=0)
    store = payload["store"]
    assert store["status"] == STATUS_EMPTY
    assert store["memories"] == {"returned": 0, "stored": 0, "status": STATUS_EMPTY}
    assert store["errors"] == []
    assert "not a failed read" in store["note"]


def test_a_stored_memory_that_did_not_match_is_not_reported_as_empty() -> None:
    """The case the old shape could not express at all."""
    payload = learning_payload(memories=[], skills=[], memories_stored=12)
    store = payload["store"]
    assert store["status"] == STATUS_NO_MATCH
    assert store["memories"]["stored"] == 12
    assert store["memories"]["returned"] == 0
    assert store["memories"]["status"] == STATUS_NO_MATCH
    assert "12 memories are stored" in store["note"]
    assert store["status"] != STATUS_EMPTY


def test_a_failed_read_never_reads_as_empty() -> None:
    payload = unavailable_learning("the learning tables answered 500")
    store = payload["store"]
    assert store["status"] == STATUS_UNAVAILABLE
    assert store["status"] != STATUS_EMPTY
    assert store["errors"] == ["the learning tables answered 500"]
    assert "not as empty" in store["note"]
    # The lists stay present so no consumer needs a None branch, which is
    # exactly why the status field has to carry the difference.
    assert payload["memories"] == []
    assert payload["skills"] == []


def test_the_three_empty_cases_carry_three_different_notes() -> None:
    """The whole point, asserted directly rather than inferred from branches."""
    notes = {
        learning_payload(memories=[], skills=[], memories_stored=0)["store"]["note"],
        learning_payload(memories=[], skills=[], memories_stored=3)["store"]["note"],
        unavailable_learning("cluster gone")["store"]["note"],
    }
    assert len(notes) == 3


def test_skills_alone_are_enough_to_make_the_store_populated() -> None:
    payload = learning_payload(
        memories=[],
        skills=[{"name": "verify-before-merge"}],
        memories_stored=0,
    )
    store = payload["store"]
    assert store["status"] == STATUS_POPULATED
    assert store["skills"] == {"returned": 1, "stored": 1, "status": STATUS_POPULATED}
    # Skills are listed whole rather than searched, so they can never be in the
    # no_match state; a zero there always means an empty collection.
    assert store["skills"]["status"] != STATUS_NO_MATCH


def test_stored_can_never_undercut_returned() -> None:
    """Two reads can disagree under a concurrent write; the payload may not lie."""
    payload = learning_payload(
        memories=[{"memory_id": "MEM-1"}, {"memory_id": "MEM-2"}],
        skills=[],
        memories_stored=0,
    )
    memories = payload["store"]["memories"]
    assert memories["returned"] == 2
    assert memories["stored"] == 2
    assert memories["status"] == STATUS_POPULATED


def test_the_original_two_keys_survive_for_existing_consumers() -> None:
    payload = learning_payload(
        memories=[{"memory_id": "MEM-1"}],
        skills=[{"name": "audit"}],
        memories_stored=1,
    )
    # app/api/v1/agent_tasks.py returns this inside the task context and
    # test_devon_agent_tasks_api.py:183 reads both lists by name.
    assert payload["memories"] == [{"memory_id": "MEM-1"}]
    assert payload["skills"] == [{"name": "audit"}]


def test_the_in_process_store_reports_no_match_over_a_real_row() -> None:
    """End to end on the path runtime.py:127 actually calls, with no database."""
    store = InMemoryLearningStore()
    store.remember("Reproduce the failure before claiming a fix", tags=["ci"])

    matched = store.context_for("reproduce the failure first")
    assert matched["store"]["status"] == STATUS_POPULATED
    assert matched["store"]["memories"]["returned"] == 1

    missed = store.context_for("order more coffee filters")
    assert missed["memories"] == []
    assert missed["store"]["status"] == STATUS_NO_MATCH
    assert missed["store"]["memories"]["stored"] == 1


def test_the_in_process_store_on_a_cold_start_is_empty_not_unavailable() -> None:
    payload = InMemoryLearningStore().context_for("anything at all")
    assert payload["store"]["status"] == STATUS_EMPTY
    assert payload["store"]["errors"] == []


@pytest.mark.parametrize("reason", ["", "   "])
def test_an_unnamed_outage_still_records_an_error(reason: str) -> None:
    store = unavailable_learning(reason)["store"]
    assert store["status"] == STATUS_UNAVAILABLE
    assert store["errors"] == ["no reason recorded"]


@pytest.mark.asyncio
async def test_a_store_without_context_for_is_named_absent_not_omitted() -> None:
    """runtime.py:127 used to drop the key, so the prompt lost learning in silence."""

    class StoreWithoutContext:
        """A LearningStore that satisfies the protocol but offers no context_for."""

        def remember(self, text, *, tags=(), source="operator"):  # pragma: no cover
            raise NotImplementedError

        def forget(self, memory_id):  # pragma: no cover
            raise NotImplementedError

        def search_memories(self, query, *, limit=5):  # pragma: no cover
            return []

    tools = ToolRegistry()
    tools.register(
        ToolSpec(
            name="repo.inspect",
            description="Inspect repository state",
            risk=ToolRisk.READ,
            handler=lambda args: "clean",
        )
    )
    runtime = AgentRuntime(
        planner=StaticPlanner(
            [
                PlanStep(
                    step_id="STEP-01",
                    title="Inspect",
                    tool_call=ToolCall(name="repo.inspect", arguments={}),
                )
            ]
        ),
        tools=tools,
        learning=StoreWithoutContext(),  # type: ignore[arg-type]
    )

    task = await runtime.create_task("Inspect Meta")

    assert "devon_learning" in task.context
    store = task.context["devon_learning"]["store"]
    assert store["status"] == STATUS_UNAVAILABLE
    assert store["status"] != STATUS_EMPTY
    assert store["errors"] == ["the injected learning store exposes no context_for"]
