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

The GitHub token is kept away from the agent as far as one Unix user allows,
and no further. It is blanked in the agent's environment, handed to git per
command as a header rather than written to any config, and the push and the pull
request are made from a SECOND, pristine clone the agent never touched, with
hooks and local config disabled, so an agent that edited `.git/hooks` or
`.git/config` in its own tree gains nothing at push time (a critic reproduced
that route on 2026-10-24 and it is closed). What stays open: the agent's shell
runs as the same user as this worker, so it can read this process's environment
through /proc. The binding limits are therefore the token's own scope (a fine
grained token with contents and pull request rights on the allowlisted
repositories only), the per job dollar limit, and allowlisting only repositories
whose content is trusted. Running the agent as a separate user is stage two of
the box build.

Everything that touches the outside world is injected (`query`, `run`, `http`),
so the whole flow runs in tests against a local bare repository and a mock
GitHub with no network and no model.
"""

from __future__ import annotations

import asyncio
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
TEST_TIMEOUT_SECONDS = 1_800
GIT_TIMEOUT_SECONDS = 600
_EMPTY_HOOKS = tempfile.mkdtemp(prefix="devon-no-hooks-")
DEFAULT_MAX_TURNS = 60
DEFAULT_MAX_BUDGET_USD = 5.0
CEILING_MAX_BUDGET_USD = 50.0
BRANCH_PREFIX = "devon/code-"
IN_FLIGHT_STATES = ("cloning", "coding", "testing", "pushing")

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
        return BRANCH_PREFIX + self.job_id


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
    pushed: bool = False
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

    def reconcile_on_start(self) -> List[str]:
        """Close every job a previous process left mid-flight.

        A worker that died between states left a record that no re-POST would
        ever move, because accept returns the existing record and execute runs
        only from queued. Those jobs are marked failed with the reason, so the
        caller can read it and submit a fresh job id. Nothing is retried on its
        own: a half finished clone or push is not safe to resume blind.
        """
        closed: List[str] = []
        for path in sorted(self.jobs_dir.glob("*.json")):
            record = JobRecord(**json.loads(path.read_text(encoding="utf-8")))
            if record.state in IN_FLIGHT_STATES:
                record.error = f"the worker restarted while this job was {record.state}; submit a new job"
                record.state = "failed"
                self._save(record)
                closed.append(record.job["job_id"])
        return closed

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
            await self._git(["clone", "--quiet", "--branch", job.base_ref, self._clone_url(job.repository), str(workdir)], cwd=None)
            await self._git(["checkout", "--quiet", "-b", job.branch], cwd=workdir)
            await self._git(["config", "user.name", "DEVON code worker"], cwd=workdir)
            await self._git(["config", "user.email", "devon-code-worker@users.noreply.github.com"], cwd=workdir)
            base_sha = (await self._git(["rev-parse", "HEAD"], cwd=workdir)).stdout.strip()

            record.state = "coding"
            self._save(record)
            record.agent = await self._run_agent(job, workdir)
            self._save(record)

            # Anything the agent left uncommitted is the worker's to commit, so
            # the pull request carries exactly what is on disk.
            if (await self._git(["status", "--porcelain"], cwd=workdir)).stdout.strip():
                await self._git(["add", "-A"], cwd=workdir)
                await self._git(["commit", "--quiet", "-m", f"DEVON code job {job.job_id}: uncommitted work"], cwd=workdir)
            record.commits = int(
                (await self._git(["rev-list", "--count", f"{base_sha}..HEAD"], cwd=workdir)).stdout.strip() or 0
            )
            if record.commits == 0:
                record.state = "no_change"
                record.error = "the agent finished without changing anything; nothing was pushed"
                self._save(record)
                return record

            record.state = "testing"
            self._save(record)
            record.tests = await self._run_tests(job, workdir)
            self._save(record)

            record.state = "pushing"
            self._save(record)
            await self._push_from_pristine_clone(job, workdir)
            record.pushed = True
            self._save(record)
            try:
                record.pull_request = await self._open_draft(job, record)
            except Exception as exc:
                # The branch is on the remote and nothing here can undo that, so
                # the record says so instead of reading as a job that did nothing.
                record.state = "pushed_pr_failed"
                record.error = _scrub(f"branch {job.branch} was pushed but the pull request was not opened: {exc}", self.github_token)[:2_000]
                self._save(record)
                return record
            record.state = _final_state(record)
            self._save(record)
            return record
        except Exception as exc:  # the record is the answer; nothing is re-raised to the caller
            record.state = "failed"
            record.error = _scrub(f"{type(exc).__name__}: {exc}", self.github_token)[:2_000]
            self._save(record)
            return record
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    async def _push_from_pristine_clone(self, job: Job, workdir: Path) -> None:
        """Push the agent's commits from a clone the agent never touched.

        The agent had Write and Bash in `workdir`, so its `.git/hooks` and
        `.git/config` are agent controlled: a pre-push hook sees the token in
        GIT_CONFIG_PARAMETERS and an `insteadOf` rewrite sends the authed push
        elsewhere. A fresh local clone copies the objects and refs only, and the
        push runs there with hooks pointed at an empty directory, system and
        global config ignored, and the destination given as a literal URL.
        """
        pushdir = Path(tempfile.mkdtemp(prefix=f"devon-push-{job.job_id}-"))
        try:
            await self._git(["clone", "--quiet", "--no-hardlinks", "--branch", job.branch, str(workdir), str(pushdir)], cwd=None)
            await self._git(
                ["push", "--quiet", self._clone_url(job.repository), f"HEAD:refs/heads/{job.branch}"],
                cwd=pushdir,
                authed=True,
            )
        finally:
            shutil.rmtree(pushdir, ignore_errors=True)

    async def _run_agent(self, job: Job, workdir: Path) -> Dict[str, Any]:
        if self._query is None:
            raise RuntimeError("no agent is configured: install claude-agent-sdk")
        # Secrets the agent must not carry. os.environ is the server process
        # environment; the agent's Bash runs as the same user and could read
        # /proc for the parent's original block, which is why this is a
        # reduction and not a wall. The docstring says so.
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

    async def _run_tests(self, job: Job, workdir: Path) -> Dict[str, Any]:
        if not job.test_command:
            return {"ran": False, "passed": None, "note": "no test_command was given, so the worker ran no tests"}
        try:
            proc = await asyncio.to_thread(
                self._run,
                ["bash", "-lc", job.test_command],
                cwd=str(workdir),
                capture_output=True,
                text=True,
                timeout=TEST_TIMEOUT_SECONDS,
                env=_child_env(),
            )
        except subprocess.TimeoutExpired as exc:
            # A hung test run is a test result, not a worker fault: the work is
            # still pushed and the draft says the tests never finished.
            partial = _scrub(_text(exc.stdout) + _text(exc.stderr), self.github_token)
            return {
                "ran": True,
                "command": job.test_command,
                "exit_code": None,
                "passed": False,
                "timed_out": True,
                "tail": (partial + f"\n[the worker stopped the tests after {TEST_TIMEOUT_SECONDS}s]")[-MAX_TEST_OUTPUT_CHARS:],
            }
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
        if tests.get("timed_out"):
            status = "TESTS TIMED OUT"
        elif tests.get("passed") is False:
            status = "TESTS FAILING"
        elif tests.get("ran"):
            status = "tests passed"
        else:
            status = "tests not run"
        if record.agent.get("is_error") or record.agent.get("subtype") != "success":
            status += f", AGENT ENDED {record.agent.get('subtype') or 'without a result'}"
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

    async def _git(self, args: List[str], *, cwd: Optional[Path], authed: bool = False) -> subprocess.CompletedProcess:
        prefix = ["git"]
        remote_clone = not authed and args and args[0] == "clone" and not args[-2].startswith("/")
        if self.github_token and (authed or remote_clone):
            # The token rides on the one command that needs it, as a header,
            # never into any config file.
            header = base64.b64encode(f"x-access-token:{self.github_token}".encode()).decode()
            prefix += ["-c", f"http.extraheader=AUTHORIZATION: basic {header}"]
        if authed:
            # Hooks and local config in the pushing clone are inert: hooksPath
            # points at an empty directory, and system and global config are not
            # read, so no insteadOf rewrite can redirect the authed push.
            prefix += ["-c", f"core.hooksPath={_EMPTY_HOOKS}"]
        env = _child_env()
        if authed:
            env["GIT_CONFIG_NOSYSTEM"] = "1"
            env["GIT_CONFIG_GLOBAL"] = os.devnull
        proc = await asyncio.to_thread(
            self._run,
            prefix + args,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            env=env,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"git {args[0]} failed: " + _scrub((proc.stderr or proc.stdout or "")[-1_000:], self.github_token)
            )
        return proc


def _final_state(record: JobRecord) -> str:
    """Only a clean agent run with passing or unrun tests is plain done."""
    agent_ok = record.agent.get("subtype") == "success" and not record.agent.get("is_error")
    if not agent_ok:
        return "done_agent_error"
    if record.tests.get("passed") is False:
        return "done_tests_failing"
    return "done"


def _text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value or "")


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
