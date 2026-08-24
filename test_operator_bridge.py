from pathlib import Path

import pytest

from services.devon.approval import ApprovalQueue
from services.operator.bridge import OperatorBridge, OperatorError, Risk


@pytest.fixture()
def bridge(tmp_path: Path) -> OperatorBridge:
    return OperatorBridge(root=tmp_path, enabled=True, operator_key="test-key")


def test_read_command_executes_without_approval(bridge: OperatorBridge) -> None:
    plan = bridge.plan("pwd")
    assert plan.risk is Risk.READ
    result = bridge.execute_read(plan)
    assert result.returncode == 0
    assert result.stdout.strip() == str(bridge.root)


def test_unknown_command_fails_closed_to_approval(bridge: OperatorBridge) -> None:
    plan = bridge.plan("touch example.txt")
    assert plan.risk is Risk.WRITE
    assert plan.approval_required is True


def test_environment_dump_requires_approval(bridge: OperatorBridge) -> None:
    plan = bridge.plan("printenv")
    assert plan.risk is Risk.WRITE
    assert plan.approval_required is True


def test_write_executes_only_after_devon_approval(bridge: OperatorBridge) -> None:
    approvals = ApprovalQueue()
    plan = bridge.plan("touch approved.txt")
    request_id, token = bridge.request(plan, approvals)

    with pytest.raises(OperatorError, match="not approved"):
        bridge.execute_approved(request_id, approvals)

    decision = approvals.decide(request_id, token, "approve", "Tee")
    assert decision.approved is True

    result = bridge.execute_approved(request_id, approvals)
    assert result.returncode == 0
    assert (bridge.root / "approved.txt").exists()

    with pytest.raises(OperatorError, match="no pending"):
        bridge.execute_approved(request_id, approvals)


def test_working_directory_cannot_escape_root(bridge: OperatorBridge, tmp_path: Path) -> None:
    outside = tmp_path.parent
    with pytest.raises(OperatorError, match="escapes operator root"):
        bridge.plan("pwd", str(outside))


@pytest.mark.parametrize("command", ["sudo id", "shutdown now", "rm -rf /"])
def test_host_destruction_commands_are_blocked(bridge: OperatorBridge, command: str) -> None:
    plan = bridge.plan(command)
    assert plan.risk is Risk.BLOCKED


def test_operator_key_is_checked(bridge: OperatorBridge) -> None:
    bridge.authenticate("test-key")
    with pytest.raises(OperatorError, match="does not match"):
        bridge.authenticate("wrong-key")
