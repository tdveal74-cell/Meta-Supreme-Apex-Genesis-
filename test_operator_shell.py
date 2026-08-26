"""The operator shell WebSocket: a real PTY behind a two-factor gate.

The shell is the one place a human gets an unmediated bash on the API
container, so these tests pin the boundary that matters:

  - a full shell needs BOTH a valid login JWT and the dedicated shell key
    (which is distinct from the operator key);
  - a missing or wrong either factor is refused with a close code;
  - with no shell key configured the endpoint is disabled outright;
  - with both factors the caller gets a live PTY that runs a real piped
    command and reports its exit code.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import operator_shell as shell_module
from app.core.config import settings
from app.main import app
from app.security.jwt import create_access_token


@pytest.fixture()
def shell_enabled(monkeypatch):
    # Bridge on (gives the PTY a root/cwd) and a dedicated shell key set.
    monkeypatch.setattr(shell_module._bridge, "enabled", True)
    monkeypatch.setattr(settings, "DEVON_SHELL_KEY", "test-shell-key")
    monkeypatch.setattr(settings, "DEVON_SHELL_IDLE_TIMEOUT_SECONDS", 900)
    return settings


@pytest.fixture()
def good_token():
    return create_access_token(subject="tee-operator")


@pytest.fixture()
def client():
    return TestClient(app)


def _recv_type(ws, wanted: str, attempts: int = 60) -> dict:
    for _ in range(attempts):
        frame = json.loads(ws.receive_text())
        if frame.get("type") == wanted:
            return frame
    raise AssertionError(f"never received a {wanted!r} frame")


def test_shell_disabled_without_shell_key(client, monkeypatch, good_token):
    monkeypatch.setattr(shell_module._bridge, "enabled", True)
    monkeypatch.setattr(settings, "DEVON_SHELL_KEY", "")
    with client.websocket_connect("/api/v1/operator/shell") as ws:
        ws.send_text(json.dumps({"type": "hello", "token": good_token, "key": "x"}))
        frame = json.loads(ws.receive_text())
        assert frame["type"] == "error"
        assert "not configured" in frame["message"]


def test_shell_rejects_without_token(client, shell_enabled):
    # Right shell key, but no login JWT — one factor is not enough.
    with client.websocket_connect("/api/v1/operator/shell") as ws:
        ws.send_text(json.dumps({"type": "hello", "key": "test-shell-key"}))
        frame = json.loads(ws.receive_text())
        assert frame["type"] == "error"
        assert "session" in frame["message"]


def test_shell_rejects_wrong_shell_key(client, shell_enabled, good_token):
    # Valid JWT, but wrong shell key — the other factor fails.
    with client.websocket_connect("/api/v1/operator/shell") as ws:
        ws.send_text(json.dumps({"type": "hello", "token": good_token, "key": "nope"}))
        frame = json.loads(ws.receive_text())
        assert frame["type"] == "error"
        assert "shell key" in frame["message"]


def test_shell_rejects_operator_key_as_shell_key(client, shell_enabled, good_token, monkeypatch):
    # The operator key must NOT open the shell: the keys are separate.
    monkeypatch.setattr(shell_module._bridge, "_operator_key", "operator-only-key")
    with client.websocket_connect("/api/v1/operator/shell") as ws:
        ws.send_text(
            json.dumps({"type": "hello", "token": good_token, "key": "operator-only-key"})
        )
        frame = json.loads(ws.receive_text())
        assert frame["type"] == "error"
        assert "shell key" in frame["message"]


def test_shell_rejects_malformed_hello(client, shell_enabled):
    with client.websocket_connect("/api/v1/operator/shell") as ws:
        ws.send_text("this is not json")
        frame = json.loads(ws.receive_text())
        assert frame["type"] == "error"
        assert frame["message"] == "malformed hello"


def test_shell_runs_real_commands_with_both_factors(client, shell_enabled, good_token):
    with client.websocket_connect("/api/v1/operator/shell") as ws:
        ws.send_text(
            json.dumps(
                {
                    "type": "hello",
                    "token": good_token,
                    "key": "test-shell-key",
                    "cols": 120,
                    "rows": 32,
                }
            )
        )
        ready = _recv_type(ws, "ready")
        assert ready["cwd"] == str(shell_module._bridge.root)
        assert ready["idle_timeout"] == 900

        # A pipe proves this is a real shell, not the parsed command path.
        ws.send_text(
            json.dumps({"type": "input", "data": "printf 'devon\\nshell\\n' | tail -1\n"})
        )
        seen = ""
        for _ in range(60):
            frame = json.loads(ws.receive_text())
            if frame.get("type") == "output":
                seen += frame["data"]
                if "shell" in seen.replace("\r", ""):
                    break
        assert "shell" in seen.replace("\r", "")

        ws.send_text(json.dumps({"type": "input", "data": "exit\n"}))
        exit_frame = _recv_type(ws, "exit")
        assert isinstance(exit_frame["code"], int)
