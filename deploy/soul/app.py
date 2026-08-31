"""Hosted DEVON Operator surface for the phone/browser lane.

The existing ``main.py`` remains the read-only DEVON Soul application. This
module is only a deployment wrapper: it imports that application and mounts a
separate Operator capability whose commands execute inside a Vercel Sandbox
microVM, never inside the DEVON Soul function process.

Load-bearing boundaries:
- DEVON Soul remains read-only and does not execute subprocesses.
- Operator commands run only in an isolated Sandbox workspace.
- Production environment variables are never forwarded into the Sandbox.
- The Sandbox receives no GitHub write credential in v1.
- Browser access uses the existing DEVON console gate and SameSite cookie.
- The Sandbox base directory and the Meta Git worktree are discovered and
  verified independently. A Sandbox cwd is never assumed to be a Git repo.
- Clean detached GitSource worktrees are attached to local ``main`` only after
  an explicit ``origin/main`` tracking ref is fetched. Dirty detached worktrees
  are preserved instead of being reset or switched.
"""

from __future__ import annotations

import posixpath
import re
from pathlib import Path
from typing import Any

from fastapi import Cookie, Header, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse
from main import _presented, _require, app
from vercel import sandbox as vercel_sandbox
from vercel.headers import set_headers
from vercel.sandbox import GitSource

ROOT = Path(__file__).resolve().parent
TERMINAL = ROOT / "terminal.html"
LEGACY_WORKSPACE_ALIASES = frozenset(
    {"/vercel/sandbox", "/vercel", "/home/vercel-sandbox"}
)
META_REPO_URL = "https://github.com/tdveal74-cell/Meta-Supreme-Apex-Genesis-.git"
META_REPO_REF = "main"
META_REPO_DIRNAME = "devon-meta"
MAX_COMMAND_CHARS = 8_000
MAX_OUTPUT_CHARS = 1_000_000
CWD_MARKER = "__DEVON_CWD__="
WORKSPACE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,256}$")


def _assert_sandbox_sdk_contract() -> None:
    """Fail deployment import if the pinned Sandbox API drifts again."""
    missing = [
        name
        for name in ("create_sandbox", "resume_sandbox")
        if not callable(getattr(vercel_sandbox, name, None))
    ]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(f"Vercel Sandbox SDK contract missing: {joined}")


_assert_sandbox_sdk_contract()


@app.middleware("http")
async def register_vercel_request_context(request: Request, call_next):
    """Expose Vercel's per-request OIDC context to the Python SDK."""
    set_headers(request.headers)
    return await call_next(request)


def _operator_require(
    authorization: str | None,
    cookie: str | None,
) -> None:
    # v1 deliberately reuses the already-established browser gate. The shell
    # receives no production credentials and cannot write GitHub, so possession
    # of this gate buys an isolated workspace, not estate access. Query param
    # t is never accepted as auth (cookie / sessionStorage / header only).
    _require(authorization, cookie)


def _terminal_door(reason: str = "") -> str:
    note = f'<p class="why">{reason}</p>' if reason else ""
    return TERMINAL_DOOR_HTML.replace("{{NOTE}}", note)


