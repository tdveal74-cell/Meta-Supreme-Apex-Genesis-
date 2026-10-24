"""Client for DEVON's n8n Action Router, the one door into the n8n executors.

Ruled by Tee 2026-10-24: DEVON executes through both lanes, the Python runtime
and n8n. This client lets the runtime hand an approved job straight to the
Action Router (`vault.WORKFLOWS["Action Router"]`, webhook `devon-action`) as an
AUTHORIZED v1 job envelope, the same shape the Job Driver posts. The router and
each executor then run their own gates on it: allowlist, ceiling, grant, expiry
and idempotency key. Nothing here widens what an executor will accept.

ACTIONS mirrors the router's TARGETS table in
`n8n/devon/action-router/authorise_and_resolve_target.js`, ceiling for ceiling.
`test_devon_n8n_action_adapter.py` pins the two together, because a name on this
side that the router does not know is a capability that reads as real and is
refused every time.

The router authenticates the caller with the `x-devon-key` header and nothing
else, and that key is approval-equivalent for a write: anyone holding it can
post an AUTHORIZED envelope. It is configuration (`DEVON_N8N_ACTION_KEY`), never
a tool argument or output. Written 2026-10-24 against a mock transport; no
envelope has been posted to the live router from this code yet, and the first
one is the proof.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional

import httpx

ROUTER_URL = "https://n8n.editforge.online/webhook/devon-action"
SCHEMA_VERSION = "1.0.0"
MAX_ERROR_CHARS = 2_000
MAX_SUMMARY_CHARS = 500

# Action name to the ceiling the router enforces for it.
ACTIONS: Dict[str, str] = {
    "spine.echo": "read",
    "drive.draft": "reversible_write",
    "airtable.row": "reversible_write",
    "zapier.mcp": "reversible_write",
}

# Payload keys the router and executors reserve for themselves. A caller who
# set one would be steering the router rather than handing it a job.
RESERVED_PAYLOAD_KEYS = ("action", "editforge")

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class N8NActionError(ValueError):
    """The dispatch cannot proceed safely, or the router answered with no usable result."""


def ulid_from(seed: str, *, millis: Optional[int] = None) -> str:
    """A ULID whose time part is now and whose random part is fixed by the seed.

    Deterministic randomness means a retried dispatch of the same approved
    binding carries the same 80 bits, so the executors' search by intent id and
    idempotency key has something stable to find.
    """
    ms = int(time.time() * 1000) if millis is None else int(millis)
    if not 0 <= ms < 2**48:
        raise N8NActionError("ULID time is out of range")
    entropy = int.from_bytes(hashlib.sha256(seed.encode("utf-8")).digest()[:10], "big")
    value = (ms << 80) | entropy
    chars = []
    for _ in range(26):
        chars.append(_CROCKFORD[value & 31])
        value >>= 5
    return "".join(reversed(chars))


def _iso(moment: Optional[datetime]) -> Optional[str]:
    if moment is None:
        return None
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class N8NActionClient:
    def __init__(
        self,
        *,
        key: Optional[str] = None,
        url: Optional[str] = None,
        timeout_seconds: float = 60.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self.key = (key if key is not None else os.getenv("DEVON_N8N_ACTION_KEY", "")).strip()
        self.url = (url or os.getenv("DEVON_N8N_ACTION_URL") or ROUTER_URL).strip()
        self.timeout_seconds = max(1.0, min(float(timeout_seconds), 120.0))
        self.transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.key and self.url.startswith("https://"))

    @staticmethod
    def require_action(action: str) -> str:
        name = (action or "").strip()
        if name not in ACTIONS:
            raise N8NActionError(
                f"action {name!r} is not on the Action Router allowlist. Known: "
                + ", ".join(sorted(ACTIONS))
            )
        return name

    def build_envelope(
        self,
        *,
        action: str,
        summary: str,
        payload: Mapping[str, Any],
        area: Optional[str],
        binding: str,
        request_id: str,
        decided_by: Optional[str],
        decided_at: Optional[datetime],
        requested_at: Optional[datetime],
        expires_at: datetime,
        card: str,
        millis: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Build the AUTHORIZED envelope. Pure, so it can be tested without a router."""
        name = self.require_action(action)
        clean_summary = " ".join((summary or "").split())
        if len(clean_summary) < 8:
            raise N8NActionError("summary must say what the job is, at least 8 characters")
        if len(clean_summary) > MAX_SUMMARY_CHARS:
            raise N8NActionError(
                f"summary is {len(clean_summary)} characters; the limit is {MAX_SUMMARY_CHARS}"
            )
        if not isinstance(payload, Mapping):
            raise N8NActionError("payload must be an object")
        reserved = [key for key in RESERVED_PAYLOAD_KEYS if key in payload]
        if reserved:
            raise N8NActionError(
                "payload may not set " + ", ".join(reserved)
                + "; the action is named by the action argument and renders have their own lane"
            )
        if len(binding) < 32:
            raise N8NActionError("approval binding is missing")

        now = datetime.now(timezone.utc) if millis is None else datetime.fromtimestamp(millis / 1000, timezone.utc)
        return {
            "schema_version": SCHEMA_VERSION,
            "intent_id": ulid_from(binding, millis=millis),
            "state": "AUTHORIZED",
            "created_at": _iso(now),
            "updated_at": _iso(now),
            "area": area or None,
            "actor": {
                "type": "devon",
                "source": "devon-agent-runtime",
                "on_behalf_of": "tee",
            },
            "idempotency_key": f"devon-rt-{binding[:40]}",
            "intent": {
                "summary": clean_summary,
                "level": 2,
                "blast_radius": ACTIONS[name],
                "payload": {**dict(payload), "action": name},
            },
            "approval": {
                "state": "granted",
                "queue_row_id": request_id,
                "decided_by": decided_by or "Tee",
                "decided_at": _iso(decided_at),
                "requested_at": _iso(requested_at),
                "expires_at": _iso(expires_at),
                "scope": "execute exactly as planned: " + clean_summary,
                "card_executor": card[:500],
            },
            "execution": {"state": "pending", "executor": "n8n", "attempts": 0, "max_attempts": 1},
            "artifacts": [],
            "canon_refs": [],
        }

    async def dispatch(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        if not self.configured:
            raise N8NActionError(
                "n8n Action Router is not configured. Set DEVON_N8N_ACTION_KEY "
                "(the router's x-devon-key) on the deployment."
            )
        action = envelope.get("intent", {}).get("payload", {}).get("action")
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                response = await client.post(
                    self.url,
                    headers={
                        "x-devon-key": self.key,
                        "Content-Type": "application/json",
                        "User-Agent": "DEVON-Agent-Runtime",
                    },
                    json={"envelope": envelope, "action": action},
                )
        except httpx.HTTPError as exc:
            raise N8NActionError(
                f"Action Router transport error: {exc}. Do not assume the job ran; "
                "read the executor's own record before retrying."
            ) from exc

        if not 200 <= response.status_code < 300:
            raise N8NActionError(
                f"Action Router answered HTTP {response.status_code}: "
                f"{response.text[:MAX_ERROR_CHARS]}"
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise N8NActionError(
                "Action Router answered with no JSON body. Do not assume the job ran."
            ) from exc
        first = data[0] if isinstance(data, list) and data else data
        if not isinstance(first, dict):
            raise N8NActionError(
                "Action Router answered with an unexpected shape. Do not assume the job ran."
            )
        if first.get("refused") is True:
            raise N8NActionError(
                "Action Router refused: "
                + str(first.get("reason") or first.get("refusal_reason") or "no reason given")[:MAX_ERROR_CHARS]
            )
        return _summarise(first, envelope)


def _summarise(answer: Dict[str, Any], sent: Dict[str, Any]) -> Dict[str, Any]:
    """Pull the receipt out of whichever of the two answer shapes came back.

    The router may answer with the executor's envelope or with its own dispatch
    report wrapping one. Either way success means an envelope that moved past
    AUTHORIZED; anything else is reported as not confirmed rather than as done.
    """
    returned = answer if answer.get("schema_version") == SCHEMA_VERSION else answer.get("envelope")
    if not isinstance(returned, dict):
        returned = {}
    state = returned.get("state") or answer.get("executor_state")
    artifacts = returned.get("artifacts") if isinstance(returned.get("artifacts"), list) else []
    artifact_uri = answer.get("artifact_uri") or (
        str(artifacts[-1].get("uri") or "") if artifacts and isinstance(artifacts[-1], dict) else ""
    )
    if state in (None, "", "AUTHORIZED") or answer.get("outcome") in (
        "executor_refused",
        "executor_returned_nothing_usable",
    ):
        raise N8NActionError(
            "The router answered but no executor confirmed the work (state "
            f"{state!r}, outcome {answer.get('outcome')!r}). Not reported as done: "
            + json.dumps(answer, ensure_ascii=False, default=str)[:MAX_ERROR_CHARS]
        )
    execution = returned.get("execution") if isinstance(returned.get("execution"), dict) else {}
    return {
        "action": sent["intent"]["payload"]["action"],
        "intent_id": sent["intent_id"],
        "idempotency_key": sent["idempotency_key"],
        "state": state,
        "executor_execution_id": execution.get("execution_id") or answer.get("execution_id"),
        "artifact_uri": artifact_uri or None,
        "artifacts": artifacts,
    }
