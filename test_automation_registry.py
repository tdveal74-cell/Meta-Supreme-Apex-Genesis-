"""Offline tests for scripts/automation_registry.py.

These prove the shape check, the diff and the exit codes against fixtures.
They prove nothing about the key or the host: only a real run of
`--check` with N8N_VPS_KEY set does that.
"""

import json
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))

import automation_registry as reg  # noqa: E402

TODAY = date(2026, 10, 31)


def doc(*rows, every=90, repo=()):
    return {"review_every_days": every, "workflows": list(rows), "repo": list(repo)}


def row(wid="a1", name="Lane A", reviewed=None, owner="Tee", lane="DEVON"):
    return {"id": wid, "name": name, "lane": lane, "owner": owner, "reviewed": reviewed}


def live(wid="a1", name="Lane A", active=True, updated="2026-09-01T00:00:00.000Z"):
    return {"id": wid, "name": name, "active": active, "updatedAt": updated}


def test_the_shipped_registry_is_well_formed():
    shipped = reg.load()
    assert reg.validate(shipped) == []
    assert len(shipped["workflows"]) == 68
    assert all(r["owner"] == "Tee" for r in shipped["workflows"])


def test_the_shipped_registry_records_no_invented_review_date():
    # Seeded 2026-10-31 with no reviews on record. A date appearing here is a
    # person's act, made in a later commit, never part of the seed.
    assert all(r["reviewed"] is None for r in reg.load()["workflows"])


@pytest.mark.parametrize(
    "bad, fragment",
    [
        ([], "not a JSON object"),
        ({"review_every_days": 0, "workflows": [], "repo": []}, "review_every_days"),
        ({"review_every_days": True, "workflows": [], "repo": []}, "review_every_days"),
        ({"review_every_days": 90, "workflows": {}, "repo": []}, "must be a list"),
        ({"review_every_days": 90, "workflows": []}, "repo must be a list"),
        (doc({**row(), "reveiwed": None}), "wrong fields"),
        (doc({k: v for k, v in row().items() if k != "owner"}), "wrong fields"),
        (doc(row(owner=" ")), "empty owner"),
        (doc(row(reviewed="31/10/2026")), "YYYY-MM-DD"),
        (doc(row(reviewed="2026-02-30")), "not a real date"),
        (doc(row(), row()), "repeats id"),
    ],
)
def test_validate_refuses_a_malformed_registry(bad, fragment):
    problems = reg.validate(bad)
    assert any(fragment in p for p in problems), problems


def test_a_matching_estate_is_clean_and_counts_the_backlog():
    findings, notes = reg.diff(doc(row()), [live()], TODAY)
    assert findings == []
    assert notes == ["NEVER REVIEWED: 1 of 1 workflow rows carry no review date"]


def test_an_active_workflow_with_no_row_is_unowned():
    findings, _ = reg.diff(doc(row()), [live(), live("b2", "New lane")], TODAY)
    assert findings == ['UNOWNED: active workflow b2 "New lane" has no row']


def test_an_inactive_workflow_with_no_row_is_not_a_finding():
    findings, _ = reg.diff(doc(row()), [live(), live("b2", "Draft", active=False)], TODAY)
    assert findings == []


def test_a_row_for_a_deleted_or_deactivated_workflow_is_stale():
    findings, _ = reg.diff(doc(row(), row("b2", "Gone")), [live()], TODAY)
    assert findings == ['STALE: b2 "Gone" is not on the instance']
    findings, _ = reg.diff(doc(row()), [live(active=False)], TODAY)
    assert findings == ['STALE: a1 "Lane A" is on the instance but not active']


def test_a_review_older_than_the_period_is_due():
    findings, _ = reg.diff(doc(row(reviewed="2026-08-01")), [live(updated="2026-07-01T00:00:00Z")], TODAY)
    assert len(findings) == 1 and findings[0].startswith("REVIEW DUE") and "91 days ago" in findings[0]


def test_the_period_boundary_is_inclusive():
    findings, _ = reg.diff(doc(row(reviewed="2026-08-02")), [live(updated="2026-07-01T00:00:00Z")], TODAY)
    assert findings == []


def test_a_change_after_the_review_makes_it_due():
    findings, _ = reg.diff(doc(row(reviewed="2026-10-01")), [live(updated="2026-10-20T09:00:00Z")], TODAY)
    assert findings == [
        'REVIEW DUE: a1 "Lane A" owner Tee, changed 2026-10-20 after its review on 2026-10-01'
    ]


