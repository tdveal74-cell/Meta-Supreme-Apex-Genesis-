"""An approval is permission to do one thing once, not standing permission.

Before this, `ApprovalState` ended at approved, refused and expired. The
capability boundary satisfied itself that a record was APPROVED and bound to the
exact arguments in hand, and both facts stayed true forever. Nothing anywhere
marked the approval spent. Anyone still holding the runtime metadata could
replay the same governed effect indefinitely, and every replay would pass every
check honestly, because every check was still true.

That predates presence authority and survived it: presence changed who may
approve and how fast, not how long an approval lasts once given.

The tests that matter here are the two that constrain WHEN the spend happens.
Consuming too early turns a refused call into a burnt approval and hands anyone
who can reach the boundary a way to disarm queued work. Consuming too late
leaves a live approval sitting behind a half-finished effect. It goes last among
the checks and before the handler, and both halves are pinned below.
"""

from __future__ import annotations

import pytest

from services.agent_runtime.governance import (
    APPROVAL_METADATA_KEY,
    RUNTIME_REQUESTED_BY,
    approval_binding,
    approval_marker,
    require_approved_runtime_binding,
)
from services.devon.approval import (
    ApprovalQueue,
    ApprovalRequest,
    ApprovalState,
    InMemoryApprovalStore,
    RefusalReason,
)

TASK = "TASK-CONSUME"
STEP = "STEP-01"
TOOL = "github.write_file"
ARGS = {
    "repository": "tdveal74-cell/Meta-Supreme-Apex-Genesis-",
    "path": "README.md",
    "content": "x",
    "message": "m",
    "branch": "main",
}


def approved(queue: ApprovalQueue, *, arguments=None):
    """A record in exactly the state the capability boundary expects to find."""
    args = ARGS if arguments is None else arguments
    binding = approval_binding(
        task_id=TASK, step_id=STEP, tool_name=TOOL, arguments=args
    )
    record, token = queue.request(
        title="Write a file",
        what_happens=f"Write {args.get('path')}. {approval_marker(binding)}",
        requested_by=RUNTIME_REQUESTED_BY,
    )
    assert queue.decide(record.request_id, token, "approve").approved is True
    return record.request_id, binding


def metadata(request_id: str, binding: str) -> dict:
    return {
        "request_id": request_id,
        "binding": binding,
        "task_id": TASK,
        "step_id": STEP,
        "tool_name": TOOL,
    }


# ---------------------------------------------------------------------------
# The replay this closes
# ---------------------------------------------------------------------------


def test_the_same_approval_cannot_authorise_the_same_effect_twice() -> None:
    queue = ApprovalQueue(InMemoryApprovalStore())
    request_id, binding = approved(queue)
    meta = metadata(request_id, binding)

    # First crossing: everything is in order and the effect is authorised.
    got_id, got_binding = require_approved_runtime_binding(
        queue, meta, tool_name=TOOL, arguments=ARGS
    )
    assert got_id == request_id
    assert got_binding == binding

    # Second crossing with byte-identical metadata. Before this change it
    # succeeded, because APPROVED and bound-to-these-arguments were both still
    # true and nothing recorded that the effect had already happened.
    # The refusal arrives from the state check a few lines above the consume,
    # which now finds CONSUMED rather than APPROVED. That is the ordinary path
    # and it is the consume on the first crossing that makes it true. The
    # consume's own refusal is the narrower one: it catches a second caller that
    # read APPROVED before the first had finished spending it, which is the race
    # the compare-and-set test below pins.
    with pytest.raises(ValueError) as caught:
        require_approved_runtime_binding(queue, meta, tool_name=TOOL, arguments=ARGS)
    assert "consumed" in str(caught.value)
    assert "not approved" in str(caught.value)


def test_the_record_ends_consumed_rather_than_approved() -> None:
    queue = ApprovalQueue(InMemoryApprovalStore())
    request_id, binding = approved(queue)

    require_approved_runtime_binding(
        queue, metadata(request_id, binding), tool_name=TOOL, arguments=ARGS
    )

    spent = queue.get(request_id)
    assert spent is not None
    assert spent.state is ApprovalState.CONSUMED


