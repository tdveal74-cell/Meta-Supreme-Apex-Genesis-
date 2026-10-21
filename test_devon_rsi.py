"""Behavior and negative controls for the proposal-only RSI runner."""

import copy
import hashlib
import json
import os
import py_compile
import subprocess
import sys

import pytest

from tools.devon_rsi import kernel, maker, runner


@pytest.fixture
def cases():
    return kernel.read_json(runner.ROOT / "cases.json")


@pytest.fixture
def trust():
    return hashlib.sha256((runner.ROOT / "release.json").read_bytes()).hexdigest()


def complete():
    return kernel.make_candidate({k: v[1] for k, v in kernel.ALLOWED.items()})


@pytest.mark.parametrize("index", range(50))
def test_case_acceptance(cases, index):
    result = kernel.score([cases[index]], complete())[0]
    assert result["passed"]


@pytest.mark.parametrize("surface", ["../canon", "/etc/passwd", "charter", "gates", "suite", "secrets", "devon_skill", "surfaces/review_policy.json/../x"])
def test_closed_path_is_rejected(surface):
    proposal = complete()
    proposal["surface"] = surface
    with pytest.raises(kernel.Refused):
        kernel.candidate(proposal)


@pytest.mark.parametrize("key", ["promote", "code", "standing_lane", "cost", "identity", "scorer"])
def test_candidate_cannot_add_capability(key):
    proposal = complete()
    proposal["settings"][key] = True
    with pytest.raises(kernel.Refused):
        kernel.candidate(proposal)


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e9999}', b'[' * 2000, b'x' * 65537, b'\xff'])
def test_malformed_data_fails_closed(raw):
    with pytest.raises(kernel.Refused):
        kernel.strict_load(raw)


def test_shared_critical_failure_is_vetoed(cases):
    base = kernel.score(cases, complete())
    proposed = copy.deepcopy(base)
    base[0]["passed"] = proposed[0]["passed"] = False
    assert kernel.decide(base, proposed) == ("REJECT", "CRITICAL_FAILURE")


def test_noncritical_regression_is_vetoed(cases):
    base = kernel.score(cases, complete())
    proposed = copy.deepcopy(base)
    next(row for row in proposed if not row["critical"])["passed"] = False
    assert kernel.decide(base, proposed) == ("REJECT", "REGRESSION")


def test_missing_case_and_duplicate_refuse(cases):
    rows = kernel.score(cases, complete())
    with pytest.raises(kernel.Refused):
        kernel.decide(rows, rows[:-1])
    with pytest.raises(kernel.Refused):
        kernel.score([cases[0], cases[0]], complete())


def test_search_ablates_and_never_promotes(tmp_path, trust):
    result = runner.run(tmp_path / "new", trust)
    assert result["status"] == "ACCEPT_FOR_HUMAN_REVIEW"
    assert result["evaluated_candidates"] == 16
    assert result["best"]["passed"] == result["best"]["total"] == 50
    assert result["baseline_passed"] < 50
    assert result["evaluations_used"] <= kernel.MAX_EVALUATIONS
    assert not result["gain_claim"] and not result["promoted"]
    assert result["production_effects"] == []
    assert len(result["ablation"][-1]["kept"]) == 4
    assert all(r["passed"] < 50 for r in result["ablation"][:-1])
    assert runner.verify_journal(tmp_path / "new/journal", result["journal_head"])


def test_budget_overrun_leaves_rejection(tmp_path, trust):
    result = runner.run(tmp_path / "budget", trust, evaluations=1)
    assert result["status"] == "REJECT"
    assert json.loads((tmp_path / "budget/decision.json").read_text())["status"] == "REJECT"


def test_budget_time_and_bool_refuse(monkeypatch):
    clock = iter([0, 61])
    monkeypatch.setattr(runner.time, "monotonic", lambda: next(clock))
    budget = runner.Budget()
    with pytest.raises(kernel.Refused, match="TIME_BUDGET"):
        budget.charge()
    with pytest.raises(kernel.Refused):
        runner.Budget(True)


def test_predecessor_never_overwritten(tmp_path, trust):
    out = tmp_path / "old"
    out.mkdir()
    (out / "predecessor").write_text("preserve")
    with pytest.raises(kernel.Refused):
        runner.run(out, trust)
    assert (out / "predecessor").read_text() == "preserve"


def test_trust_drift_and_injection_are_rejected(tmp_path):
    (tmp_path / "core.py").write_text("x=1")
    manifest = {"core.py": hashlib.sha256(b"x=1").hexdigest()}
    raw = kernel.canonical(manifest)
    (tmp_path / "release.json").write_bytes(raw)
    trust = hashlib.sha256(raw).hexdigest()
    kernel.verify_seal(tmp_path, trust)
    (tmp_path / "extra.py").write_text("x=2")
    with pytest.raises(kernel.Refused, match="RELEASE_FILE_SET_DRIFT"):
        kernel.verify_seal(tmp_path, trust)
    (tmp_path / "extra.py").unlink()
    (tmp_path / "core.py").write_text("x=3")
    with pytest.raises(kernel.Refused, match="RELEASE_DRIFT"):
        kernel.verify_seal(tmp_path, trust)
    with pytest.raises(kernel.Refused, match="MANIFEST_DRIFT"):
        kernel.verify_seal(tmp_path, "0" * 64)


def test_symlink_is_not_a_candidate(tmp_path):
    (tmp_path / "data").write_bytes(kernel.canonical(complete()))
    (tmp_path / "link").symlink_to(tmp_path / "data")
    with pytest.raises(kernel.Refused):
        kernel.read_json(tmp_path / "link")


def test_journal_tamper_truncate_reorder(tmp_path):
    journal = runner.Journal(tmp_path / "journal")
    journal.append({"type": "start"})
    head = journal.append({"type": "finish"})
    path = journal.path / "000001.json"
    saved = path.read_bytes()
    path.unlink()
    with pytest.raises(kernel.Refused, match="JOURNAL_HEAD"):
        runner.verify_journal(journal.path, head)
    path.write_bytes(saved.replace(b"finish", b"forged"))
    with pytest.raises(kernel.Refused, match="JOURNAL_HASH"):
        runner.verify_journal(journal.path, head)
    path.write_bytes(saved)
    path.rename(journal.path / "000002.json")
    with pytest.raises(kernel.Refused, match="JOURNAL_CHAIN"):
        runner.verify_journal(journal.path, head)


def test_observation_requires_full_window_and_no_duplicates():
    events = [{"id": str(i), "failed": i == 0, "source": "operator_export"} for i in range(20)]
    assert not runner.observation_window(events[:-1])["trigger"]
    assert runner.observation_window(events)["trigger"]
    assert not runner.observation_window(events)["production_verified"]
    with pytest.raises(kernel.Refused):
        runner.observation_window(events + [events[0]])
    events[0]["identity"] = "Tee"
    with pytest.raises(kernel.Refused):
        runner.observation_window(events)


def test_gain_never_comes_from_fixtures_or_constant_deltas():
    pairs = [{"block_id": str(i), "control": 0.2, "candidate": 0.9} for i in range(20)]
    assert kernel.gain_evidence(pairs, fixture=True)["reason"] == "FIXTURE_ONLY"
    assert kernel.gain_evidence(pairs, fixture=False)["reason"] == "NO_VARIANCE"
    pairs[0]["candidate"] = 0.8
    evidence = kernel.gain_evidence(pairs, fixture=False)
    assert evidence["statistical_signal"] and not evidence["claim"]
    assert not kernel.gain_evidence(pairs, fixture=False, comparisons=100000)["statistical_signal"]
    pairs[0]["candidate"] = float("nan")
    assert kernel.gain_evidence(pairs, fixture=False)["reason"] == "INVALID_PAIRS"


def test_maker_receives_no_evaluation_data():
    req = maker.request()
    assert req["options"]["num_predict"] == 512
    assert "cases" not in json.dumps(req)
    assert "expected" not in json.dumps(req)
    assert "tools" not in req


def test_cli_refuses_forged_identity_without_echo(tmp_path, trust):
    proposal = complete()
    proposal["identity"] = "CANARY_DO_NOT_ECHO"
    source = tmp_path / "bad.json"
    source.write_text(json.dumps(proposal))
    process = subprocess.run(
        [sys.executable, "-m", "tools.devon_rsi.runner", "--candidate", str(source),
         "--output", str(tmp_path / "report"), "--trust-sha256", trust],
        capture_output=True, text=True, timeout=10,
    )
    assert process.returncode == 2
    assert "CANARY_DO_NOT_ECHO" not in process.stdout + process.stderr
    assert not (tmp_path / "report").exists()


@pytest.mark.parametrize("operation", [
    {"lane": "S1", "action": "emit_receipt"},
    {"lane": "S2", "action": "file_receipt", "target": "_Devon Core", "preserve_predecessor": True},
    {"lane": "S3", "action": "file_continuity", "target": "_Devon Core", "preserve_predecessor": True},
    {"lane": "S4", "action": "editforge_dispatch", "dry_run": True},
    {"lane": "S5", "action": "airtable_read", "mode": "records_or_schema"},
])
def test_standing_lanes_produce_plans_only(operation):
    assert kernel.standing_plan(operation)["decision"] == "STANDING_PLAN"
    assert kernel.standing_plan(operation)["effects"] == []
    altered = dict(operation, grant="promote")
    assert kernel.standing_plan(altered)["decision"] == "HOLD"


def test_standing_lane_never_expands():
    assert kernel.standing_plan({"lane": "S4", "action": "editforge_dispatch", "dry_run": False})["decision"] == "HOLD"
    assert kernel.standing_plan({"lane": "S3", "action": "file_continuity", "target": "Canon", "preserve_predecessor": True})["decision"] == "HOLD"


@pytest.mark.parametrize("script,args", [
    ("run-isolated.sh", ["/opt/devon/rsi/releases/../../../../tmp/escape", "a" * 64,
                         "sha256:" + "b" * 64, "/opt/devon/rsi/runs/ok"]),
    ("run-isolated.sh", ["/opt/devon/rsi/releases/" + "c" * 40, "a" * 64,
                         "sha256:" + "b" * 64, "/opt/devon/rsi/runs/../../../../../tmp/escape"]),
    ("make-local.sh", ["/opt/devon/rsi/releases/../../../../tmp/escape", "/opt/devon/rsi/maker/ok"]),
    ("make-local.sh", ["/opt/devon/rsi/releases/" + "c" * 40, "/opt/devon/rsi/maker/../../../../../tmp/escape"]),
])
def test_operator_wrapper_rejects_traversal(script, args):
    result = subprocess.run(["bash", "deploy/devon-rsi/" + script, *args],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode != 0


def test_fresh_bytecode_prefix_blocks_stale_cache(tmp_path):
    source = tmp_path / "probe.py"
    source.write_text("print('BAD')\n")
    stat = source.stat()
    py_compile.compile(str(source), doraise=True)
    source.write_text("print('YES')\n")
    os.utime(source, (stat.st_atime, stat.st_mtime))
    env = dict(os.environ, PYTHONPATH=str(tmp_path))
    vulnerable = subprocess.run([sys.executable, "-B", "-m", "probe"],
                                env=env, capture_output=True, text=True, check=True)
    assert vulnerable.stdout.strip() == "BAD"
    protected = subprocess.run([sys.executable, "-B", "-X", f"pycache_prefix={tmp_path}/fresh", "-m", "probe"],
                               env=env, capture_output=True, text=True, check=True)
    assert protected.stdout.strip() == "YES"
