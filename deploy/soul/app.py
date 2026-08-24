"""Hosted DEVON Operator surface for the phone/browser lane.

The existing ``main.py`` remains the read-only DEVON Soul application.  This
module is only a deployment wrapper: it imports that application and mounts a
separate Operator capability whose commands execute inside a Vercel Sandbox
microVM, never inside the DEVON Soul function process.

Load-bearing boundaries:
- DEVON Soul remains read-only and does not execute subprocesses.
- Operator commands run only in an isolated Sandbox workspace.
- Production environment variables are never forwarded into the Sandbox.
- The Sandbox receives no GitHub write credential in v1.
- Browser access uses the existing DEVON console gate and SameSite cookie.
"""

from __future__ import annotations

import os
import posixpath
import re
from pathlib import Path
from typing import Any

from fastapi import Cookie, Header, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, HTMLResponse
from vercel.headers import set_headers
from vercel.sandbox import Sandbox

from main import TOKEN_COOKIE, _presented, _require, app

ROOT = Path(__file__).resolve().parent
TERMINAL = ROOT / "terminal.html"
WORKSPACE_ROOT = "/vercel/sandbox"
META_REPO_URL = "https://github.com/tdveal74-cell/Meta-Supreme-Apex-Genesis-.git"
META_REPO_REF = "main"
MAX_COMMAND_CHARS = 8_000
MAX_OUTPUT_CHARS = 1_000_000
CWD_MARKER = "__DEVON_CWD__="
SNAPSHOT_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,256}$")


@app.middleware("http")
async def register_vercel_request_context(request: Request, call_next):
    """Expose Vercel's per-request OIDC context to the Python SDK."""
    set_headers(request.headers)
    return await call_next(request)


def _operator_require(
    authorization: str | None,
    t: str | None,
    cookie: str | None,
) -> None:
    # v1 deliberately reuses the already-established browser gate.  The shell
    # receives no production credentials and cannot write GitHub, so possession
    # of this gate buys an isolated disposable workspace, not estate access.
    _require(authorization, t, cookie)


def _terminal_door(reason: str = "") -> str:
    note = f'<p class="why">{reason}</p>' if reason else ""
    return TERMINAL_DOOR_HTML.replace("{{NOTE}}", note)


TERMINAL_DOOR_HTML = """<!doctype html><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="referrer" content="no-referrer">
<title>DEVON Operator</title>
<style>
 :root{color-scheme:dark}
 *{box-sizing:border-box}
 body{margin:0;min-height:100vh;display:grid;place-items:center;background:#05080c;
      color:#e8edf2;font:15px/1.6 ui-sans-serif,system-ui,-apple-system,sans-serif;padding:24px}
 main{width:100%;max-width:28rem}
 .eyebrow{font-size:11px;letter-spacing:.24em;color:#d4a017;font-weight:700;margin:0 0 8px}
 h1{font-size:25px;letter-spacing:-.02em;margin:0 0 8px}
 p{margin:0 0 18px;color:#93a6b5}
 p.why{color:#d4a017;border-left:2px solid #d4a017;padding-left:10px;font-size:13px}
 label{display:block;font-size:10px;letter-spacing:.18em;color:#6f8493;margin:0 0 6px}
 input{width:100%;padding:13px 12px;background:#0b141b;color:#e8edf2;border:1px solid #22384a;
       border-radius:8px;font:14px ui-monospace,SFMono-Regular,Menlo,monospace}
 input:focus{outline:none;border-color:#d4a017}
 button{width:100%;margin-top:10px;padding:14px;border:1px solid #d4a017;border-radius:8px;
        background:#d4a017;color:#080b0f;font:700 12px/1 ui-sans-serif,system-ui,sans-serif;
        letter-spacing:.16em;cursor:pointer}
 .note{margin-top:16px;font-size:12px;color:#5e7484}
</style>
<main>
 <p class="eyebrow">DEVON · OPERATOR</p>
 <h1>Browser Terminal</h1>
 {{NOTE}}
 <p>Paste the same DEVON console token you already use. No terminal app is required on this device.</p>
 <form id="f" autocomplete="off">
  <label for="t">DEVON CONSOLE TOKEN</label>
  <input id="t" type="password" inputmode="text" autocapitalize="off" autocorrect="off"
         spellcheck="false" placeholder="Paste token">
  <button type="submit">OPEN TERMINAL</button>
 </form>
 <p class="note">Commands execute in an isolated cloud workspace. No production secrets or GitHub write credential are injected.</p>
</main>
<script>
document.getElementById('f').addEventListener('submit', function (e) {
  e.preventDefault();
  var v = (document.getElementById('t').value || '').trim();
  if (!v) return;
  try { localStorage.setItem('devon.soul.token', v); } catch (err) {}
  var secure = location.protocol === 'https:' ? '; Secure' : '';
  document.cookie = 'devon_console=' + encodeURIComponent(v) +
                    '; path=/; max-age=31536000; SameSite=Strict' + secure;
  location.href = '/terminal';
});
</script>"""