TERMINAL_DOOR_HTML = """<!doctype html><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="referrer" content="no-referrer">
<title>DEVON Operator</title>
<style>
 :root{color-scheme:dark;--navy:#0A1628;--amber:#D4A017;--surface:#F8F5F0}
 *{box-sizing:border-box}
 html,body{margin:0;overflow-x:hidden}
 body{min-height:100dvh;min-height:100vh;display:flex;align-items:flex-start;
      justify-content:flex-start;background:var(--navy);color:var(--surface);
      font:15px/1.5 ui-sans-serif,system-ui,-apple-system,sans-serif;
      padding:max(16px,env(safe-area-inset-top,0px)) 16px 24px}
 main{width:100%;max-width:26rem}
 h1{font-size:12px;letter-spacing:.24em;color:var(--amber);margin:0 0 8px;font-weight:700}
 p{margin:0 0 14px;color:#93A6B5;font-size:14px}
 p.why{color:var(--amber);border-left:2px solid var(--amber);padding-left:10px;font-size:13px}
 label{display:block;font-size:11px;letter-spacing:.18em;color:#8A9BAE;margin:0 0 6px}
 input{width:100%;min-height:44px;padding:12px;background:#0C1A2E;color:var(--surface);
       border:1px solid #1E3348;border-radius:6px;font:14px ui-monospace,monospace}
 input:focus{outline:none;border-color:var(--amber)}
 button{width:100%;min-height:44px;margin-top:10px;padding:12px;border:1px solid var(--amber);
        border-radius:6px;background:transparent;color:var(--amber);
        font:700 12px/1 ui-sans-serif,system-ui,sans-serif;letter-spacing:.18em;
        cursor:pointer}
 button:active{background:#0C1A2E}
 .note{margin-top:14px;font-size:12px;color:#8A9BAE}
</style>
<main>
 <h1>DEVON OPERATOR</h1>
 {{NOTE}}
 <p>Paste the same console token you already use. It is kept in this browser and nowhere else.</p>
 <form id="f" autocomplete="off">
  <label for="t">CONSOLE TOKEN</label>
  <input id="t" type="password" inputmode="text" autocapitalize="off" autocorrect="off"
         spellcheck="false" placeholder="CONSOLE_TOKEN from the host">
  <button type="submit">OPEN TERMINAL</button>
 </form>
 <p class="note">Commands execute in an isolated cloud workspace. No production secrets or GitHub write credential are injected.</p>
</main>
<script>
document.getElementById('f').addEventListener('submit', function (e) {
  e.preventDefault();
  var v = (document.getElementById('t').value || '').trim();
  if (!v) return;
  try { sessionStorage.setItem('devon.soul.token', v); } catch (err) {}
  try { localStorage.setItem('devon.soul.token', v); } catch (err) {}
  var secure = location.protocol === 'https:' ? '; Secure' : '';
  document.cookie = 'devon_console=' + encodeURIComponent(v) +
                    '; path=/; max-age=31536000; SameSite=Strict' + secure;
  location.href = '/terminal';
});
</script>"""


def _absolute_directory(value: object, *, label: str) -> str:
    candidate = posixpath.normpath(str(value or "").strip())
    if not candidate.startswith("/"):
        raise RuntimeError(f"{label} must be an absolute directory")
    return candidate


def _inside(path: str, root: str) -> bool:
    return path == root or path.startswith(root + "/")


def _normalize_cwd(value: object, repo_root: str, sandbox_root: str) -> str:
    """Resolve browser cwd while confining it to the verified Meta worktree."""
    raw = str(value or "").strip()
    # Earlier terminal versions cached host-shaped paths. They are compatibility
    # aliases only. The real worktree is verified on every command.
    if not raw or raw == sandbox_root or raw in LEGACY_WORKSPACE_ALIASES:
        return repo_root
    if not raw.startswith("/"):
        raw = posixpath.join(repo_root, raw)
    normalized = posixpath.normpath(raw)
    if not _inside(normalized, repo_root):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="working directory must stay inside the DEVON Meta worktree",
        )
    return normalized


def _workspace_id(value: object) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    if not candidate:
        return None
    if not WORKSPACE_ID_RE.fullmatch(candidate):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="workspace id is malformed",
        )
    return candidate


def _bounded_output(value: object) -> tuple[str, bool]:
    text = "" if value is None else str(value)
    if len(text) <= MAX_OUTPUT_CHARS:
        return text, False
    return text[:MAX_OUTPUT_CHARS] + "\n[DEVON output truncated]\n", True


def _extract_cwd(
    stdout: str,
    fallback: str,
    repo_root: str,
    sandbox_root: str,
) -> tuple[str, str]:
    lines = stdout.splitlines(keepends=True)
    resolved = fallback
    kept: list[str] = []
    for line in lines:
        stripped = line.rstrip("\r\n")
        if stripped.startswith(CWD_MARKER):
            candidate = stripped[len(CWD_MARKER) :].strip()
            try:
                resolved = _normalize_cwd(candidate, repo_root, sandbox_root)
            except HTTPException:
                resolved = fallback
            continue
        kept.append(line)
    return "".join(kept), resolved


async def _sandbox_root(sandbox: Any) -> str:
    """Discover the live Sandbox base directory, with a pwd fallback."""
    reported = getattr(sandbox, "cwd", None)
    if callable(reported):
        reported = reported()
    if reported:
        return _absolute_directory(reported, label="sandbox cwd")

    probe = await sandbox.run_process("pwd", capture_output=True)
    if int(probe.returncode) != 0:
        raise RuntimeError("sandbox did not report a working directory and pwd failed")
    lines = str(probe.stdout or "").strip().splitlines()
    if not lines:
        raise RuntimeError("sandbox did not report a working directory and pwd was empty")
    return _absolute_directory(lines[-1], label="sandbox pwd")