def test_a_change_on_the_review_day_is_covered_by_it():
    findings, _ = reg.diff(doc(row(reviewed="2026-10-20")), [live(updated="2026-10-20T23:59:00Z")], TODAY)
    assert findings == []


def test_a_rename_is_a_note_not_a_finding():
    findings, notes = reg.diff(doc(row()), [live(name="Lane A v2")], TODAY)
    assert findings == []
    assert 'RENAMED: a1 is now "Lane A v2", the row says "Lane A"' in notes


def test_check_without_a_key_cannot_check(monkeypatch, capsys):
    monkeypatch.delenv("N8N_VPS_KEY", raising=False)
    assert reg.main(["--check"]) == reg.CANNOT_CHECK
    assert "N8N_VPS_KEY is not set" in capsys.readouterr().out


def test_validate_mode_needs_no_network(monkeypatch):
    monkeypatch.delenv("N8N_VPS_KEY", raising=False)
    assert reg.main(["--validate"]) == reg.OK


def test_an_invalid_file_is_a_finding_before_any_read(tmp_path, monkeypatch):
    path = tmp_path / "r.json"
    path.write_text(json.dumps(doc(row(), row())))
    monkeypatch.setenv("N8N_VPS_KEY", "never-used")
    monkeypatch.setattr(reg, "fetch_workflows", lambda *a: pytest.fail("read before validating"))
    assert reg.main(["--check", "--registry", str(path)]) == reg.FINDING


def test_check_exit_codes_follow_the_diff(tmp_path, monkeypatch):
    path = tmp_path / "r.json"
    path.write_text(json.dumps(doc(row())))
    monkeypatch.setenv("N8N_VPS_KEY", "fixture")
    monkeypatch.setattr(reg, "repo_automations", lambda *a: [])
    monkeypatch.setattr(reg, "fetch_workflows", lambda *a: [live()])
    assert reg.main(["--check", "--registry", str(path)]) == reg.OK
    monkeypatch.setattr(reg, "fetch_workflows", lambda *a: [live(), live("b2", "New")])
    assert reg.main(["--check", "--registry", str(path)]) == reg.FINDING


def test_a_failed_read_cannot_check(tmp_path, monkeypatch):
    path = tmp_path / "r.json"
    path.write_text(json.dumps(doc(row())))
    monkeypatch.setenv("N8N_VPS_KEY", "fixture")

    def boom(*_):
        raise ValueError("the workflow listing still had a cursor after 20 pages")

    monkeypatch.setattr(reg, "fetch_workflows", boom)
    assert reg.main(["--check", "--registry", str(path)]) == reg.CANNOT_CHECK


def test_fetch_follows_the_cursor_and_refuses_a_partial_listing(monkeypatch):
    pages = [
        {"data": [{"id": "a1", "name": "A", "active": True, "updatedAt": "x", "nodes": []}], "nextCursor": "c1"},
        {"data": [{"id": "b2", "name": "B", "active": False, "updatedAt": "y"}], "nextCursor": None},
    ]
    seen = []

    class Response:
        def __init__(self, body):
            self.body = json.dumps(body).encode()

        def read(self, *_):
            return self.body

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def fake_urlopen(request, timeout):
        seen.append(request.full_url)
        return Response(pages[len(seen) - 1])

    monkeypatch.setattr(reg.urllib.request, "urlopen", fake_urlopen)
    out = reg.fetch_workflows("https://host", "k")
    assert [w["id"] for w in out] == ["a1", "b2"]
    assert "nodes" not in out[0]
    assert "cursor=c1" in seen[1]

    endless = {"data": [], "nextCursor": "again"}
    monkeypatch.setattr(reg.urllib.request, "urlopen", lambda r, timeout: Response(endless))
    with pytest.raises(ValueError, match="still had a cursor"):
        reg.fetch_workflows("https://host", "k")


def test_a_review_date_in_the_future_is_a_finding():
    # Found by the critic of c7bc739: 2027 typed for 2026 silenced both alarms.
    findings, _ = reg.diff(doc(row(reviewed="2027-01-01")), [live()], TODAY)
    assert len(findings) == 1 and findings[0].startswith("BAD REVIEW DATE")


def test_a_review_dated_today_is_not_in_the_future():
    findings, _ = reg.diff(doc(row(reviewed="2026-10-31")), [live()], TODAY)
    assert findings == []


