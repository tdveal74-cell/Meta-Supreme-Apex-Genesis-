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


def test_read_lane_never_reads_the_process_environment(bridge: OperatorBridge) -> None:
    """H4 as the audit ran it: cat is read-only by name, /proc/self/environ is
    the host's secrets. It now fails closed to human approval."""
    plan = bridge.plan("cat /proc/self/environ")
    assert plan.risk is Risk.WRITE
    assert plan.approval_required is True
    assert "/proc/self/environ" in plan.reason
    with pytest.raises(OperatorError, match="not read-only"):
        bridge.execute_read(plan)


@pytest.mark.parametrize(
    "command",
    [
        "cat ../outside.txt",
        "ls /",
        "cat /etc/passwd",
        "head -n 2 /sys/kernel/hostname",
        "git --git-dir=/tmp/elsewhere/.git log",
        "cat .env",
        "git show HEAD:.env",
        "ls .git/config",
    ],
)
def test_read_lane_stays_inside_the_root_and_off_dotfiles(
    bridge: OperatorBridge, command: str
) -> None:
    plan = bridge.plan(command)
    assert plan.risk is Risk.WRITE, plan.reason
    assert "read lane" in plan.reason


def test_read_lane_still_reads_files_inside_the_root(bridge: OperatorBridge) -> None:
    (bridge.root / "notes.txt").write_text("inside\n", encoding="utf-8")
    (bridge.root / "sub").mkdir()
    (bridge.root / "sub" / "deep.txt").write_text("deeper\n", encoding="utf-8")
    for command in ("cat notes.txt", "ls -la", "head -n 1 sub/deep.txt", "wc -l ./notes.txt"):
        plan = bridge.plan(command)
        assert plan.risk is Risk.READ, plan.reason
        assert bridge.execute_read(plan).returncode == 0


@pytest.mark.parametrize("command", ["ps eww -p 1", "ps auxe", "ps -eo args"])
def test_ps_left_the_read_lane(bridge: OperatorBridge, command: str) -> None:
    """The fresh critic's finding on the first cut: ps takes no path argument
    and reads /proc/<pid>/environ itself, so `ps eww` printed the process
    environment on the unattended lane. It now waits for the human."""
    plan = bridge.plan(command)
    assert plan.risk is Risk.WRITE, plan.reason
    assert plan.approval_required is True


def test_host_paths_are_matched_by_component_not_prefix() -> None:
    assert OperatorBridge._is_host_path(Path("/proc/self/environ"))
    assert OperatorBridge._is_host_path(Path("/sys/kernel/hostname"))
    assert OperatorBridge._is_host_path(Path("/dev"))
    assert not OperatorBridge._is_host_path(Path("/devon/repo/notes.txt"))
    assert not OperatorBridge._is_host_path(Path("/system/x"))
    assert not OperatorBridge._is_host_path(Path("/procurement/y"))


def test_read_lane_follows_symlinks_before_judging(bridge: OperatorBridge, tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside.txt"
    outside.write_text("secret\n", encoding="utf-8")
    (bridge.root / "innocent.txt").symlink_to(outside)
    plan = bridge.plan("cat innocent.txt")
    assert plan.risk is Risk.WRITE
    assert "operator root" in plan.reason