async def _git_toplevel(sandbox: Any, candidate: str) -> str | None:
    """Return a verified Git toplevel for candidate, or None when it is not Git."""
    probe = await sandbox.run_process(
        "git",
        ["-C", candidate, "rev-parse", "--show-toplevel"],
        capture_output=True,
    )
    if int(probe.returncode) != 0:
        return None
    lines = str(probe.stdout or "").strip().splitlines()
    if not lines:
        return None
    return _absolute_directory(lines[-1], label="git toplevel")


async def _git_branch(sandbox: Any, repo_root: str) -> str | None:
    """Return the current local branch, or None when HEAD is detached."""
    probe = await sandbox.run_process(
        "git",
        ["-C", repo_root, "symbolic-ref", "--quiet", "--short", "HEAD"],
        capture_output=True,
    )
    if int(probe.returncode) != 0:
        return None
    lines = str(probe.stdout or "").strip().splitlines()
    return lines[-1].strip() if lines else None


async def _ensure_main_branch(sandbox: Any, repo_root: str) -> tuple[str, bool]:
    """Attach a clean detached worktree to tracked main without losing state."""
    current = await _git_branch(sandbox, repo_root)
    if current:
        return current, False

    dirty = await sandbox.run_process(
        "git",
        ["-C", repo_root, "status", "--porcelain"],
        capture_output=True,
    )
    if int(dirty.returncode) != 0:
        raise RuntimeError("could not inspect detached Meta worktree state")
    if str(dirty.stdout or "").strip():
        return "detached", False

    # Preserve the detached commit before moving the worktree. This protects
    # commits that GitSource may have materialized outside any local branch.
    head = await sandbox.run_process(
        "git",
        ["-C", repo_root, "rev-parse", "HEAD"],
        capture_output=True,
    )
    if int(head.returncode) != 0:
        raise RuntimeError("could not resolve detached Meta HEAD")
    head_lines = str(head.stdout or "").strip().splitlines()
    if not head_lines:
        raise RuntimeError("detached Meta HEAD was empty")
    head_sha = head_lines[-1].strip()
    recovery_branch = f"devon/recovery-{head_sha[:12]}"
    recovery_ref = f"refs/heads/{recovery_branch}"
    recovery_exists = await sandbox.run_process(
        "git",
        ["-C", repo_root, "show-ref", "--verify", "--quiet", recovery_ref],
        capture_output=True,
    )
    if int(recovery_exists.returncode) != 0:
        preserved = await sandbox.run_process(
            "git",
            ["-C", repo_root, "branch", recovery_branch, head_sha],
            capture_output=True,
        )
        if int(preserved.returncode) != 0:
            detail = str(
                preserved.stderr or preserved.stdout or "git branch failed"
            ).strip()
            raise RuntimeError(
                f"could not preserve detached Meta HEAD: {detail[-2_000:]}"
            )

    # Vercel GitSource can deliver a shallow checkout where the object at
    # refs/remotes/origin/main exists but Git has no fetch/tracking metadata for
    # origin/main. Install the exact refspec and fetch it unconditionally.
    fetch_refspec = "+refs/heads/main:refs/remotes/origin/main"
    configured = await sandbox.run_process(
        "git",
        ["-C", repo_root, "config", "remote.origin.fetch", fetch_refspec],
        capture_output=True,
    )
    if int(configured.returncode) != 0:
        detail = str(
            configured.stderr or configured.stdout or "git config failed"
        ).strip()
        raise RuntimeError(
            f"could not configure origin/main tracking: {detail[-2_000:]}"
        )

    fetched = await sandbox.run_process(
        "git",
        [
            "-C",
            repo_root,
            "fetch",
            "--depth",
            "1",
            "origin",
            fetch_refspec,
        ],
        capture_output=True,
    )
    if int(fetched.returncode) != 0:
        detail = str(fetched.stderr or fetched.stdout or "git fetch failed").strip()
        raise RuntimeError(f"could not resolve origin/main: {detail[-2_000:]}")

    remote_main = await sandbox.run_process(
        "git",
        ["-C", repo_root, "rev-parse", "--verify", "refs/remotes/origin/main"],
        capture_output=True,
    )
    if int(remote_main.returncode) != 0:
        raise RuntimeError("origin/main fetch completed without a remote-tracking ref")

    local_main = await sandbox.run_process(
        "git",
        ["-C", repo_root, "show-ref", "--verify", "--quiet", "refs/heads/main"],
        capture_output=True,
    )
    if int(local_main.returncode) == 0:
        # Never overwrite a divergent local branch. A clean worktree does not
        # imply that a pre-existing local main has no unique commits.
        can_ff = await sandbox.run_process(
            "git",
            [
                "-C",
                repo_root,
                "merge-base",
                "--is-ancestor",
                "refs/heads/main",
                "refs/remotes/origin/main",
            ],
            capture_output=True,
        )
        if int(can_ff.returncode) != 0:
            return "detached", False
        switched = await sandbox.run_process(
            "git",
            ["-C", repo_root, "switch", "main"],
            capture_output=True,
        )
        if int(switched.returncode) == 0:
            switched = await sandbox.run_process(
                "git",
                ["-C", repo_root, "merge", "--ff-only", "refs/remotes/origin/main"],
                capture_output=True,
            )
    else:
        # Use the fully qualified ref. Do not rely on `--track origin/main`,
        # which is the exact operation that failed in authenticated production.
        switched = await sandbox.run_process(
            "git",
            [
                "-C",
                repo_root,
                "switch",
                "-c",
                "main",
                "refs/remotes/origin/main",
            ],
            capture_output=True,
        )

    if int(switched.returncode) != 0:
        detail = str(switched.stderr or switched.stdout or "git switch failed").strip()
        raise RuntimeError(
            f"could not attach detached worktree to main: {detail[-2_000:]}"
        )

    # Configure the upstream explicitly after branch creation so it does not
    # depend on whatever metadata GitSource happened to provide.
    for key, value in (
        ("branch.main.remote", "origin"),
        ("branch.main.merge", "refs/heads/main"),
    ):
        tracked = await sandbox.run_process(
            "git",
            ["-C", repo_root, "config", key, value],
            capture_output=True,
        )
        if int(tracked.returncode) != 0:
            detail = str(
                tracked.stderr or tracked.stdout or "git config failed"
            ).strip()
            raise RuntimeError(
                f"could not configure main upstream: {detail[-2_000:]}"
            )

    verified = await _git_branch(sandbox, repo_root)
    if verified != "main":
        raise RuntimeError("Meta worktree branch attach completed without local main")
    return verified, True


