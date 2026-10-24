"""DEVON code worker: one approved coding job in, one draft pull request out.

Ruled by Tee 2026-10-24: DEVON writes code through the Claude Agent SDK hosted
on the VPS, with the SDK's own subagents doing the parallel work inside a job.

A job is a sentence of work against one allowlisted repository. The worker:

1. clones the repository into a fresh directory and checks out a new branch
   named for the job, from the base ref the job names;
2. runs the agent there, with a test writer and a reviewer as subagents,
   inside a turn limit and a dollar limit;
3. runs the job's test command ITSELF, after the agent stops, because an
   agent saying the tests pass is a claim and the exit code is the receipt;
4. commits anything the agent left uncommitted, pushes the branch, and opens
   a DRAFT pull request carrying the test result and the cost.

It never merges, never pushes to the base ref, and never force pushes. A job
whose tests fail still opens its draft pull request, labelled failing in the
title, so the work is reviewable rather than lost; nothing about a draft can
reach the base branch without a human.

The GitHub token never enters the agent's environment and is never written to
`.git/config`: git receives it per command as an extra header, and the agent's
environment has it blanked. The agent's own key (`ANTHROPIC_API_KEY`) cannot be
withheld, because the agent needs it to run, and the dollar limit is what bounds
a prompt injected through repository content. That is the residual risk and it
is stated here rather than left for a reader to find.

Everything that touches the outside world is injected (`query`, `run`, `http`),
so the whole flow runs in tests against a local bare repository and a mock
GitHub with no network and no model.
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional, Sequence

JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{5,63}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,99}$")
MAX_TASK_CHARS = 20_000
MAX_TEST_OUTPUT_CHARS = 6_000
DEFAULT_MAX_TURNS = 60
DEFAULT_MAX_BUDGET_USD = 5.0
CEILING_MAX_BUDGET_USD = 50.0
BRANCH_PREFIX = "devon/code-"

AGENT_TOOLS = ["Read", "Edit", "Write", "Glob", "Grep", "Bash", "Task"]
# The worker pushes; the agent never does. These are refused even though the
# agent has no credential to push with, because a refused command is cheaper
# to read in a transcript than a failed one.
AGENT_DENIED = ["Bash(git push:*)", "Bash(git remote:*)", "Bash(curl:*)", "Bash(wget:*)"]

SYSTEM_APPEND = (
    "You are DEVON's code worker, working in a fresh clone on a new branch. "
    "Make the change the task asks for and nothing wider. Run the project's "
    "tests yourself and fix what fails before you stop. Commit your work with "
    "clear messages. Do not push, do not change git remotes, do not touch "
    "credentials, and do not edit CI to make a test pass. If the task cannot be "
    "done, stop and say why in your final message instead of guessing."
)

SUBAGENTS = {
    "test-writer": {
        "description": "Writes or extends tests that pin the behaviour the task asks for.",
        "prompt": (
            "You write tests for the change being made. Prefer one focused test "
            "that fails without the change and passes with it. Never weaken or "
            "delete an existing test."
        ),
        "tools": ["Read", "Edit", "Write", "Glob", "Grep", "Bash"],
    },
    "reviewer": {
        "description": "Reviews the diff before the work is finished and reports defects.",
        "prompt": (
            "You review the current diff against the task. Report real defects "
            "with file and line, and scope creep beyond the task. Do not edit."
        ),
        "tools": ["Read", "Glob", "Grep", "Bash"],
    },
}


class JobRefused(ValueError):
    """The job is malformed or outside what this worker may touch."""


@dataclass
class Job:
    job_id: str
    repository: str
    task: str
    base_ref: str = "main"
    test_command: str = ""
    max_turns: int = DEFAULT_MAX_TURNS
    max_budget_usd: float = DEFAULT_MAX_BUDGET_USD
    requested_by: str = "DEVON"
    approval_id: str = ""

    @property
    def branch(self) -> str:
        return BRANCH_PREFIX + self.job_id.lower()


@dataclass
class JobRecord:
    job: Dict[str, Any]
    state: str = "queued"
    created_at: str = field(default_factory=lambda: _now())
    updated_at: str = field(default_factory=lambda: _now())
    branch: str = ""
    commits: int = 0
    tests: Dict[str, Any] = field(default_factory=dict)
    agent: Dict[str, Any] = field(default_factory=dict)
    pull_request: Dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_job(raw: Dict[str, Any], *, allowed_repos: Sequence[str]) -> Job:
    """Refuse anything malformed before a directory is created or a token used."""
    if not isinstance(raw, dict):
        raise JobRefused("job must be an object")
    job_id = str(raw.get("job_id") or "")
    if not JOB_ID_RE.fullmatch(job_id):
        raise JobRefused("job_id must be 6 to 64 letters, digits, dash or underscore")
    repository = str(raw.get("repository") or "").strip()
    if not REPO_RE.fullmatch(repository):
        raise JobRefused("repository must be exact owner/name")
    if repository not in set(allowed_repos):
        raise JobRefused(f"repository is not allowlisted for the code worker: {repository}")
    task = str(raw.get("task") or "").strip()
    if len(task) < 20:
        raise JobRefused("task must say what to change, at least 20 characters")
    if len(task) > MAX_TASK_CHARS:
        raise JobRefused(f"task is longer than {MAX_TASK_CHARS} characters")
    base_ref = str(raw.get("base_ref") or "main").strip()
    if not REF_RE.fullmatch(base_ref) or ".." in base_ref or base_ref.startswith(BRANCH_PREFIX):
        raise JobRefused("base_ref is not a plain branch name")
    test_command = str(raw.get("test_command") or "").strip()
    if len(test_command) > 500 or "\n" in test_command:
        raise JobRefused("test_command must be one line of at most 500 characters")
    try:
        max_turns = int(raw.get("max_turns") or DEFAULT_MAX_TURNS)
        max_budget = float(raw.get("max_budget_usd") or DEFAULT_MAX_BUDGET_USD)
    except (TypeError, ValueError) as exc:
        raise JobRefused("max_turns and max_budget_usd must be numbers") from exc
    if not 1 <= max_turns <= 200:
        raise JobRefused("max_turns must be between 1 and 200")
    if not 0 < max_budget <= CEILING_MAX_BUDGET_USD:
        raise JobRefused(f"max_budget_usd must be above 0 and at most {CEILING_MAX_BUDGET_USD}")
    return Job(
        job_id=job_id,
        repository=repository,
        task=task,
        base_ref=base_ref,
        test_command=test_command,
        max_turns=max_turns,
        max_budget_usd=max_budget,
        requested_by=str(raw.get("requested_by") or "DEVON")[:120],
        approval_id=str(raw.get("approval_id") or "")[:120],
    )


Runner = Callable[..., subprocess.CompletedProcess]
QueryFn = Callable[..., AsyncIterator[Any]]
HttpFn = Callable[[str, str, Dict[str, str], Optional[Dict[str, Any]]], Awaitable[Dict[str, Any]]]


class CodeWorker:
    def __init__(
        self,
        *,
        github_token: str,
        allowed_repos: Sequence[str],
        jobs_dir: Path,
        query: Optional[QueryFn] = None,
        http: Optional[HttpFn] = None,
        run: Optional[Runner] = None,
        clone_url: Optional[Callable[[str], str]] = None,
        model: Optional[str] = None,
    ) -> None:
        self.github_token = github_token
        self.allowed_repos = list(allowed_repos)
        self.jobs_dir = Path(jobs_dir)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self._query = query
        self._http = http
        self._run = run or subprocess.run
        self._clone_url = clone_url or (lambda repo: f"https://github.com/{repo}.git")
        self.model = model

    # -- records -----------------------------------------------------------

    def _record_path(self, job_id: str) -> Path:
        return self.jobs_dir / f"{job_id}.json"

    def load(self, job_id: str) -> Optional[JobRecord]:
        if not JOB_ID_RE.fullmatch(job_id or ""):
            return None
        path = self._record_path(job_id)
        if not path.exists():
            return None
        return JobRecord(**json.loads(path.read_text(encoding="utf-8")))

    def _save(self, record: JobRecord) -> None:
        record.updated_at = _now()
        path = self._record_path(record.job["job_id"])
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(record.to_dict(), indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(path)

    def accept(self, raw: Dict[str, Any]) -> JobRecord:
        """Validate and record a job. The same job_id twice returns the first record."""
        job = validate_job(raw, allowed_repos=self.allowed_repos)
        existing = self.load(job.job_id)
        if existing is not None:
            if existing.job.get("task") != job.task or existing.job.get("repository") != job.repository:
                raise JobRefused("job_id was already used for a different job")
            return existing
        record = JobRecord(job=asdict(job), branch=job.branch)
        self._save(record)
        return record

    # -- the run -----------------------------------------------------------

    async def execute(self, job_id: str) -> JobRecord:
        record = self.load(job_id)
        if record is None:
            raise JobRefused(f"no job {job_id}")
        if record.state != "queued":
            return record
        job = Job(**record.job)
        workdir = Path(tempfile.mkdtemp(prefix=f"devon-code-{job.job_id}-"))
        try:
            record.state = "cloning"
            self._save(record)
            self._git(["clone", "--quiet", "--branch", job.base_ref, self._clone_url(job.repository), str(workdir)], cwd=None)
            self._git(["checkout", "--quiet", "-b", job.branch], cwd=workdir)
            self._git(["config", "user.name", "DEVON code worker"], cwd=workdir)
            self._git(["config", "user.email", "devon-code-worker@users.noreply.github.com"], cwd=workdir)
            base_sha = self._git(["rev-parse", "HEAD"], cwd=workdir).stdout.strip()

            record.state = "coding"
            self._save(record)
            record.agent = await self._run_agent(job, workdir)
            self._save(record)

            # Anything the agent left uncommitted is the worker's to commit, so
            # the pull request carries exactly what is on disk.
            if self._git(["status", "--porcelain"], cwd=workdir).stdout.strip():
                self._git(["add", "-A"], cwd=workdir)
                self._git(["commit", "--quiet", "-m", f"DEVON code job {job.job_id}: uncommitted work"], cwd=workdir)
            record.commits = int(
                self._git(["rev-list", "--count", f"{base_sha}..HEAD"], cwd=workdir).stdout.strip() or 0
            )
            if record.commits == 0:
                record.state = "no_change"
                record.error = "the agent finished without changing anything; nothing was pushed"
                self._save(record)
                return record

            record.state = "testing"
            self._save(record)
            record.tests = self._run_tests(job, workdir)
            self._save(record)

            record.state = "pushing"
            self._save(record)
            self._git(["push", "--quiet", self._clone_url(job.repository), f"HEAD:refs/heads/{job.branch}"], cwd=workdir, authed=True)
            record.pull_request = await self._open_draft(job, record)
            record.state = "done" if record.tests.get("passed") is not False else "done_tests_failing"
            self._save(record)
            return record
        except Exception as exc:  # the record is the answer; nothing is re-raised to the caller
            record.state = "failed"
            record.error = _scrub(f"{type(exc).__name__}: {exc}", self.github_token)[:2_000]
            self._save(record)
            return record
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    async def _run_agent(self, job: Job, workdir: Path) -> Dict[str, Any]:
        if self._query is None:
            raise RuntimeError("no agent is configured: install claude-agent-sdk")
        prompt = (
            f"Task from DEVON, approved by Tee (approval {job.approval_id or 'unstated'}):\n\n"
            f"{job.task}\n\n"
            f"The repository is {job.repository}, checked out at {job.base_ref} on branch {job.branch}. "
            + (f"The test command is: {job.test_command}" if job.test_command else "Find and run the project's tests.")
        )
        env = {
            # Blanked so a prompt injected through repository content finds no
            # GitHub credential and no worker key in the agent's environment.
            "GITHUB_TOKEN": "",
            "GH_TOKEN": "",
            "DEVON_CODE_WORKER_GITHUB_TOKEN": "",
            "DEVON_CODE_WORKER_KEY": "",
        }
        last: Dict[str, Any] = {}
        async for message in self._query(
            prompt=prompt,
            cwd=str(workdir),
            system_append=SYSTEM_APPEND,
            allowed_tools=AGENT_TOOLS,
            disallowed_tools=AGENT_DENIED,
            subagents=SUBAGENTS,
            max_turns=job.max_turns,
            max_budget_usd=job.max_budget_usd,
            model=self.model,
            env=env,
        ):
            if getattr(message, "subtype", None) is not None and hasattr(message, "is_error"):
                last = {
                    "subtype": message.subtype,
                    "is_error": bool(message.is_error),
                    "num_turns": getattr(message, "num_turns", None),
                    "total_cost_usd": getattr(message, "total_cost_usd", None),
                    "result": _scrub(str(getattr(message, "result", "") or ""), self.github_token)[:4_000],
                }
        if not last:
            raise RuntimeError("the agent ended without a result message")
        return last

    def _run_tests(self, job: Job, workdir: Path) -> Dict[str, Any]:
        if not job.test_command:
            return {"ran": False, "passed": None, "note": "no test_command was given, so the worker ran no tests"}
        proc = self._run(
            ["bash", "-lc", job.test_command],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=1_800,
            env=_child_env(),
        )
        output = _scrub((proc.stdout or "") + (proc.stderr or ""), self.github_token)
        return {
            "ran": True,
            "command": job.test_command,
            "exit_code": proc.returncode,
            "passed": proc.returncode == 0,
            "tail": output[-MAX_TEST_OUTPUT_CHARS:],
        }

    async def _open_draft(self, job: Job, record: JobRecord) -> Dict[str, Any]:
        if self._http is None:
            raise RuntimeError("no GitHub client is configured")
        tests = record.tests
        if tests.get("passed") is False:
            status = "TESTS FAILING"
        elif tests.get("ran"):
            status = "tests passed"
        else:
            status = "tests not run"
        title = f"DEVON: {job.task.splitlines()[0][:80]} [{status}]"
        body = "\n".join(
            [
                f"Opened by the DEVON code worker for job `{job.job_id}`, approval `{job.approval_id or 'unstated'}`.",
                "",
                "## Task",
                "",
                job.task,
                "",
                "## Tests, run by the worker after the agent stopped",
                "",
                f"Command: `{tests.get('command') or 'none given'}`, exit code `{tests.get('exit_code')}`.",
                "",
                "```",
                str(tests.get("tail") or tests.get("note") or ""),
                "```",
                "",
                "## Agent",
                "",
                f"Ended `{record.agent.get('subtype')}` after {record.agent.get('num_turns')} turns, "
                f"estimated cost ${record.agent.get('total_cost_usd')}.",
                "",
                "Draft on purpose. Nothing here reaches the base branch without a human.",
            ]
        )
        data = await self._http(
            "POST",
            f"/repos/{job.repository}/pulls",
            {"Authorization": f"Bearer {self.github_token}"},
            {"title": title, "head": job.branch, "base": job.base_ref, "body": body, "draft": True},
        )
        if not data.get("html_url") or not data.get("number"):
            raise RuntimeError("GitHub answered the pull request create without a number or url")
        return {"number": data["number"], "url": data["html_url"], "draft": data.get("draft", True)}

    def _git(self, args: List[str], *, cwd: Optional[Path], authed: bool = False) -> subprocess.CompletedProcess:
        prefix = ["git"]
        if authed and self.github_token:
            header = base64.b64encode(f"x-access-token:{self.github_token}".encode()).decode()
            prefix += ["-c", f"http.extraheader=AUTHORIZATION: basic {header}"]
        elif not authed and self.github_token and args and args[0] == "clone":
            # Cloning a private repository needs the token too, still per command.
            header = base64.b64encode(f"x-access-token:{self.github_token}".encode()).decode()
            prefix += ["-c", f"http.extraheader=AUTHORIZATION: basic {header}"]
        proc = self._run(
            prefix + args,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=600,
            env=_child_env(),
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"git {args[0]} failed: " + _scrub((proc.stderr or proc.stdout or "")[-1_000:], self.github_token)
            )
        return proc


def _child_env() -> Dict[str, str]:
    env = dict(os.environ)
    for key in ("GITHUB_TOKEN", "GH_TOKEN", "DEVON_CODE_WORKER_GITHUB_TOKEN", "DEVON_CODE_WORKER_KEY", "ANTHROPIC_API_KEY"):
        env.pop(key, None)
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def _scrub(text: str, secret: str) -> str:
    if secret:
        text = text.replace(secret, "[redacted]")
        text = text.replace(base64.b64encode(f"x-access-token:{secret}".encode()).decode(), "[redacted]")
    return text


def sdk_query() -> QueryFn:
    """Adapt claude_agent_sdk.query to the worker's call. Imported lazily."""
    from claude_agent_sdk import AgentDefinition, ClaudeAgentOptions, query

    async def run(*, prompt, cwd, system_append, allowed_tools, disallowed_tools, subagents,
                  max_turns, max_budget_usd, model, env):
        options = ClaudeAgentOptions(
            cwd=cwd,
            system_prompt={"type": "preset", "preset": "claude_code", "append": system_append},
            allowed_tools=allowed_tools,
            disallowed_tools=disallowed_tools,
            permission_mode="dontAsk",
            setting_sources=["project"],
            max_turns=max_turns,
            max_budget_usd=max_budget_usd,
            model=model,
            env=env,
            agents={
                name: AgentDefinition(description=spec["description"], prompt=spec["prompt"], tools=spec["tools"])
                for name, spec in subagents.items()
            },
        )
        async for message in query(prompt=prompt, options=options):
            yield message

    return run
