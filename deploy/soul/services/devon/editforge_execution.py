"""DEVON's governed execution boundary for EditForge.

DEVON owns intent, approval, routing, verification, and revision decisions.
EditForge owns media execution. This pure module validates and gates contracts;
the FastAPI application boundary owns transport. Neither surface can publish,
delete, change canon, or change identity through this contract.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, Mapping, Optional

EDIT_COMMAND_SCHEMA = "editforge.edit-command.v1"
EDIT_RECEIPT_SCHEMA = "editforge.edit-receipt.v1"
APPROVAL_MARKER = "EDITFORGE_INTENT_SHA256="

PROPERTIES = {"tqo", "nco-forge", "tsws", "ascension-caudex"}
DELIVERABLES = {"long-form", "short-form", "micro-drama"}
ALLOWED_OPERATIONS = {
    "trim",
    "split",
    "reorder",
    "replace-shot",
    "reframe",
    "speed",
    "captions",
    "audio-mix",
    "grade",
    "title",
    "transition",
    "synthesize-voice",
    "generate-full-motion",
    "lip-sync",
    "render-preview",
    "render-master",
    "derive-short",
    "assemble-episode",
    "assemble-compilation",
}
IDENTITY_OPERATIONS = {"synthesize-voice", "generate-full-motion", "lip-sync"}
FORBIDDEN_EFFECTS = {"publish", "delete", "change-canon", "change-identity"}
SHA256_RE = re.compile(r"^[a-f0-9]{64}$", re.IGNORECASE)
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,119}$")


class EditForgeExecutionError(RuntimeError):
    """A governed execution was refused or the execution boundary failed."""


def canonical_hash(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_intent(intent: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    for field in ("commandId", "projectId", "cutId"):
        if not ID_RE.fullmatch(str(intent.get(field) or "")):
            issues.append(f"{field} must be a stable 3-120 character id")
    if intent.get("property") not in PROPERTIES:
        issues.append("property is not canonical")
    if intent.get("deliverable") not in DELIVERABLES:
        issues.append("deliverable is not supported")
    source = intent.get("source") or {}
    source_uri = str(source.get("uri") or "").strip()
    if not re.match(r"^https?://", source_uri, re.IGNORECASE):
        issues.append("source.uri must be HTTP or HTTPS")
    if not SHA256_RE.fullmatch(str(source.get("sha256") or "")):
        issues.append("source.sha256 must be a SHA-256 hash")
    canon = intent.get("canon") or {}
    if not str(canon.get("version") or "").strip() or canon.get("locked") is not True:
        issues.append("locked canon version is required")

    operations = intent.get("operations") or []
    if not isinstance(operations, list) or not operations:
        issues.append("at least one edit operation is required")
        operations = []
    if any(not isinstance(operation, dict) for operation in operations):
        issues.append("every operation must be an object")
    operation_types = {str(operation.get("type") or "") for operation in operations if isinstance(operation, dict)}
    operation_ids = [str(operation.get("id") or "") for operation in operations if isinstance(operation, dict)]
    if any(not ID_RE.fullmatch(operation_id) for operation_id in operation_ids):
        issues.append("every operation must have a stable 3-120 character id")
    if len(operation_ids) != len(set(operation_ids)):
        issues.append("operation ids must be unique")
    if any(not isinstance(operation.get("params"), dict) for operation in operations if isinstance(operation, dict)):
        issues.append("every operation params value must be an object")
    unknown = operation_types - ALLOWED_OPERATIONS
    if unknown:
        issues.append(f"unsupported operations: {', '.join(sorted(unknown))}")
    forbidden = operation_types & FORBIDDEN_EFFECTS
    if forbidden:
        issues.append(f"forbidden effects require a separate authority: {', '.join(sorted(forbidden))}")
    if operation_types & IDENTITY_OPERATIONS:
        identity = intent.get("identity") or {}
        required = ("cloneId", "voiceId", "version")
        if any(not str(identity.get(key) or "").strip() for key in required):
            issues.append("clone id, voice id, and identity version are required")
        if identity.get("consentRecorded") is not True:
            issues.append("cloned identity consent must be recorded")
    if intent.get("deliverable") == "micro-drama" and "generate-full-motion" not in operation_types:
        issues.append("micro-drama execution requires full motion")
    if intent.get("property") == "tsws" and "tsws" not in str(canon.get("version") or "").lower():
        issues.append("TSWS execution must name a TSWS canon revision")
    if intent.get("property") == "ascension-caudex" and "acx" not in str(canon.get("version") or "").lower():
        issues.append("Ascension Caudex execution must name an ACX canon revision")
    output = intent.get("output") or {}
    if output.get("mode") not in {"preview", "master"}:
        issues.append("output.mode must be preview or master")
    if output.get("mode") == "master" and "render-master" not in operation_types:
        issues.append("master output requires render-master")
    if output.get("mode") == "preview" and "render-master" in operation_types:
        issues.append("render-master cannot run as a preview")
    if output.get("container") not in {"mp4", "mov"}:
        issues.append("output.container must be mp4 or mov")
    if output.get("fps") not in {24, 25, 30}:
        issues.append("output.fps must be 24, 25, or 30")
    for field in ("width", "height"):
        value = output.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or not 320 <= value <= 8192:
            issues.append(f"output.{field} must be an integer from 320 to 8192")
    return issues


def approval_consequence(intent: Mapping[str, Any]) -> str:
    digest = canonical_hash(intent)
    operation_types = [str(op.get("type")) for op in intent.get("operations", [])]
    return (
        "Authorize DEVON to send this exact non-destructive edit command to EditForge. "
        f"Project: {intent.get('projectId')}. Cut: {intent.get('cutId')}. "
        f"Operations: {', '.join(operation_types)}. Output: {(intent.get('output') or {}).get('mode')}. "
        "This does not authorize canon changes, identity changes, publication, or deletion. "
        f"{APPROVAL_MARKER}{digest}"
    )


def approval_matches(*, what_happens: str, intent: Mapping[str, Any]) -> bool:
    return f"{APPROVAL_MARKER}{canonical_hash(intent)}" in (what_happens or "")


def build_command(
    intent: Mapping[str, Any], *, approval_id: str, approved_by: str
) -> Dict[str, Any]:
    issues = validate_intent(intent)
    if issues:
        raise EditForgeExecutionError("; ".join(issues))
    command = dict(intent)
    command["schema"] = EDIT_COMMAND_SCHEMA
    command["issuedBy"] = "DEVON"
    command["authorization"] = {
        "approvalId": approval_id,
        "approvedBy": approved_by,
        "scopes": sorted(
            {f"edit:{operation['type']}" for operation in intent.get("operations", [])}
        ),
    }
    return command


def validate_receipt(
    receipt: Mapping[str, Any], *, command_id: str, revision_id: Optional[str] = None
) -> list[str]:
    issues: list[str] = []
    if receipt.get("schema") != EDIT_RECEIPT_SCHEMA:
        issues.append("receipt schema mismatch")
    if receipt.get("commandId") != command_id:
        issues.append("receipt command mismatch")
    if revision_id and receipt.get("revisionId") != revision_id:
        issues.append("receipt revision mismatch")
    if receipt.get("status") not in {"completed", "failed", "cancelled"}:
        issues.append("receipt is not terminal")
    for artifact in receipt.get("artifacts") or []:
        if not SHA256_RE.fullmatch(str(artifact.get("sha256") or "")):
            issues.append("artifact is missing a valid SHA-256 hash")
        if not str(artifact.get("uri") or "").strip():
            issues.append("artifact URI is missing")
    if receipt.get("status") == "completed" and not receipt.get("artifacts"):
        issues.append("completed receipt has no artifacts")
    return issues