async def _repo_root(sandbox: Any, sandbox_root: str) -> tuple[str, bool]:
    """Find or create a verified Meta Git worktree inside the Sandbox."""
    direct = await _git_toplevel(sandbox, sandbox_root)
    if direct and _inside(direct, sandbox_root):
        return direct, False

    # GitSource checkout placement is not treated as a contract. Search only
    # inside the isolated Sandbox root and verify any hit with git itself.
    find_result = await sandbox.run_process(
        "find",
        [sandbox_root, "-maxdepth", "4", "-type", "d", "-name", ".git", "-print", "-quit"],
        capture_output=True,
    )
    if int(find_result.returncode) == 0:
        for line in str(find_result.stdout or "").splitlines():
            dotgit = posixpath.normpath(line.strip())
            candidate = posixpath.dirname(dotgit)
            if not candidate or not _inside(candidate, sandbox_root):
                continue
            verified = await _git_toplevel(sandbox, candidate)
            if verified and _inside(verified, sandbox_root):
                return verified, False

    target = posixpath.join(sandbox_root, META_REPO_DIRNAME)
    existing = await _git_toplevel(sandbox, target)
    if existing and _inside(existing, sandbox_root):
        return existing, False

    clone = await sandbox.run_process(
        "git",
        [
            "clone",
            "--depth",
            "1",
            "--branch",
            META_REPO_REF,
            "--single-branch",
            META_REPO_URL,
            target,
        ],
        cwd=sandbox_root,
        capture_output=True,
    )
    if int(clone.returncode) != 0:
        detail = str(clone.stderr or clone.stdout or "git clone failed").strip()
        detail = detail[-2_000:]
        raise RuntimeError(f"Meta repository bootstrap failed: {detail}")

    verified = await _git_toplevel(sandbox, target)
    if not verified or not _inside(verified, sandbox_root):
        raise RuntimeError("Meta repository bootstrap completed without a valid Git worktree")
    return verified, True


async def _fresh_sandbox():
    """Create the persistent workspace supported by Sandbox 0.4."""
    return await vercel_sandbox.create_sandbox(
        source=GitSource(url=META_REPO_URL, revision=META_REPO_REF),
        persistent=True,
    )


async def _resume_sandbox(workspace_id: str):
    return await vercel_sandbox.resume_sandbox(name=workspace_id)