def test_the_listing_request_uses_only_parameters_the_watchdogs_already_use():
    # excludePinnedData was in the first version and is used nowhere else in
    # the repository, so it was unproven against the live API and dropped.
    import inspect
    source = inspect.getsource(reg.fetch_workflows)
    assert "excludePinnedData" not in source
    assert "/api/v1/workflows?limit=100" in source


# Repository automations, added 2026-11-01.


def rrow(path=".github/workflows/x.yml", reviewed=None):
    return {"path": path, "lane": "GitHub Actions", "owner": "Tee", "reviewed": reviewed}


def test_the_shipped_registry_claims_every_repository_automation():
    # The pin that turns a pull request red when it adds a workflow file or a
    # hook nobody has claimed, the way the CI job count is pinned to its files.
    shipped = reg.load()
    present = reg.repo_automations()
    assert reg.repo_coverage(shipped, present) == []
    assert ".github/workflows/ci.yml" in present
    assert ".claude/hooks/gate_ledger.py" in present
    assert all(r["reviewed"] is None for r in shipped["repo"])


def test_discovery_reads_workflow_files_and_wired_hooks(tmp_path):
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "a.yml").write_text("on: push\n")
    (tmp_path / ".github" / "workflows" / "b.yaml").write_text("on: push\n")
    (tmp_path / ".github" / "workflows" / "notes.md").write_text("not a workflow\n")
    (tmp_path / ".claude").mkdir()
    settings = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
        {"type": "command", "command": 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/g.py" pre; rc=$?'},
        {"type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/s.sh"},
    ]}]}}
    (tmp_path / ".claude" / "settings.json").write_text(json.dumps(settings))
    assert reg.repo_automations(str(tmp_path)) == [
        ".claude/hooks/g.py", ".claude/hooks/s.sh", ".github/workflows/a.yml", ".github/workflows/b.yaml",
    ]


def test_discovery_of_an_empty_tree_finds_nothing(tmp_path):
    assert reg.repo_automations(str(tmp_path)) == []


def test_an_unclaimed_file_and_a_claim_on_nothing_are_findings():
    present = [".github/workflows/new.yml", ".github/workflows/x.yml"]
    assert reg.repo_coverage(doc(repo=[rrow()]), present) == [
        "UNOWNED: .github/workflows/new.yml runs from this repository and has no row"
    ]
    assert reg.repo_coverage(doc(repo=[rrow(), rrow(".github/workflows/gone.yml")]), [".github/workflows/x.yml"]) == [
        "STALE: the row for .github/workflows/gone.yml names a file that is not wired in"
    ]


def test_validate_refuses_a_malformed_repo_row():
    bad = doc(repo=[{"path": "x", "lane": "L", "owner": "Tee"}])
    assert any("repo row 0 has the wrong fields" in p for p in reg.validate(bad))
    assert any("repeats path" in p for p in reg.validate(doc(repo=[rrow(), rrow()])))


def test_a_repository_review_follows_the_file_s_last_commit():
    present = [".github/workflows/x.yml"]
    findings, notes = reg.repo_diff(
        doc(repo=[rrow(reviewed="2026-10-01")]), present, {present[0]: date(2026, 10, 20)}, TODAY
    )
    assert findings == [
        "REVIEW DUE: .github/workflows/x.yml owner Tee, changed 2026-10-20 after its review on 2026-10-01"
    ]
    findings, _ = reg.repo_diff(doc(repo=[rrow(reviewed="2026-10-20")]), present, {present[0]: date(2026, 10, 20)}, TODAY)
    assert findings == []
    _, notes = reg.repo_diff(doc(repo=[rrow()]), present, {present[0]: None}, TODAY)
    assert notes == ["NEVER REVIEWED: 1 of 1 repository rows carry no review date"]


def test_validate_mode_fails_on_an_unclaimed_repository_automation(tmp_path, monkeypatch):
    path = tmp_path / "r.json"
    path.write_text(json.dumps(doc(row(), repo=[])))
    monkeypatch.setattr(reg, "repo_automations", lambda *a: [".github/workflows/new.yml"])
    assert reg.main(["--validate", "--registry", str(path)]) == reg.FINDING


