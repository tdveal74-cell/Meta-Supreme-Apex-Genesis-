"""Authenticated DEVON control surface for EditForge media execution."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.devon import _queue
from app.core.config import settings
from app.security.deps import CurrentUser
from app.services.editforge_client import EditForgeClient, EditForgeConfig
from services.devon.approval import ApprovalState
from services.devon.editforge_execution import (
    EditForgeExecutionError,
    approval_consequence,
    approval_matches,
    build_command,
    validate_intent,
    validate_receipt,
)

router = APIRouter(prefix="/devon/editforge", tags=["DEVON EditForge"])


class SourceBody(BaseModel):
    uri: str = Field(..., min_length=1, max_length=8_000)
    sha256: str = Field(..., min_length=64, max_length=64)


class IdentityBody(BaseModel):
    clone_id: str = Field(..., min_length=1, max_length=500)
    voice_id: str = Field(..., min_length=1, max_length=500)
    version: str = Field(..., min_length=1, max_length=500)
    consent_recorded: bool


class CanonBody(BaseModel):
    version: str = Field(..., min_length=1, max_length=500)
    locked: bool


class OperationBody(BaseModel):
    id: str = Field(..., min_length=3, max_length=120)
    type: str = Field(..., min_length=1, max_length=100)
    target: Optional[str] = Field(default=None, max_length=2_000)
    params: Dict[str, Any] = Field(default_factory=dict)


class OutputBody(BaseModel):
    mode: Literal["preview", "master"]
    width: int = Field(..., ge=320, le=8_192)
    height: int = Field(..., ge=320, le=8_192)
    fps: Literal[24, 25, 30]
    container: Literal["mp4", "mov"]
    upload_url: Optional[str] = Field(default=None, max_length=8_000)


class EditDraftBody(BaseModel):
    command_id: str = Field(..., min_length=3, max_length=120)
    project_id: str = Field(..., min_length=3, max_length=120)
    cut_id: str = Field(..., min_length=3, max_length=120)
    property: Literal["tqo", "nco-forge", "tsws", "ascension-caudex"]
    deliverable: Literal["long-form", "short-form", "micro-drama"]
    source: SourceBody
    identity: Optional[IdentityBody] = None
    canon: CanonBody
    operations: List[OperationBody] = Field(..., min_length=1, max_length=250)
    output: OutputBody

    def to_intent(self) -> Dict[str, Any]:
        identity = None
        if self.identity:
            identity = {
                "cloneId": self.identity.clone_id,
                "voiceId": self.identity.voice_id,
                "version": self.identity.version,
                "consentRecorded": self.identity.consent_recorded,
            }
        output: Dict[str, Any] = {
            "mode": self.output.mode,
            "width": self.output.width,
            "height": self.output.height,
            "fps": self.output.fps,
            "container": self.output.container,
        }
        if self.output.upload_url:
            output["uploadUrl"] = self.output.upload_url
        return {
            "commandId": self.command_id,
            "projectId": self.project_id,
            "cutId": self.cut_id,
            "property": self.property,
            "deliverable": self.deliverable,
            "source": self.source.model_dump(),
            **({"identity": identity} if identity else {}),
            "canon": self.canon.model_dump(),
            "operations": [operation.model_dump(exclude_none=True) for operation in self.operations],
            "output": output,
        }


class ExecuteBody(BaseModel):
    approval_id: str = Field(..., min_length=3, max_length=120)
    draft: EditDraftBody


def _client() -> EditForgeClient:
    return EditForgeClient(
        EditForgeConfig(
            base_url=settings.EDITFORGE_URL,
            token=settings.EDITFORGE_TOKEN or "",
            timeout_seconds=settings.EDITFORGE_TIMEOUT_SECONDS,
        )
    )


def _public_execution(execution: Dict[str, Any]) -> Dict[str, Any]:
    """Return operational state without signed source or upload URLs."""
    public = {key: value for key, value in execution.items() if key != "command"}
    command = execution.get("command") or {}
    if command:
        public["command"] = {
            "commandId": command.get("commandId"),
            "projectId": command.get("projectId"),
            "cutId": command.get("cutId"),
            "property": command.get("property"),
            "deliverable": command.get("deliverable"),
            "operations": [
                {"id": operation.get("id"), "type": operation.get("type")}
                for operation in command.get("operations") or []
            ],
            "output": {
                key: value
                for key, value in (command.get("output") or {}).items()
                if key != "uploadUrl"
            },
        }
    return public


@router.get("/status")
async def editforge_status(user: CurrentUser) -> Dict[str, Any]:
    """Read the live EditForge boundary without exposing its credential."""
    client = _client()
    if not client.config.configured:
        return {
            "configured": False,
            "live_verified": False,
            "reason": "EDITFORGE_URL and EDITFORGE_TOKEN must be configured",
        }
    try:
        status = await client.status()
    except EditForgeExecutionError as exc:
        return {"configured": True, "live_verified": False, "reason": str(exc)}
    return {"configured": True, "live_verified": True, "editforge": status}


@router.post("/authorize")
async def authorize_edit(body: EditDraftBody, user: CurrentUser) -> Dict[str, Any]:
    """Raise a single-use approval bound to the exact edit intent hash."""
    intent = body.to_intent()
    issues = validate_intent(intent)
    if issues:
        raise HTTPException(status_code=422, detail=issues)
    record, token = _queue.request(
        title=f"Execute EditForge command {body.command_id}",
        what_happens=approval_consequence(intent),
        requested_by=f"DEVON:{user.id}",
        area="Creation",
        reversible=True,
        blast_radius=f"project:{body.project_id}/cut:{body.cut_id}",
    )
    return {
        "state": "approval_required",
        "request_id": record.request_id,
        "approval_token": token,
        "summary": record.summary(),
        "decision_endpoint": "/api/v1/devon/approvals/decide",
        "note": "The token is returned once. Approval authorizes only this exact command hash.",
    }


@router.post("/execute")
async def execute_edit(body: ExecuteBody, user: CurrentUser) -> Dict[str, Any]:
    """Execute only after the shared DEVON authority approved this exact intent."""
    intent = body.draft.to_intent()
    record = _queue.get(body.approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="approval request not found")
    if record.state is not ApprovalState.APPROVED:
        raise HTTPException(status_code=409, detail=f"approval is {record.state.value}")
    if not approval_matches(what_happens=record.what_happens, intent=intent):
        raise HTTPException(status_code=409, detail="approval does not match this edit intent")

    command = build_command(
        intent,
        approval_id=record.request_id,
        approved_by=record.decided_by or "Tee",
    )
    try:
        result = await _client().execute(command)
    except EditForgeExecutionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    editforge = dict(result)
    if isinstance(editforge.get("execution"), dict):
        editforge["execution"] = _public_execution(editforge["execution"])
    return {
        "devon": "executed",
        "canonical_orchestrator": "DEVON",
        "approval_id": record.request_id,
        "command_id": command["commandId"],
        "operations": [operation["type"] for operation in command["operations"]],
        "editforge": editforge,
    }


@router.get("/executions/{command_id}")
async def get_execution(command_id: str, user: CurrentUser, poll: bool = True) -> Dict[str, Any]:
    """Read back worker state and validate a terminal receipt before trusting it."""
    try:
        result = await _client().execution(command_id, poll=poll)
    except EditForgeExecutionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    execution = result.get("execution") or {}
    receipt = execution.get("receipt")
    receipt_issues = (
        validate_receipt(
            receipt,
            command_id=command_id,
            revision_id=execution.get("revisionId"),
        )
        if receipt
        else []
    )
    return {
        "execution": _public_execution(execution),
        "receipt_valid": bool(receipt) and not receipt_issues,
        "receipt_issues": receipt_issues,
    }


@router.post("/executions/{command_id}/{action}")
async def control_execution(
    command_id: str,
    action: Literal["retry", "cancel"],
    user: CurrentUser,
) -> Dict[str, Any]:
    """Retry or cancel through EditForge; publication and deletion are absent."""
    try:
        return await _client().action(command_id, action)
    except EditForgeExecutionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