def _normalize_cwd(value: object) -> str:
    raw = str(value or WORKSPACE_ROOT).strip() or WORKSPACE_ROOT
    if not raw.startswith("/"):
        raw = posixpath.join(WORKSPACE_ROOT, raw)
    normalized = posixpath.normpath(raw)
    if normalized != WORKSPACE_ROOT and not normalized.startswith(WORKSPACE_ROOT + "/"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="working directory must stay inside the DEVON sandbox workspace",
        )
    return normalized


def _snapshot_id(value: object) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    if not candidate:
        return None
    if not SNAPSHOT_RE.fullmatch(candidate):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="snapshot id is malformed",
        )
    return candidate


def _read_result_field(result: Any, name: str, default: Any = "") -> Any:
    value = getattr(result, name, default)
    if callable(value):
        value = value()
    return value


def _bounded_output(value: object) -> tuple[str, bool]:
    text = "" if value is None else str(value)
    if len(text) <= MAX_OUTPUT_CHARS:
        return text, False
    return text[:MAX_OUTPUT_CHARS] + "\n[DEVON output truncated]\n", True


def _extract_cwd(stdout: str, fallback: str) -> tuple[str, str]:
    lines = stdout.splitlines(keepends=True)
    resolved = fallback
    kept: list[str] = []
    for line in lines:
        stripped = line.rstrip("\r\n")
        if stripped.startswith(CWD_MARKER):
            candidate = stripped[len(CWD_MARKER) :].strip()
            try:
                resolved = _normalize_cwd(candidate)
            except HTTPException:
                resolved = fallback
            continue
        kept.append(line)
    return "".join(kept), resolved


def _snapshot_value(snapshot: Any) -> str:
    for name in ("snapshot_id", "id"):
        value = getattr(snapshot, name, None)
        if callable(value):
            value = value()
        if value:
            return str(value)
    if isinstance(snapshot, dict):
        for name in ("snapshot_id", "snapshotId", "id"):
            if snapshot.get(name):
                return str(snapshot[name])
    raise RuntimeError("sandbox snapshot returned no id")


def _fresh_sandbox() -> Any:
    return Sandbox.create(
        runtime="python3.13",
        source={
            "type": "git",
            "url": META_REPO_URL,
            "revision": META_REPO_REF,
            "depth": 1,
        },
    )


def _restored_sandbox(snapshot_id: str) -> Any:
    return Sandbox.create(
        runtime="python3.13",
        source={"type": "snapshot", "snapshot_id": snapshot_id},
    )


def _stop_quietly(sandbox: Any) -> None:
    try:
        stop = getattr(sandbox, "stop", None)
        if callable(stop):
            stop()
    except Exception:
        pass