def test_the_human_ruling_survives_being_spent() -> None:
    """Consuming records that an effect ran; it must not erase who allowed it.

    `decided_at` and `decided_by` are the audit trail of the ruling itself. If
    consuming overwrote them with the moment the effect ran, the queue would
    lose the only record of when Tee actually said yes.
    """
    queue = ApprovalQueue(InMemoryApprovalStore())
    request_id, binding = approved(queue)
    before = queue.get(request_id)
    assert before is not None

    require_approved_runtime_binding(
        queue, metadata(request_id, binding), tool_name=TOOL, arguments=ARGS
    )

    after = queue.get(request_id)
    assert after is not None
    assert after.decided_at == before.decided_at
    assert after.decided_by == before.decided_by


# ---------------------------------------------------------------------------
# When the spend happens, in both directions
# ---------------------------------------------------------------------------


def test_a_call_refused_for_any_other_reason_leaves_the_approval_spendable() -> None:
    """The spend goes last, and this is why.

    If it went first, anyone able to reach the capability boundary could burn a
    queued approval by presenting deliberately wrong arguments: the consume
    would land, the binding check would then refuse, and the honest effect Tee
    approved would be dead with no way to run it. Refusal must cost the caller
    nothing that belongs to the approval.
    """
    queue = ApprovalQueue(InMemoryApprovalStore())
    request_id, binding = approved(queue)

    tampered = dict(ARGS)
    tampered["path"] = "somewhere-else.md"
    with pytest.raises(ValueError) as caught:
        require_approved_runtime_binding(
            queue, metadata(request_id, binding), tool_name=TOOL, arguments=tampered
        )
    assert "does not match" in str(caught.value)

    # Still spendable, and the honest call still works.
    assert queue.get(request_id).state is ApprovalState.APPROVED
    got_id, _ = require_approved_runtime_binding(
        queue, metadata(request_id, binding), tool_name=TOOL, arguments=ARGS
    )
    assert got_id == request_id


def test_a_wrong_tool_name_does_not_burn_the_approval() -> None:
    queue = ApprovalQueue(InMemoryApprovalStore())
    request_id, binding = approved(queue)

    meta = metadata(request_id, binding)
    meta["tool_name"] = "operator.command"
    with pytest.raises(ValueError):
        require_approved_runtime_binding(
            queue, meta, tool_name="operator.command", arguments=ARGS
        )

    assert queue.get(request_id).state is ApprovalState.APPROVED


# ---------------------------------------------------------------------------
# The queue method on its own
# ---------------------------------------------------------------------------


def test_consume_is_single_use_and_says_why() -> None:
    queue = ApprovalQueue(InMemoryApprovalStore())
    request_id, _binding = approved(queue)

    first = queue.consume(request_id)
    assert first.ok is True
    assert first.state is ApprovalState.CONSUMED

    second = queue.consume(request_id)
    assert second.ok is False
    assert second.reason is RefusalReason.ALREADY_CONSUMED


def test_consume_refuses_a_record_that_was_never_approved() -> None:
    queue = ApprovalQueue(InMemoryApprovalStore())
    record, _token = queue.request(
        title="Pending", what_happens="nothing yet", requested_by=RUNTIME_REQUESTED_BY
    )

    result = queue.consume(record.request_id)
    assert result.ok is False
    assert result.reason is RefusalReason.ALREADY_DECIDED
    assert "not approved" in result.message


def test_consume_refuses_a_refused_record() -> None:
    queue = ApprovalQueue(InMemoryApprovalStore())
    record, token = queue.request(
        title="Refused", what_happens="denied", requested_by=RUNTIME_REQUESTED_BY
    )
    queue.decide(record.request_id, token, "refuse")

    assert queue.consume(record.request_id).ok is False


def test_consume_names_a_missing_request_rather_than_failing_open() -> None:
    queue = ApprovalQueue(InMemoryApprovalStore())
    assert queue.consume("REQ-NOT-REAL").reason is RefusalReason.UNKNOWN_ID
    assert queue.consume("").reason is RefusalReason.NO_ID
    assert queue.consume(None).reason is RefusalReason.NO_ID