def test_git_dates_refuse_a_shallow_clone(tmp_path):
    import subprocess

    origin = tmp_path / "origin"
    origin.mkdir()
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@x", "GIT_COMMITTER_DATE": "2026-10-02T00:00:00Z",
           "GIT_AUTHOR_DATE": "2026-10-02T00:00:00Z"}
    run = lambda *a, cwd=origin: subprocess.run(a, cwd=cwd, env=env, check=True, capture_output=True)  # noqa: E731
    run("git", "init", "-q")
    (origin / "a.yml").write_text("1\n")
    run("git", "add", "a.yml")
    run("git", "commit", "-q", "-m", "one")
    env["GIT_COMMITTER_DATE"] = "2026-10-05T00:00:00Z"
    (origin / "b.yml").write_text("1\n")
    run("git", "add", "b.yml")
    run("git", "commit", "-q", "-m", "two")
    assert reg.git_changed(str(origin), "a.yml") == date(2026, 10, 2)
    assert reg.git_changed(str(origin), "b.yml") == date(2026, 10, 5)
    assert reg.git_changed(str(origin), "missing.yml") is None

    shallow = tmp_path / "shallow"
    run("git", "clone", "-q", "--depth", "1", f"file://{origin}", str(shallow), cwd=tmp_path)
    with pytest.raises(ValueError, match="shallow"):
        reg.git_changed(str(shallow), "a.yml")


def test_check_cannot_check_on_a_shallow_clone(tmp_path, monkeypatch, capsys):
    path = tmp_path / "r.json"
    path.write_text(json.dumps(doc(row(), repo=[rrow()])))
    monkeypatch.setenv("N8N_VPS_KEY", "fixture")
    monkeypatch.setattr(reg, "repo_automations", lambda *a: [".github/workflows/x.yml"])
    monkeypatch.setattr(reg, "fetch_workflows", lambda *a: [live()])

    def shallow(*_):
        raise ValueError("the checkout is shallow, so file dates would all read as the newest commit")

    monkeypatch.setattr(reg, "git_changed", shallow)
    assert reg.main(["--check", "--registry", str(path)]) == reg.CANNOT_CHECK
    assert "shallow" in capsys.readouterr().out


# Found by the critic of 1e08f1da.


def _tree(tmp_path, commands):
    (tmp_path / ".claude").mkdir()
    hooks = [{"type": "command", "command": c} for c in commands]
    (tmp_path / ".claude" / "settings.json").write_text(
        json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": hooks}]}})
    )
    return str(tmp_path)


def test_a_hook_in_any_spelling_is_discovered(tmp_path):
    root = _tree(tmp_path, [
        '"${CLAUDE_PROJECT_DIR}/.claude/hooks/a.sh"',
        ".claude/hooks/b.sh",
        "bash /abs/c.sh",
    ])
    assert reg.repo_automations(root) == [
        ".claude/hooks/a.sh", ".claude/settings.json#PreToolUse/2", ".claude/settings.json#PreToolUse/3",
    ]


def test_a_malformed_settings_file_cannot_check(tmp_path, monkeypatch, capsys):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text("{bad")
    monkeypatch.setattr(reg, "REPO", str(tmp_path))
    real = reg.repo_automations
    monkeypatch.setattr(reg, "repo_automations", lambda: real(str(tmp_path)))
    assert reg.main(["--validate"]) == reg.CANNOT_CHECK
    assert "JSONDecodeError" in capsys.readouterr().out


def test_git_dates_are_utc_and_hooks_follow_their_wiring(tmp_path):
    import subprocess

    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@x"}

    def commit(when, *files):
        for name in files:
            target = tmp_path / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(when + "\n")
            subprocess.run(["git", "add", name], cwd=tmp_path, env=env, check=True)
        e = {**env, "GIT_COMMITTER_DATE": when, "GIT_AUTHOR_DATE": when}
        subprocess.run(["git", "commit", "-q", "-m", when], cwd=tmp_path, env=e, check=True)

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    # 23:30 at UTC-05:00 is 04:30 UTC the next day.
    commit("2026-10-02T23:30:00-05:00", ".claude/hooks/h.py")
    commit("2026-10-09T12:00:00+00:00", ".claude/settings.json")
    assert reg.git_changed(str(tmp_path), ".claude/hooks/h.py") == date(2026, 10, 3)
    dates = reg.changed_dates(str(tmp_path), [".claude/hooks/h.py", ".claude/settings.json#Stop/1"])
    assert dates == {".claude/hooks/h.py": date(2026, 10, 9), ".claude/settings.json#Stop/1": date(2026, 10, 9)}