@app.get("/terminal", include_in_schema=False)
async def operator_terminal(
    authorization: str | None = Header(default=None),
    t: str | None = Query(default=None),
    devon_console: str | None = Cookie(default=None),
):
    """Serve the browser terminal only to a caller through the DEVON gate."""
    if not TERMINAL.exists():
        raise HTTPException(status_code=404, detail="No terminal asset deployed.")
    try:
        _operator_require(authorization, t, devon_console)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            why = "DEVON's console gate is not configured on the host."
        elif _presented(authorization, t, devon_console):
            why = "That DEVON token was refused."
        else:
            why = "Sign in once to open the Operator terminal."
        return HTMLResponse(_terminal_door(why), status_code=exc.status_code)

    response = FileResponse(TERMINAL, media_type="text/html")
    # Direct ?t= visits must become ordinary cookie-authenticated API calls
    # after the page loads, just like the existing DEVON door flow.
    if t and t.strip():
        response.set_cookie(
            TOKEN_COOKIE,
            t.strip(),
            max_age=31_536_000,
            httponly=False,
            secure=True,
            samesite="strict",
            path="/",
        )
    return response


@app.get("/api/v1/operator-terminal/status")
async def operator_terminal_status(
    authorization: str | None = Header(default=None),
    t: str | None = Query(default=None),
    devon_console: str | None = Cookie(default=None),
):
    _operator_require(authorization, t, devon_console)
    return {
        "status": "ready",
        "mode": "isolated-vercel-sandbox",
        "workspace": WORKSPACE_ROOT,
        "repository": "tdveal74-cell/Meta-Supreme-Apex-Genesis-",
        "ref": META_REPO_REF,
        "production_secrets_injected": False,
        "github_write_connected": False,
        "devon_core_executes": False,
    }


@app.post("/api/v1/operator-terminal/command")
async def operator_terminal_command(
    request: Request,
    authorization: str | None = Header(default=None),
    t: str | None = Query(default=None),
    devon_console: str | None = Cookie(default=None),
):
    """Execute one shell command inside an isolated snapshot-backed Sandbox."""
    _operator_require(authorization, t, devon_console)
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

    cwd = _normalize_cwd(body.get("cwd"))
    reset = bool(body.get("reset"))
    previous_snapshot = None if reset else _snapshot_id(body.get("snapshot_id"))

    sandbox = None
    try:
        sandbox = (
            _restored_sandbox(previous_snapshot)
            if previous_snapshot
            else _fresh_sandbox()
        )
        # Bash lives *inside the microVM*.  This is intentionally a real shell
        # rather than the host-side argv-only bridge from v1.  No production
        # environment or host filesystem is forwarded to it.
        import shlex

        script = (
            f"cd -- {shlex.quote(cwd)} || exit 74\n"
            f"{command}\n"
            "rc=$?\n"
            f"printf '\\n{CWD_MARKER}%s\\n' \"$PWD\"\n"
            "exit $rc\n"
        )
        result = sandbox.run_command("bash", ["-lc", script])
        stdout_raw = _read_result_field(result, "stdout", "")
        stderr_raw = _read_result_field(result, "stderr", "")
        exit_code = _read_result_field(result, "exit_code", None)
        if exit_code is None:
            exit_code = _read_result_field(result, "returncode", 1)

        stdout_text, resolved_cwd = _extract_cwd(str(stdout_raw or ""), cwd)
        stdout, stdout_truncated = _bounded_output(stdout_text)
        stderr, stderr_truncated = _bounded_output(stderr_raw)

        snapshot = sandbox.snapshot()
        next_snapshot = _snapshot_value(snapshot)
        sandbox = None  # snapshot finalizes/stops the session

        return {
            "command": command,
            "cwd": resolved_cwd,
            "exit_code": int(exit_code),
            "stdout": stdout,
            "stderr": stderr,
            "snapshot_id": next_snapshot,
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
        if sandbox is not None:
            _stop_quietly(sandbox)
