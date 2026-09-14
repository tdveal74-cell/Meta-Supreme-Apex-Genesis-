"""Signed, allowlisted client for the DEVON VPS read-only gateway."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from typing import Any

import httpx

DEFAULT_OPS_URL = "https://ops.editforge.online"
ALLOWED_READS = frozenset(
    {
        ("status", ""),
        ("health", "n8n"),
        ("health", "render-adapter"),
    }
)


class DevonOpsGatewayError(RuntimeError):
    """A safe-to-return gateway failure."""


def _settings() -> tuple[str, bytes]:
    url = (os.environ.get("DEVON_OPS_URL") or DEFAULT_OPS_URL).strip().rstrip("/")
    secret = (os.environ.get("DEVON_OPS_SECRET") or "").strip()
    if not secret:
        raise DevonOpsGatewayError("DEVON_OPS_SECRET is not configured.")
    if not url.startswith("https://"):
        raise DevonOpsGatewayError("DEVON_OPS_URL must use HTTPS.")
    return url, secret.encode("utf-8")


def _signed_request(operation: str, target: str) -> tuple[bytes, dict[str, str]]:
    if (operation, target) not in ALLOWED_READS:
        raise DevonOpsGatewayError("That VPS read operation is not allowed.")

    _, secret = _settings()
    body = json.dumps(
        {"operation": operation, "target": target},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    stamp = str(int(time.time()))
    signature = hmac.new(
        secret,
        stamp.encode("ascii") + bytes([10]) + body,
        hashlib.sha256,
    ).hexdigest()
    return body, {
        "Content-Type": "application/json",
        "X-Devon-Timestamp": stamp,
        "X-Devon-Signature": signature,
    }


async def gateway_read(operation: str, target: str = "") -> dict[str, Any]:
    """Run one fixed read-only operation through the signed gateway."""
    url, _ = _settings()
    body, headers = _signed_request(operation, target)
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
            response = await client.post(
                f"{url}/v1/read",
                content=body,
                headers=headers,
            )
    except httpx.RequestError as exc:
        raise DevonOpsGatewayError("The VPS operations gateway is unreachable.") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise DevonOpsGatewayError("The VPS operations gateway returned invalid JSON.") from exc

    if response.status_code != 200:
        code = payload.get("error") if isinstance(payload, dict) else None
        raise DevonOpsGatewayError(
            f"The VPS operations gateway refused the request: {code or response.status_code}."
        )
    if not isinstance(payload, dict):
        raise DevonOpsGatewayError("The VPS operations gateway returned an invalid response.")
    return payload