# ---------------------------------------------------------------------------
# The store transition underneath it
# ---------------------------------------------------------------------------


def test_only_one_of_two_racing_workers_spends_the_approval() -> None:
    """Compare-and-set, the same shape `decide` already uses for the token.

    Two workers holding the same approval metadata both read APPROVED and both
    attempt the transition. Exactly one row moves; the loser is told the effect
    is already running rather than being allowed to run it again.
    """
    store = InMemoryApprovalStore()
    queue = ApprovalQueue(store)
    request_id, _binding = approved(queue)

    record = store.get(request_id)
    spent_by_a = ApprovalRequest(
        **{
            **{
                field: getattr(record, field)
                for field in record.__dataclass_fields__
                if field != "state"
            },
            "state": ApprovalState.CONSUMED,
        }
    )

    assert store.transition_approved(spent_by_a) is True
    assert store.transition_approved(spent_by_a) is False


def test_the_transition_refuses_anything_not_currently_approved() -> None:
    store = InMemoryApprovalStore()
    queue = ApprovalQueue(store)
    record, _token = queue.request(
        title="Pending", what_happens="nothing", requested_by=RUNTIME_REQUESTED_BY
    )

    pending = store.get(record.request_id)
    attempt = ApprovalRequest(
        **{
            **{
                field: getattr(pending, field)
                for field in pending.__dataclass_fields__
                if field != "state"
            },
            "state": ApprovalState.CONSUMED,
        }
    )
    assert store.transition_approved(attempt) is False


# ---------------------------------------------------------------------------
# End to end through a real adapter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_real_adapter_refuses_the_second_identical_call() -> None:
    """The unit tests above hold the boundary; this holds the whole path.

    A caller replaying a governed GitHub write does not call
    `require_approved_runtime_binding` directly. It calls the tool, and what
    matters is that the refusal reaches it as a failed ToolResult rather than as
    a second branch on Tee's repository.
    """
    import httpx

    from services.agent_runtime.tools import ToolRegistry
    from services.github.agent_adapter import GitHubCapabilityAdapter
    from services.github.client import GitHubRESTClient

    repo = "tdveal74-cell/Meta-Supreme-Apex-Genesis-"
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url)))
        if request.method == "GET":
            return httpx.Response(200, json={"object": {"sha": "a" * 40}})
        return httpx.Response(
            201, json={"ref": "refs/heads/spent-once", "object": {"sha": "b" * 40}}
        )

    args = {"repository": repo, "branch": "spent-once", "base_ref": "main"}
    binding = approval_binding(
        task_id=TASK, step_id=STEP, tool_name="github.create_branch", arguments=args
    )

    queue = ApprovalQueue(InMemoryApprovalStore())
    record, token = queue.request(
        title="Branch",
        what_happens=f"Create a branch. {approval_marker(binding)}",
        requested_by=RUNTIME_REQUESTED_BY,
    )
    assert queue.decide(record.request_id, token, "approve").approved is True

    client = GitHubRESTClient(
        token="test-secret-token",
        allowed_repos=[repo],
        base_url="https://api.github.test",
        transport=httpx.MockTransport(handler),
    )
    registry = ToolRegistry()
    GitHubCapabilityAdapter(client, queue).register(registry)

    payload = dict(args)
    payload[APPROVAL_METADATA_KEY] = {
        "request_id": record.request_id,
        "binding": binding,
        "task_id": TASK,
        "step_id": STEP,
        "tool_name": "github.create_branch",
    }

    first = await registry.execute("github.create_branch", dict(payload))
    assert first.ok is True, first.error
    reached_github = len(calls)
    assert reached_github > 0

    second = await registry.execute("github.create_branch", dict(payload))
    assert second.ok is False
    assert "consumed" in second.error and "not approved" in second.error

    # The assertion this test exists for: the replay stopped at the capability
    # boundary and never became a second HTTP request against the repository.
    assert len(calls) == reached_github, "the replay reached GitHub"
