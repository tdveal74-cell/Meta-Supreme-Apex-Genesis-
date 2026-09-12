"""Authenticated DEVON control surface for EditForge media execution."""

from __future__ import annotations

import secrets
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.devon import _queue
from app.core.config import settings
from app.security.deps import CurrentUser
from app.services.editforge_client import (
    EditForgeClient,
    EditForgeConfig,
    read_editforge_status,
)
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
    # Minted by DEVON at authorize and returned to the caller; the draft
    # carries it back into execute. A caller-chosen id is refused at
    # authorize, because two accounts holding approvals for one id is how a
    # second account gets to retry or cancel another account's command.
    command_id: Optional[str] = Field(default=None, min_length=3, max_length=120)
    project_id: str = Field(..., min_length=3, max_length=120)
    cut_id: str = Field(..., min_length=3, max_length=120)
    property: Literal["tqo", "nco-forge", "tsws", "ascension-caudex"]
    deliverable: Literal["long-form", "short-form", "micro-drama"]
    source: SourceBody
    identity: Optional[IdentityBody] = None
    canon: CanonBody
    operations: List[OperationBody] = Field(..., min_length=1, max_length=250)
    output: OutputBody

    def to_intent(self, *, command_id: Optional[str] = None) -> Dict[str, Any]:
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
            "commandId": command_id or self.command_id,
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


class ControlBody(BaseModel):
    approval_id: str = Field(..., min_length=3, max_length=120)


def _raised_by(record, user: CurrentUser) -> bool:
    """Whether this caller raised the approval. Stamped at authorize, never
    supplied by the caller: another account presenting a valid approval id
    gets the same 404 as an unknown id."""
    return record.requested_by == f"DEVON:{user.id}" or (
        bool(record.owner_id) and record.owner_id == str(user.id)
    )


def _command_title(command_id: str) -> str:
    return f"Execute EditForge command {command_id}"


def _mint_command_id() -> str:
    """Unguessable and owned: the approval's title names it and nothing else can."""
    return f"cmd-{secrets.token_hex(8)}"


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
    return await read_editforge_status(_client().config)


@router.post("/authorize")
async def authorize_edit(body: EditDraftBody, user: CurrentUser) -> Dict[str, Any]:
    """Raise a single-use approval bound to the exact edit intent hash.

    DEVON mints the command id here and hands it back; the same draft with
    that id is what execute accepts, because the id is inside the hash the
    approval was bound to.
    """
    if body.command_id:
        raise HTTPException(
            status_code=422,
            detail=(
                "command_id is minted by DEVON at authorize. Send the draft without "
                "one and carry the returned command_id into execute."
            ),
        )
    command_id = _mint_command_id()
    intent = body.to_intent(command_id=command_id)
    issues = validate_intent(intent)
    if issues:
        raise HTTPException(status_code=422, detail=issues)
    record, token = _queue.request(
        title=_command_title(command_id),
        what_happens=approval_consequence(intent),
        requested_by=f"DEVON:{user.id}",
        area="Creation",
        reversible=True,
        blast_radius=f"project:{body.project_id}/cut:{body.cut_id}",
        owner_id=user.id,
    )
    return {
        "state": "approval_required",
        "request_id": record.request_id,
        "approval_token": token,
        "command_id": command_id,
        "summary": record.summary(),
        "decision_endpoint": "/api/v1/devon/approvals/decide",
        "note": (
            "The token is returned once. Approval authorizes only this exact command "
            "hash, which includes the minted command_id."
        ),
    }


@router.post("/execute")
async def execute_edit(body: ExecuteBody, user: CurrentUser) -> Dict[str, Any]:
    """Execute once, after the shared DEVON authority approved this exact intent.

    The approval is spent before the command leaves, so one human ruling
    renders once and spends provider credit once. A command EditForge then
    refuses leaves the approval spent; a fresh authorize is the retry path,
    the same policy every runtime adapter follows.
    """
    if not body.draft.command_id:
        raise HTTPException(
            status_code=422,
            detail="draft.command_id must be the command_id that authorize returned",
        )
    intent = body.draft.to_intent()
    record = _queue.get(body.approval_id)
    if record is None or not _raised_by(record, user):
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
    spent = _queue.consume(body.approval_id, consumed_by=f"DEVON:{user.id}")
    if not spent.ok:
        raise HTTPException(
            status_code=409,
            detail=spent.message or "approval could not be spent",
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
    body: ControlBody,
    user: CurrentUser,
) -> Dict[str, Any]:
    """Retry or cancel through EditForge, on the approval that ran the command.

    The caller names the approval it executed with. It must be the caller's
    own, already spent by execute, and raised for this command id. The id was
    minted by authorize, so no other account can hold an approval that names
    it. Publication and deletion are absent.
    """
    record = _queue.get(body.approval_id)
    if record is None or not _raised_by(record, user):
        raise HTTPException(status_code=404, detail="approval request not found")
    if record.state is not ApprovalState.CONSUMED:
        raise HTTPException(
            status_code=409,
            detail=f"approval is {record.state.value}; only an executed command can be retried or cancelled",
        )
    if record.title != _command_title(command_id):
        raise HTTPException(status_code=409, detail="approval does not name this command")
    try:
        return await _client().action(command_id, action)
    except EditForgeExecutionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
