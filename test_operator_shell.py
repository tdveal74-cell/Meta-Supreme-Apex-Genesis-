"""The operator shell WebSocket: a real PTY for the key holder, nobody else.

The shell endpoint is the one place a human gets an unmediated bash on the
API container, so these tests pin the boundary that matters: no key, no
shell; disabled bridge, no shell; right key, a live PTY that echoes real
command output back.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import operator as operator_module
from app.main import app


@pytest.fixture()
def enabled_bridge(monkeypatch):
    monkeypatch.setattr(operator_module._bridge, "enabled", True)
    monkeypatch.setattr(operator_module._bridge, "_operator_key", "test-shell-key")
    return operator_module._bridge


@pytest.fixture()
def client():
    return TestClient(app)


def _recv_type(ws, wanted: str, attempts: int = 50) -> dict:
    """Read frames until one of the wanted type arrives."""
    for _ in range(attempts):
        frame = json.loads(ws.receive_text())
        if frame.get("type") == wanted:
            return frame
    raise AssertionError(f"never received a {wanted!r} frame")


def test_shell_rejects_wrong_key(client, enabled_bridge):
    with client.websocket_connect("/api/v1/operator/shell") as ws:
        ws.send_text(json.dumps({"type": "hello", "key": "wrong"}))
        frame = json.loads(ws.receive_text())
        assert frame["type"] == "error"
        assert "operator key" in frame["message"]


def test_shell_rejects_when_bridge_disabled(client, monkeypatch):
    monkeypatch.setattr(operator_module._bridge, "enabled", False)
    with client.websocket_connect("/api/v1/operator/shell") as ws:
        ws.send_text(json.dumps({"type": "hello", "key": "anything"}))
        frame = json.loads(ws.receive_text())
        assert frame["type"] == "error"
        assert "disabled" in frame["message"]


def test_shell_rejects_malformed_hello(client, enabled_bridge):
    with client.websocket_connect("/api/v1/operator/shell") as ws:
        ws.send_text("this is not json")
        frame = json.loads(ws.receive_text())
        assert frame["type"] == "error"
        assert frame["message"] == "malformed hello"


def test_shell_runs_real_commands_in_a_pty(client, enabled_bridge):
    with client.websocket_connect("/api/v1/operator/shell") as ws:
        ws.send_text(
            json.dumps(
                {"type": "hello", "key": "test-shell-key", "cols": 120, "rows": 32}
            )
        )
        ready = _recv_type(ws, "ready")
        assert ready["cwd"] == str(operator_module._bridge.root)

        # A pipe proves this is a real shell, not the parsed command path.
        ws.send_text(
            json.dumps(
                {"type": "input", "data": "printf 'devon\\nshell\\n' | tail -1\n"}
            )
        )
        seen = ""
        for _ in range(50):
            frame = json.loads(ws.receive_text())
            if frame.get("type") == "output":
                seen += frame["data"]
                if "shell" in seen.replace("\r", ""):
                    break
        assert "shell" in seen.replace("\r", "")

        ws.send_text(json.dumps({"type": "input", "data": "exit\n"}))
        exit_frame = _recv_type(ws, "exit")
        assert isinstance(exit_frame["code"], int)
