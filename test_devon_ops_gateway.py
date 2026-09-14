"""Unit tests for the signed, allowlisted DEVON VPS gateway client."""

from __future__ import annotations

import hashlib
import hmac
import json
import pathlib
import sys

import pytest

SOUL = pathlib.Path(__file__).resolve().parent / "deploy" / "soul"
sys.path.insert(0, str(SOUL))

import ops_gateway  # noqa: E402


def test_signed_request_matches_gateway_contract(monkeypatch):
    monkeypatch.setenv("DEVON_OPS_SECRET", "test-secret")
    monkeypatch.setenv("DEVON_OPS_URL", "https://ops.example.test")
    monkeypatch.setattr(ops_gateway.time, "time", lambda: 1_700_000_000)

    body, headers = ops_gateway._signed_request("health", "n8n")

    assert json.loads(body) == {"operation": "health", "target": "n8n"}
    expected = hmac.new(
        b"test-secret",
        b"1700000000" + bytes([10]) + body,
        hashlib.sha256,
    ).hexdigest()
    assert headers["X-Devon-Timestamp"] == "1700000000"
    assert headers["X-Devon-Signature"] == expected


def test_unknown_operation_is_blocked(monkeypatch):
    monkeypatch.setenv("DEVON_OPS_SECRET", "test-secret")
    with pytest.raises(ops_gateway.DevonOpsGatewayError, match="not allowed"):
        ops_gateway._signed_request("restart", "n8n")


def test_http_url_is_blocked(monkeypatch):
    monkeypatch.setenv("DEVON_OPS_SECRET", "test-secret")
    monkeypatch.setenv("DEVON_OPS_URL", "http://172.16.2.1:8091")
    with pytest.raises(ops_gateway.DevonOpsGatewayError, match="HTTPS"):
        ops_gateway._signed_request("status", "")


def test_missing_secret_fails_closed(monkeypatch):
    monkeypatch.delenv("DEVON_OPS_SECRET", raising=False)
    with pytest.raises(ops_gateway.DevonOpsGatewayError, match="not configured"):
        ops_gateway._signed_request("status", "")
