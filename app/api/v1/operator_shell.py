"""Interactive shell for the human operator, over WebSocket.

This is the operator's own terminal, not DEVON's. DEVON remains
execution-free and his gated command path (/operator/command) is
unchanged. This endpoint hands the HUMAN holding the operator key a real
PTY running bash on the API container: pipes, redirects, interactive
programs, the lot. It is deliberately not gated per-command because the
key holder is the same person the approval queue escalates to.

Protocol (all text frames):
  client -> {"type": "hello", "key": "...", "cols": 120, "rows": 32}
  server -> {"type": "ready", "shell": "/bin/bash", "cwd": "..."}
  client -> {"type": "input", "data": "ls -la\n"}
  client -> {"type": "resize", "cols": 100, "rows": 40}
  server -> {"type": "output", "data": "..."}
  server -> {"type": "exit", "code": 0}       (shell process ended)
  server -> {"type": "error", "message": "..."} then close (auth failures)

The socket closes with code 4401 on a bad key and 4400 on a malformed
hello. The bash process group is killed when the socket goes away.
"""

from __future__ import annotations

import asyncio
import fcntl
import json
import logging
import os
import pty
import shutil
import signal
import struct
import termios
from typing import Any, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.v1.operator import _bridge
from services.operator.bridge import OperatorError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/operator", tags=["DEVON Operator"])

_HELLO_TIMEOUT_SECONDS = 15.0
_MAX_INPUT_CHARS = 16_384
_MIN_DIM, _MAX_COLS, _MAX_ROWS = 2, 500, 300
_KILL_GRACE_SECONDS = 2.0


def _clamp(value: Any, fallback: int, upper: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(_MIN_DIM, min(number, upper))


def _set_winsize(fd: int, cols: int, rows: int) -> None:
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def _pick_shell() -> str:
    return shutil.which("bash") or "/bin/sh"


@router.websocket("/shell")
async def operator_shell(ws: WebSocket) -> None:
    await ws.accept()

    # -- authenticate -------------------------------------------------------
    try:
        raw = await asyncio.wait_for(ws.receive_text(), timeout=_HELLO_TIMEOUT_SECONDS)
        hello: Dict[str, Any] = json.loads(raw)
        if not isinstance(hello, dict):
            raise ValueError("hello must be a JSON object")
    except WebSocketDisconnect:
        return
    except (asyncio.TimeoutError, ValueError, json.JSONDecodeError):
        await ws.send_text(json.dumps({"type": "error", "message": "malformed hello"}))
        await ws.close(code=4400)
        return

    try:
        _bridge.authenticate(hello.get("key"))
    except OperatorError as exc:
        await ws.send_text(json.dumps({"type": "error", "message": str(exc)}))
        await ws.close(code=4401)
        return

    cols = _clamp(hello.get("cols"), 100, _MAX_COLS)
    rows = _clamp(hello.get("rows"), 30, _MAX_ROWS)

    # -- spawn the PTY ------------------------------------------------------
    shell = _pick_shell()
    master_fd, slave_fd = pty.openpty()
    _set_winsize(slave_fd, cols, rows)

    env = dict(os.environ)
    env["TERM"] = "xterm-256color"
    env.setdefault("HOME", str(_bridge.root))

    proc = await asyncio.create_subprocess_exec(
        shell,
        "-i",
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        cwd=str(_bridge.root),
        env=env,
        start_new_session=True,
    )
    os.close(slave_fd)

    loop = asyncio.get_running_loop()
    output_queue: asyncio.Queue[bytes] = asyncio.Queue()

    def _on_pty_readable() -> None:
        try:
            data = os.read(master_fd, 65_536)
        except OSError:
            data = b""
        if data:
            output_queue.put_nowait(data)
        else:
            loop.remove_reader(master_fd)
            output_queue.put_nowait(b"")  # EOF sentinel

    loop.add_reader(master_fd, _on_pty_readable)
    await ws.send_text(
        json.dumps({"type": "ready", "shell": shell, "cwd": str(_bridge.root)})
    )

    async def _pump_output() -> None:
        while True:
            chunk = await output_queue.get()
            if not chunk:
                code = await proc.wait()
                await ws.send_text(json.dumps({"type": "exit", "code": code}))
                return
            await ws.send_text(
                json.dumps(
                    {"type": "output", "data": chunk.decode("utf-8", errors="replace")}
                )
            )

    async def _pump_input() -> None:
        while True:
            message = await ws.receive_text()
            try:
                parsed = json.loads(message)
            except json.JSONDecodeError:
                continue
            kind = parsed.get("type")
            if kind == "input":
                data = str(parsed.get("data") or "")[:_MAX_INPUT_CHARS]
                if data:
                    os.write(master_fd, data.encode("utf-8", errors="replace"))
            elif kind == "resize":
                _set_winsize(
                    master_fd,
                    _clamp(parsed.get("cols"), cols, _MAX_COLS),
                    _clamp(parsed.get("rows"), rows, _MAX_ROWS),
                )
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGWINCH)
                except (ProcessLookupError, PermissionError):
                    pass
            # unknown frame types are ignored on purpose

    output_task = asyncio.create_task(_pump_output())
    input_task = asyncio.create_task(_pump_input())
    try:
        done, _pending = await asyncio.wait(
            {output_task, input_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in done:
            exc = task.exception()
            if exc is not None and not isinstance(exc, WebSocketDisconnect):
                logger.warning("operator shell task error: %s", exc)
    finally:
        for task in (output_task, input_task):
            task.cancel()
        try:
            loop.remove_reader(master_fd)
        except (OSError, ValueError):
            pass
        try:
            os.close(master_fd)
        except OSError:
            pass
        if proc.returncode is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGHUP)
                await asyncio.wait_for(proc.wait(), timeout=_KILL_GRACE_SECONDS)
            except (asyncio.TimeoutError, ProcessLookupError, PermissionError):
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
        try:
            await ws.close()
        except RuntimeError:
            pass