async def _stop_quietly(sandbox: Any) -> None:
    try:
        await sandbox.stop()
    except Exception:
        pass


@app.get("/terminal", include_in_schema=False)
async def operator_terminal(
    authorization: str | None = Header(default=None),
    devon_console: str | None = Cookie(default=None),
):
    """Serve the browser terminal only to a caller through the DEVON gate."""
    if not TERMINAL.exists():
        raise HTTPException(status_code=404, detail="No terminal asset deployed.")
    try:
        _operator_require(authorization, devon_console)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            why = "DEVON's console gate is not configured on the host."
        elif _presented(authorization, devon_console):
            why = "That DEVON token was refused."
        else:
            why = "Sign in once to open the Operator terminal."
        return HTMLResponse(_terminal_door(why), status_code=exc.status_code)

    return FileResponse(TERMINAL, media_type="text/html")


@app.get("/api/v1/operator-terminal/status")
async def operator_terminal_status(
    authorization: str | None = Header(default=None),
    devon_console: str | None = Cookie(default=None),
):
    _operator_require(authorization, devon_console)
    return {
        "status": "ready",
        "mode": "isolated-vercel-sandbox",
        "workspace": "verified Meta Git worktree",
        "workspace_discovery": "git rev-parse, bounded .git search, verified clone fallback",
        "repository": "tdveal74-cell/Meta-Supreme-Apex-Genesis-",
        "ref": META_REPO_REF,
        "production_secrets_injected": False,
        "github_write_connected": False,
        "devon_core_executes": False,
        "sandbox_sdk_contract": "vercel-sandbox-0.4-module-api",
    }


@app.post("/api/v1/operator-terminal/command")
async def operator_terminal_command(
    request: Request,
    authorization: str | None = Header(default=None),
    devon_console: str | None = Cookie(default=None),
):
    """Execute one shell command inside an isolated persistent Sandbox."""
    _operator_require(authorization, devon_console)
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="request body must be JSON") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="request body must be an object")

    command = str(body.get("command") or "").strip()
    if not command:
        raise HTTPException(status_code=422, detail="command is empty")
    if len(command) > MAX_COMMAND_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"command exceeds {MAX_COMMAND_CHARS} characters",
        )

    requested_cwd = body.get("cwd")
    reset = bool(body.get("reset"))
    prior_workspace = _workspace_id(body.get("workspace_id") or body.get("snapshot_id"))
    if reset:
        prior_workspace = None

    sandbox = None
    stopped = False
    try:
        sandbox = (
            await _resume_sandbox(prior_workspace)
            if prior_workspace
            else await _fresh_sandbox()
        )
        sandbox_root = await _sandbox_root(sandbox)
        repo_root, repo_bootstrapped = await _repo_root(sandbox, sandbox_root)
        branch, branch_attached = await _ensure_main_branch(sandbox, repo_root)
        cwd = _normalize_cwd(requested_cwd, repo_root, sandbox_root)
        script = (
            f"{command}\n"
            "rc=$?\n"
            f"printf '\n{CWD_MARKER}%s\n' \"$PWD\"\n"
            "exit $rc\n"
        )
        result = await sandbox.run_process(
            "bash",
            ["-lc", script],
            cwd=cwd,
            capture_output=True,
        )
        stdout_text, resolved_cwd = _extract_cwd(
            str(result.stdout or ""), cwd, repo_root, sandbox_root
        )
        stdout, stdout_truncated = _bounded_output(stdout_text)
        stderr, stderr_truncated = _bounded_output(result.stderr or "")
        exit_code = int(result.returncode)
        next_workspace = str(sandbox.name)

        # Persistent sandboxes snapshot their filesystem on stop and resume from
        # that state on the next browser command. This is the v0.4 SDK contract.
        await sandbox.stop()
        stopped = True

        return {
            "command": command,
            "cwd": resolved_cwd,
            "workspace_root": repo_root,
            "sandbox_root": sandbox_root,
            "repo_bootstrapped": repo_bootstrapped,
            "branch": branch,
            "branch_attached": branch_attached,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "workspace_id": next_workspace,
            # Backward-compatible field for a terminal page cached before this hotfix.
            "snapshot_id": next_workspace,
            "workspace_reset": reset,
            "truncated": stdout_truncated or stderr_truncated,
            "github_write_connected": False,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"isolated operator sandbox failed: {type(exc).__name__}: {exc}",
        ) from exc
    finally:
        if sandbox is not None and not stopped:
            await _stop_quietly(sandbox)
