"""
The learning payload's two unenforced invariants, on a real database.

WHY THIS FILE EXISTS

`test_devon_learning_context_honesty.py` is twelve tests over pure functions and
an in-process store, which is the right lane for the ladder's logic and cannot
reach either of the two claims below. Two adversaries broke both on 2026-09-10
with every guard in the estate green.

CLAIM ONE: the count and the search read the SAME SET.

`count_memories` carries the comment "The scoping clause is copied from
`list_memories` above and must stay identical to it. A count taken over a wider
or narrower scope than the search would make `store.memories.stored` a number
that describes a different set than `store.memories.returned`, which is worse
than no number at all."

That invariant was enforced by nothing. `count_memories` had no test anywhere in
the estate. Dropping the `project_id` clause from the count alone turned an
in-scope empty store into `status: no_match` with a note reading "The learning
store was read and is not empty: 3 memories are stored" about memories belonging
to another project, which is a rung inversion and a cross-scope count in one
line. Every guard stayed green.

CLAIM TWO: the DURABLE path carries the store block.

`app/services/agent_tasks.py` injects `devon_learning` into every planning
context, and `DurableAgentTaskService.create_task` is the only path that creates a
production task. An adversary stripped the `store` block from that payload,
keeping `memories` and `skills`, and the whole fix was reverted on the only path
that matters: twelve honesty tests passed, the agent task API tests passed, the
web checks passed. Key presence was guarded, by
`test_devon_agent_tasks_api.py` and `test_devon_soul_recall_seam.py`. The honesty
of the key's CONTENTS was not.

So both live here, on a database, because both need real rows and a real session.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.services.agent_runtime_persistence import AgentLearningRepository
from services.agent_runtime.learning_context import (
    STATUS_EMPTY,
    STATUS_NO_MATCH,
    STATUS_POPULATED,
    STATUS_UNAVAILABLE,
)

EVERY_STATUS = {STATUS_EMPTY, STATUS_NO_MATCH, STATUS_POPULATED, STATUS_UNAVAILABLE}


async def _project(db, owner_id: str) -> str:
    """A real project row. `project_id` carries a foreign key, so a bare uuid
    fails with agent_runtime_memories_project_id_fkey rather than scoping
    anything, which is how the first version of this file failed."""
    project_id = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO projects (id, owner_id, name, status, settings)"
            " VALUES (CAST(:id AS uuid), CAST(:owner AS uuid), :name, 'active',"
            " '{}'::jsonb)"
        ),
        {"id": project_id, "owner": owner_id, "name": f"scope probe {project_id[:8]}"},
    )
    return project_id


async def _owner(db) -> str:
    owner_id = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO users (id, email, password_hash, is_active, is_verified)"
            " VALUES (CAST(:id AS uuid), :email, :pw, TRUE, TRUE)"
        ),
        {"id": owner_id, "email": f"scope-{owner_id}@example.com", "pw": "x"},
    )
    return owner_id


@pytest.mark.asyncio
async def test_the_count_and_the_search_read_the_same_scope(db_session):
    """The invariant `count_memories`' own docstring states, finally checked.

    Three memories in one project, a goal planned in another. The in-scope store
    is genuinely empty, so the payload must say `empty`. A count that ignores the
    project reports `no_match` instead and tells the planner the store holds rows
    it may not see.
    """
    owner = await _owner(db_session)
    repo = AgentLearningRepository()
    await db_session.flush()
    project_a = await _project(db_session, owner)
    project_b = await _project(db_session, owner)

    for index in range(3):
        await repo.remember(
            db_session,
            owner_id=owner,
            text=f"a lesson about deployments number {index}",
            tags=["deploy"],
            project_id=project_a,
        )
    await db_session.flush()

    in_project_a = await repo.count_memories(
        db_session, owner_id=owner, project_id=project_a
    )
    in_project_b = await repo.count_memories(
        db_session, owner_id=owner, project_id=project_b
    )
    assert in_project_a == 3, "the count does not see its own project's rows"
    assert in_project_b == 0, (
        f"count_memories returned {in_project_b} for a project with no memories. It "
        "is counting outside the scope the search reads, so `stored` and `returned` "
        "describe different sets and the note built from them is not about one store"
    )

    # The count and the search must agree about what is in scope, which is the
    # whole invariant. Asserted as a relationship rather than two numbers, so it
    # holds however the scoping clause is written.
    found_in_b = await repo.search_memories(
        db_session, owner_id=owner, query="deployments", project_id=project_b
    )
    assert len(found_in_b) <= in_project_b, (
        "the search returned more memories than the count says are in scope, so one "
        "of them is reading a wider set than the other"
    )

    found_in_a = await repo.search_memories(
        db_session, owner_id=owner, query="deployments", project_id=project_a
    )
    assert len(found_in_a) <= in_project_a
    assert found_in_a, "the search found nothing in the project that holds the rows"


@pytest.mark.asyncio
async def test_an_empty_scope_reads_as_empty_and_not_as_no_match(db_session):
    """The rung inversion the scope mismatch produced, checked end to end."""
    owner = await _owner(db_session)
    repo = AgentLearningRepository()
    await db_session.flush()
    elsewhere = await _project(db_session, owner)
    here = await _project(db_session, owner)

    await repo.remember(
        db_session,
        owner_id=owner,
        text="a lesson that lives in another project entirely",
        tags=["elsewhere"],
        project_id=elsewhere,
    )
    await db_session.flush()

    payload = await repo.context_for(
        db_session, owner_id=owner, goal="something unrelated", project_id=here
    )
    store = payload["store"]
    assert store["status"] == STATUS_EMPTY, (
        f"an in-scope empty store reported {store['status']}. Reporting no_match "
        "here tells the planner rows exist that it simply did not match, when in "
        "this scope there are none at all"
    )
    assert store["memories"]["stored"] == 0, (
        f"stored is {store['memories']['stored']} for a scope holding no memories, "
        "which is another project's count leaking across the boundary"
    )
    assert "is not empty" not in store["note"], (
        f"the note claims the store is not empty: {store['note']!r}"
    )


@pytest.mark.asyncio
async def test_the_durable_task_context_carries_the_store_block(db_session):
    """The whole fix, on the only path that creates a production task.

    An adversary stripped `store` from this payload and nothing in the estate
    noticed, because the guards asserted the KEY was present rather than that its
    contents said which of the four kinds of nothing this is.
    """
    from app.services.agent_tasks import DurableAgentTaskService

    owner = await _owner(db_session)
    await db_session.flush()

    service = DurableAgentTaskService()
    payload = await service.learning.context_for(
        db_session, owner_id=owner, goal="ship the thing"
    )

    assert "store" in payload, (
        "the durable planning context's devon_learning has no `store` block, so "
        "`memories: []` is back to meaning three different things at once and the "
        "whole point of the payload is gone"
    )
    assert payload["store"]["status"] in EVERY_STATUS, (
        f"the store status is {payload['store']['status']!r}, which is not one of "
        f"the four the ladder defines: {sorted(EVERY_STATUS)}"
    )
    assert payload["store"]["note"], (
        "the store block carries no note, so nothing in the prompt explains which "
        "of the four kinds of nothing this is"
    )
    for half in ("memories", "skills"):
        view = payload["store"][half]
        assert "returned" in view and "stored" in view, (
            f"the {half} view is missing returned or stored, so nothing can tell a "
            "store that holds nothing from a goal that matched nothing"
        )
        assert view["stored"] >= view["returned"], (
            f"the {half} view reports {view['returned']} returned out of "
            f"{view['stored']} stored, which is more returned than exist"
        )
