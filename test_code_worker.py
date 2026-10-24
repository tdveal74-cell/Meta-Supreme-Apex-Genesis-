"""The DEVON code worker, end to end against a real local git remote.

No network and no model: the agent is a fake that edits the checkout the way
the Agent SDK would, GitHub is a recorder, and the remote is a bare repository
on disk. Everything else, clone, branch, commit, test run and push, is real git
and a real subprocess. What this cannot prove is the Agent SDK itself and the
live GitHub API; deploy/code-worker/DEPLOY.md carries the one live job that does.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent / "deploy" / "code-worker"))

import worker as cw  # noqa: E402

REPO = "tdveal74-cell/sample"
TOKEN = "ghp_test_token_that_must_never_leak"


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def remote(tmp_path):
    bare = tmp_path / "remote.git"
    _git("init", "--quiet", "--bare", "--initial-branch=main", str(bare), cwd=tmp_path)
    seed = tmp_path / "seed"
    _git("clone", "--quiet", str(bare), str(seed), cwd=tmp_path)
    (seed / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    (seed / "test_calc.py").write_text("from calc import add\n\ndef test_add():\n    assert add(2, 2) == 4\n")
    _git("-c", "user.name=t", "-c", "user.email=t@t", "add", "-A", cwd=seed)
    _git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "--quiet", "-m", "seed", cwd=seed)
    _git("push", "--quiet", "origin", "HEAD:main", cwd=seed)
    return bare


def _agent(edit=None, commit=True, seen=None):
    async def query(**kwargs):
        if seen is not None:
            seen.update(kwargs)
        cwd = Path(kwargs["cwd"])
        if edit:
            edit(cwd)
            if commit:
                _git("add", "-A", cwd=cwd)
                _git("commit", "--quiet", "-m", "fix add", cwd=cwd)
        yield SimpleNamespace(subtype="success", is_error=False, num_turns=3, total_cost_usd=0.42, result="Fixed add.")
    return query


def _fix(cwd):
    (cwd / "calc.py").write_text("def add(a, b):\n    return a + b\n")


def _break_more(cwd):
    (cwd / "calc.py").write_text("def add(a, b):\n    return a * 3\n")


def _worker(tmp_path, remote, *, query, prs):
    async def http(method, path, headers, body):
        prs.append({"method": method, "path": path, "headers": headers, "body": body})
        return {"number": 7, "html_url": "https://github.test/pr/7", "draft": body["draft"]}

    return cw.CodeWorker(
        github_token=TOKEN,
        allowed_repos=[REPO],
        jobs_dir=tmp_path / "jobs",
        query=query,
        http=http,
        clone_url=lambda repo: str(remote),
    )


JOB = {
    "job_id": "JOB-0001",
    "repository": REPO,
    "task": "Fix add so that it returns the sum of its two arguments.",
    "test_command": f"{sys.executable} -m pytest -q -p no:cacheprovider",
    "approval_id": "REQ-ABC",
}


def _branch_file(remote, branch, path):
    return subprocess.run(["git", "show", f"{branch}:{path}"], cwd=remote, capture_output=True, text=True).stdout


def test_a_job_lands_on_its_own_branch_with_a_draft_pr_and_main_untouched(tmp_path, remote):
    prs, seen = [], {}
    w = _worker(tmp_path, remote, query=_agent(_fix, seen=seen), prs=prs)
    w.accept(JOB)
    record = asyncio.run(w.execute("JOB-0001"))
    assert record.state == "done", record.error
    assert record.tests["passed"] is True and record.tests["exit_code"] == 0
    assert record.commits == 1
    assert "return a + b" in _branch_file(remote, "devon/code-job-0001", "calc.py")
    assert "return a - b" in _branch_file(remote, "main", "calc.py")
    assert len(prs) == 1 and prs[0]["body"]["draft"] is True
    assert prs[0]["body"]["head"] == "devon/code-job-0001" and prs[0]["body"]["base"] == "main"
    assert record.pull_request == {"number": 7, "url": "https://github.test/pr/7", "draft": True}
    # The agent got subagents, limits, and an environment with no GitHub credential.
    assert set(seen["subagents"]) == {"test-writer", "reviewer"}
    assert seen["env"]["GITHUB_TOKEN"] == "" and seen["env"]["DEVON_CODE_WORKER_GITHUB_TOKEN"] == ""
    assert "Bash(git push:*)" in seen["disallowed_tools"]


def test_failing_tests_still_open_a_draft_labelled_failing(tmp_path, remote):
    prs = []
    w = _worker(tmp_path, remote, query=_agent(_break_more), prs=prs)
    w.accept(JOB)
    record = asyncio.run(w.execute("JOB-0001"))
    assert record.state == "done_tests_failing"
    assert record.tests["passed"] is False
    assert "TESTS FAILING" in prs[0]["body"]["title"]


def test_uncommitted_work_is_committed_by_the_worker(tmp_path, remote):
    prs = []
    w = _worker(tmp_path, remote, query=_agent(_fix, commit=False), prs=prs)
    w.accept(JOB)
    record = asyncio.run(w.execute("JOB-0001"))
    assert record.state == "done" and record.commits == 1


def test_no_change_pushes_nothing_and_opens_nothing(tmp_path, remote):
    prs = []
    w = _worker(tmp_path, remote, query=_agent(None), prs=prs)
    w.accept(JOB)
    record = asyncio.run(w.execute("JOB-0001"))
    assert record.state == "no_change"
    assert prs == []
    branches = subprocess.run(["git", "branch", "--list"], cwd=remote, capture_output=True, text=True).stdout
    assert "devon/code" not in branches


def test_the_token_is_scrubbed_from_a_failure_and_never_written_to_disk(tmp_path, remote):
    def boom(**kwargs):
        raise RuntimeError(f"agent crashed holding {TOKEN}")

    w = _worker(tmp_path, remote, query=boom, prs=[])
    w.accept(JOB)
    record = asyncio.run(w.execute("JOB-0001"))
    assert record.state == "failed"
    assert TOKEN not in record.error and "[redacted]" in record.error
    for path in (tmp_path / "jobs").iterdir():
        assert TOKEN not in path.read_text()


def test_execute_twice_runs_the_agent_once(tmp_path, remote):
    calls = []

    async def query(**kwargs):
        calls.append(1)
        _fix(Path(kwargs["cwd"]))
        yield SimpleNamespace(subtype="success", is_error=False, num_turns=1, total_cost_usd=0.1, result="ok")

    w = _worker(tmp_path, remote, query=query, prs=[])
    w.accept(JOB)
    asyncio.run(w.execute("JOB-0001"))
    again = asyncio.run(w.execute("JOB-0001"))
    assert calls == [1] and again.state == "done"


@pytest.mark.parametrize(
    "change,match",
    [
        ({"repository": "someone/else"}, "not allowlisted"),
        ({"base_ref": "../main"}, "plain branch"),
        ({"base_ref": "devon/code-x"}, "plain branch"),
        ({"max_budget_usd": 500}, "at most"),
        ({"task": "fix it"}, "at least 20"),
        ({"job_id": "a"}, "job_id"),
        ({"test_command": "pytest\nrm -rf /"}, "one line"),
    ],
)
def test_validate_refuses(change, match):
    with pytest.raises(cw.JobRefused, match=match):
        cw.validate_job({**JOB, **change}, allowed_repos=[REPO])


def test_the_same_job_id_for_a_different_job_is_refused(tmp_path, remote):
    w = _worker(tmp_path, remote, query=_agent(_fix), prs=[])
    w.accept(JOB)
    assert w.accept(JOB).state == "queued"
    with pytest.raises(cw.JobRefused, match="already used"):
        w.accept({**JOB, "task": "Something else entirely, and long enough to pass."})


def test_the_http_surface_refuses_without_the_key(tmp_path, remote):
    from fastapi.testclient import TestClient

    import server as worker_app

    w = _worker(tmp_path, remote, query=_agent(_fix), prs=[])
    client = TestClient(worker_app.build_app(w, key="k"))
    assert client.post("/jobs", json=JOB).status_code == 401
    assert client.post("/jobs", json=JOB, headers={"x-devon-code-key": "wrong"}).status_code == 401
    assert client.get("/jobs/JOB-0001", headers={"x-devon-code-key": "k"}).status_code == 404
    assert client.get("/health").json()["key_set"] is True
    assert TOKEN not in client.get("/health").text

    unset = TestClient(worker_app.build_app(w, key=""))
    assert unset.post("/jobs", json=JOB, headers={"x-devon-code-key": ""}).status_code == 503
