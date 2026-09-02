"""
DEVON endpoints, the second brain surface.

Every route here is a read or a validation. Nothing writes to Drive, Notion,
Airtable or n8n, and nothing runs an effect. Captures return a filing plan and
effects return an approval request, which keeps the API surface incapable of
committing something unattended.

The approval queue uses the PostgreSQL shared store by default. Pending approval
records and rulings are visible across API workers and durable across process
restart. The one-time plaintext approval token is intentionally never persisted
or recoverable from the queue. An explicit DEVON_APPROVAL_STORE=memory setting
is available for offline/local work only. Backend failures fail closed rather
than silently downgrading to a process-local queue.
"""

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.security.deps import CurrentUser
from app.services.devon_approval_store import build_approval_queue
from app.services.knowledge_loop import REQUESTED_BY as KNOWLEDGE_LOOP_REQUESTER
from services.devon import areas as areas_mod
from services.devon import (
    filing,
    flagship,
    naming,
    operating_layer,
    persona,
    receipts,
    vault,
)
from services.devon.approval import NO_MATCH, DecisionResult, RefusalReason
from services.devon.assistant import Devon
from services.devon.commands import ALL_INTENTS, approval_gated_intents
from services.devon.precedence import Candidate, resolve

router = APIRouter(prefix="/devon", tags=["DEVON"])

# One logical approval authority per API process, backed by the same PostgreSQL
# table across workers. Operator and Agent Tasks import this queue so every
# effect lane consults the same durable authority.
_queue = build_approval_queue()
_devon = Devon(approvals=_queue)


def _runtime_commit() -> Optional[str]:
    for name in (
        "RAILWAY_GIT_COMMIT_SHA",
        "VERCEL_GIT_COMMIT_SHA",
        "GIT_COMMIT_SHA",
        "SOURCE_COMMIT",
    ):
        value = os.getenv(name, "").strip()
        if value:
            return value
    return None


def _approval_storage_status() -> Dict[str, Any]:
    shared = _queue.storage_backend == "postgres"
    return {
        "backend": _queue.storage_backend,
        "shared": shared,
        "state_durable": shared,
        "plaintext_tokens_persisted": False,
        "token_recoverable": False,
    }


@router.get("")
async def devon_identity() -> Dict[str, Any]:
    """Who DEVON is and what this surface will not do."""
    return {
        "name": persona.NAME,
        "owner": persona.OWNER,
        "persona": persona.PERSONA_SUMMARY,
        "register": persona.REGISTER,
        "boundary": persona.BOUNDARY,
        "areas": areas_mod.canonical_labels(),
        "hard_rules": [r.rule for r in persona.HARD_RULES],
        "intents": len(ALL_INTENTS),
        "approval_gated_intents": [i.name for i in approval_gated_intents()],
        "approval_storage": _approval_storage_status(),
        "guarantees": [
            "No route writes to Drive, Notion, Airtable or n8n.",
            "Captures return a filing plan. The caller executes it.",
            "Effects return an approval request. Rulings are Tee's, never a model's.",
        ],
    }


@router.get("/operating-layer/status")
async def operating_layer_status() -> Dict[str, Any]:
    """Live proof of the policy surface, with external state kept honest."""
    return operating_layer.capability_status(runtime_commit=_runtime_commit())


class OperatingRouteBody(BaseModel):
    goal: str = Field(..., min_length=1, max_length=20_000)
    needs: List[operating_layer.Need] = Field(default_factory=list, max_length=30)
    risk: operating_layer.Risk = operating_layer.Risk.READ
    source_systems: List[str] = Field(default_factory=list, max_length=30)


@router.post("/operating-layer/route")
async def route_operating_layer(body: OperatingRouteBody) -> Dict[str, Any]:
    """Select the best surface. This plans a route and performs no delegation."""
    decision = operating_layer.route(
        operating_layer.TaskProfile(
            goal=body.goal,
            needs=tuple(body.needs),
            risk=body.risk,
            source_systems=tuple(body.source_systems),
        )
    )
    return decision.to_dict()


class SourceReferenceBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    uri: str = Field(..., min_length=1, max_length=4000)
    read_at: str = Field(..., min_length=1, max_length=120)
    revision: str = Field(default="", max_length=500)
    content_hash: str = Field(default="", max_length=200)


class ArtifactReferenceBody(BaseModel):
    path: str = Field(..., min_length=1, max_length=2000)
    role: str = Field(..., min_length=1, max_length=500)
    sha256: str = Field(default="", max_length=64)
    media_type: str = Field(default="application/octet-stream", max_length=200)
    verified: bool = False

    def to_contract(self) -> operating_layer.ArtifactReference:
        return operating_layer.ArtifactReference(**self.model_dump())


class HandoffBody(BaseModel):
    handoff_id: str = Field(..., min_length=1, max_length=120)
    from_surface: operating_layer.Surface
    to_surface: operating_layer.Surface
    goal: str = Field(..., min_length=1, max_length=20_000)
    context_summary: str = Field(..., min_length=1, max_length=50_000)
    canonical_sources: List[SourceReferenceBody] = Field(default_factory=list, max_length=100)
    locked_decisions: List[str] = Field(default_factory=list, max_length=100)
    constraints: List[str] = Field(default_factory=list, max_length=100)
    requested_output: List[str] = Field(default_factory=list, max_length=100)
    artifacts: List[ArtifactReferenceBody] = Field(default_factory=list, max_length=100)
    verification_commands: List[str] = Field(default_factory=list, max_length=100)
    unverified_claims: List[str] = Field(default_factory=list, max_length=100)
    conflicts: List[str] = Field(default_factory=list, max_length=100)
    risk: operating_layer.Risk = operating_layer.Risk.READ
    approval_state: str = Field(default="not_required", max_length=40)


@router.post("/operating-layer/handoff/validate")
async def validate_operating_handoff(body: HandoffBody) -> Dict[str, Any]:
    """Validate the bidirectional Claude and ChatGPT handoff contract."""
    envelope = operating_layer.HandoffEnvelope(
        handoff_id=body.handoff_id,
        from_surface=body.from_surface,
        to_surface=body.to_surface,
        goal=body.goal,
        context_summary=body.context_summary,
        canonical_sources=tuple(
            operating_layer.SourceReference(**source.model_dump())
            for source in body.canonical_sources
        ),
        locked_decisions=tuple(body.locked_decisions),
        constraints=tuple(body.constraints),
        requested_output=tuple(body.requested_output),
        artifacts=tuple(artifact.to_contract() for artifact in body.artifacts),
        verification_commands=tuple(body.verification_commands),
        unverified_claims=tuple(body.unverified_claims),
        conflicts=tuple(body.conflicts),
        risk=body.risk,
        approval_state=body.approval_state,
    )
    issues = operating_layer.validate_handoff(envelope)
    return {
        "valid": not any(issue.severity == "error" for issue in issues),
        "contract": envelope.to_dict(),
        "issues": [issue.__dict__ for issue in issues],
        "executed": False,
    }


class AuditPlanBody(BaseModel):
    producer: operating_layer.Surface
    artifact_kind: str = Field(..., min_length=1, max_length=200)


@router.post("/operating-layer/audit/plan")
async def plan_cross_model_audit(body: AuditPlanBody) -> Dict[str, Any]:
    """Return the independent verifier and evidence loop for an artifact."""
    return operating_layer.build_audit_plan(
        producer=body.producer,
        artifact_kind=body.artifact_kind,
    ).to_dict()


class AuditFindingBody(BaseModel):
    severity: str = Field(..., min_length=1, max_length=40)
    claim: str = Field(..., min_length=1, max_length=10_000)
    evidence: List[str] = Field(default_factory=list, max_length=100)
    resolved: bool = False


class AuditVerdictBody(BaseModel):
    producer: operating_layer.Surface
    verifier: operating_layer.Surface
    score: int = Field(..., ge=0, le=100)
    findings: List[AuditFindingBody] = Field(default_factory=list, max_length=500)
    verification_evidence: List[str] = Field(default_factory=list, max_length=200)
    final_artifact_sha256: str = Field(..., min_length=1, max_length=64)


@router.post("/operating-layer/audit/verdict")
async def cross_model_audit_verdict(body: AuditVerdictBody) -> Dict[str, Any]:
    """Apply the evidence gate. A score alone can never pass the artifact."""
    return operating_layer.evaluate_audit(
        producer=body.producer,
        verifier=body.verifier,
        score=body.score,
        findings=tuple(
            operating_layer.AuditFinding(
                severity=finding.severity,
                claim=finding.claim,
                evidence=tuple(finding.evidence),
                resolved=finding.resolved,
            )
            for finding in body.findings
        ),
        verification_evidence=tuple(body.verification_evidence),
        final_artifact_sha256=body.final_artifact_sha256,
    ).to_dict()


class ArtifactReturnBody(BaseModel):
    handoff_id: str = Field(..., min_length=1, max_length=120)
    receipt_id: str = Field(..., min_length=1, max_length=120)
    base_ref: str = Field(default=operating_layer.CANONICAL_REF, max_length=200)
    artifacts: List[ArtifactReferenceBody] = Field(..., min_length=1, max_length=100)


@router.post("/operating-layer/artifact-return/plan")
async def plan_operating_artifact_return(body: ArtifactReturnBody) -> Dict[str, Any]:
    """Build the approval-gated branch, receipt, and read-back plan."""
    try:
        plan = operating_layer.plan_artifact_return(
            handoff_id=body.handoff_id,
            receipt_id=body.receipt_id,
            artifacts=tuple(artifact.to_contract() for artifact in body.artifacts),
            base_ref=body.base_ref,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return plan.to_dict()


@router.get("/areas")
async def list_areas() -> Dict[str, Any]:
    """The nine Areas, with both vocabularies."""
    return {
        "count": areas_mod.AREA_COUNT,
        "source": areas_mod.SOURCE,
        "areas": [
            {
                "label": a.label,
                "filename_code": a.code,
                "covers": a.covers,
                "ruled": a.ruled,
                "drive_folder": vault.AREA_FOLDERS.get(a.label),
            }
            for a in areas_mod.AREAS
        ],
        "rule": "Never add an Area without Tee's ruling.",
    }


class CommandBody(BaseModel):
    text: str = Field(
        ..., min_length=1, max_length=4_000, description="What was said to DEVON"
    )


@router.post("/command")
async def command(body: CommandBody, current_user: CurrentUser) -> Dict[str, Any]:
    """Route one utterance. Returns what DEVON understood and what he did not do.

    Signed in only. An effect utterance raises a durable approval card, and a
    card raised by nobody in particular is exactly what an anonymous caller
    would use to fill the approval rail, so the speaker must be an account and
    the card is stamped with it.
    """
    return _devon.ask(body.text, owner_id=current_user.id).to_dict()


class DecideBody(BaseModel):
    request_id: Optional[str] = None
    token: Optional[str] = None
    decision: Optional[str] = Field(default=None, description="approve or refuse")


def _visible_to(record_owner: str, user_id: str) -> bool:
    """A card is visible to its owner. A card with no owner (raised by a lane
    that has no user in hand, such as the operator bridge) is visible to any
    signed-in account."""
    return not record_owner or record_owner == user_id


def _principal_label(current_user: CurrentUser) -> str:
    """Who ruled, taken from the login rather than from the request body."""
    name = (current_user.full_name or "").strip()
    return f"{name} <{current_user.email}>" if name else str(current_user.email)


@router.get("/approvals")
async def list_approvals(current_user: CurrentUser) -> Dict[str, Any]:
    """Everything awaiting a ruling from the signed-in account."""
    return {
        "pending": [
            {
                "request_id": r.request_id,
                "title": r.title,
                "what_happens": r.what_happens,
                "blast_radius": r.blast_radius,
                "reversible": r.reversible,
                "expires_at": r.expires_at.isoformat(),
            }
            for r in _queue.pending()
            if _visible_to(r.owner_id, current_user.id)
        ],
        "storage": _approval_storage_status(),
        "note": (
            "PostgreSQL-backed shared approval state. The one-time plaintext token "
            "is not stored or recoverable. Rulings remain human-only."
            if _queue.storage_backend == "postgres"
            else "Process-local approval queue configured explicitly for offline/local work."
        ),
    }


@router.post("/approvals/decide")
async def decide(body: DecideBody, current_user: CurrentUser) -> Dict[str, Any]:
    """Rule on a pending request. Single use, expiring, fails closed.

    The ruling is signed by the login, never by text in the body. A card that
    belongs to another account gets the queue's own unknown-id refusal, byte
    for byte, so the route confirms nothing about other accounts' queues. A
    card with no owner (raised by the operator bridge, or by a task persisted
    before owners existed) is rulable by any signed-in account. A knowledge-
    loop card can be refused here but not approved: approval needs
    DEVON_RULING_KEY, which this route never sees.
    """
    record = _queue.get(body.request_id) if body.request_id else None
    if record is not None and not _visible_to(record.owner_id, current_user.id):
        result = DecisionResult(
            False,
            NO_MATCH,
            reason=RefusalReason.UNKNOWN_ID,
            message=f"No request {body.request_id}.",
        )
    elif (
        record is not None
        and record.requested_by == KNOWLEDGE_LOOP_REQUESTER
        and (body.decision or "").strip().lower() != "refuse"
    ):
        # The proposing login holds this card's token, so an approval here
        # would be the one credential approving its own capture. The knowledge
        # loop approves through a second credential the API never returns. A
        # refusal fails closed and needs no second credential, so it stays.
        raise HTTPException(
            status_code=403,
            detail=(
                "This card is a knowledge-loop capture. It is ruled through "
                "POST /api/v1/soul/approve with its single-use token and "
                "DEVON_RULING_KEY, never here."
            ),
        )
    else:
        result = _queue.decide(
            body.request_id, body.token, body.decision, _principal_label(current_user)
        )
    return {
        "ok": result.ok,
        "approved": result.approved,
        "request_id": result.request_id,
        "state": result.state.value if result.state else None,
        "reason": result.reason.value if result.reason else None,
        "message": result.message,
    }


class ReceiptBody(BaseModel):
    text: str = Field(..., min_length=1)


@router.post("/receipt/parse")
async def parse_receipt(body: ReceiptBody) -> Dict[str, Any]:
    """Read either receipt format and report every problem found."""
    try:
        receipt = receipts.parse_receipt(body.text)
    except receipts.ReceiptError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    problems = receipts.validate(receipt)
    return {
        "format": receipt.source_format.value if receipt.source_format else None,
        "valid": not any(p.severity == "error" for p in problems),
        "receipt": {
            "date": receipt.date,
            "platform": receipt.platform,
            "areas": receipt.areas,
            "title": receipt.title,
            "summary": receipt.summary,
            "decided": receipt.decided,
            "built": receipt.built,
            "open_threads": receipt.open_threads,
            "next_action": receipt.next_action,
            "canon": receipt.canon,
            "verify": receipt.verify,
            "files_opened": receipt.files_opened,
            "unverified": receipt.unverified,
        },
        "problems": [
            {"field": p.field_name, "severity": p.severity, "message": p.message}
            for p in problems
        ],
        "produced_a_decision": receipt.produced_a_decision,
        "changes_canon": receipt.changes_canon,
    }


class NameBody(BaseModel):
    filename: str = Field(..., min_length=1)


@router.post("/naming/validate")
async def validate_name(body: NameBody) -> Dict[str, Any]:
    """Check a filename against naming convention v4."""
    parsed = naming.parse_filename(body.filename)
    return {
        "conforms": parsed.conforms,
        "area": parsed.area,
        "type_code": parsed.type_code,
        "slug": parsed.slug,
        "version": parsed.version,
        "date": parsed.date,
        "markers": list(parsed.markers),
        "protected": parsed.is_protected,
        "superseded": parsed.is_superseded,
        "warnings_in_name": list(parsed.warnings_in_name),
        "violations": [
            {"rule": v.rule, "severity": v.severity, "message": v.message}
            for v in parsed.violations
        ],
    }


class BuildNameBody(BaseModel):
    area: str
    type_code: str
    slug: str
    version: int = 1
    on_date: str
    marker: Optional[str] = None
    extension: str = "md"
    superseded: bool = False


@router.post("/naming/build")
async def build_name(body: BuildNameBody) -> Dict[str, str]:
    """Build a conforming filename, or refuse with the reason."""
    try:
        return {
            "filename": naming.build_filename(
                area=body.area,
                type_code=body.type_code,
                slug=body.slug,
                version=body.version,
                on_date=body.on_date,
                marker=body.marker,
                extension=body.extension,
                superseded=body.superseded,
            )
        }
    except naming.NamingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class CandidateBody(BaseModel):
    name: str
    drive_id: Optional[str] = None
    size_bytes: Optional[int] = None
    document_date: Optional[str] = None
    modified_time: Optional[str] = None
    created_time: Optional[str] = None
    parent_path: str = ""
    is_canon: bool = False


class PrecedenceBody(BaseModel):
    candidates: List[CandidateBody]
    disagrees_on_load_bearing: bool = False


@router.post("/precedence/resolve")
async def resolve_precedence(body: PrecedenceBody) -> Dict[str, Any]:
    """Decide which draft is current, or refuse and say why."""
    ruling = resolve(
        [Candidate(**c.model_dump()) for c in body.candidates],
        disagrees_on_load_bearing=body.disagrees_on_load_bearing,
    )
    return {
        "outcome": ruling.outcome.value,
        "auto_resolvable": ruling.auto_resolvable,
        "signal": ruling.signal.value,
        "winner": ruling.winner.name if ruling.winner else None,
        "losers": [c.name for c in ruling.losers],
        "reasons": ruling.reasons,
        "refusal_codes": ruling.refusal_codes,
        "conflict_row": ruling.conflict_row() if not ruling.auto_resolvable else None,
    }


class WriteCheckBody(BaseModel):
    filename: str
    parent_id: str
    writing_new_version: bool = False
    folder_listed: bool = False
    newest_sibling: Optional[str] = None
    newest_sibling_read: bool = False
    change: str = "substance"
    lane_supports_in_place: bool = False
    folder_contents: List[str] = Field(default_factory=list)


@router.post("/filing/check")
async def check_filing(body: WriteCheckBody) -> Dict[str, Any]:
    """Run the filing laws against a proposed write. Answers only, no effect."""
    try:
        change = filing.ChangeKind(body.change)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="change must be 'correction' or 'substance'"
        ) from exc

    request = filing.WriteRequest(
        filename=body.filename,
        parent_id=body.parent_id,
        writing_new_version=body.writing_new_version,
        sibling_evidence=filing.SiblingRead(
            folder_listed=body.folder_listed,
            newest_sibling=body.newest_sibling,
            newest_sibling_read=body.newest_sibling_read,
        ),
        change=change,
        lane_supports_in_place=body.lane_supports_in_place,
        folder_contents=tuple(body.folder_contents),
    )
    check = filing.check_write(request)
    return {
        "allowed": check.allowed,
        "summary": check.summary(),
        "laws": [
            {"law": r.law, "verdict": r.verdict.value, "message": r.message}
            for r in check.results
        ],
        "naming_violations": check.naming_violations,
        "folder_warnings": [
            {"name": n, "warnings": list(w)} for n, w in check.folder_warnings
        ],
    }


@router.get("/filing/laws")
async def list_laws() -> Dict[str, Any]:
    """The eight laws, each naming the failure that produced it."""
    return {
        "source": filing.SOURCE,
        "one_line": (
            "Read the newest file first. Write to the tree, never the root. Prove it "
            "with a read-back you validated. Never rule for Tee."
        ),
        "laws": [
            {
                "number": law.number,
                "title": law.title,
                "rule": law.rule,
                "failure_prevented": law.failure_prevented,
            }
            for law in filing.LAWS
        ],
    }


@router.get("/vault")
async def vault_map() -> Dict[str, Any]:
    """The Drive, Notion, Airtable and n8n map, with its staleness stated."""
    return {
        "read_on": vault.READ_ON,
        "caveat": vault.VERIFY_BEFORE_AUTOMATION,
        "root": vault.VAULT_ROOT,
        "folders": vault.FOLDERS,
        "known_empty": list(vault.KNOWN_EMPTY),
        "area_folders": vault.AREA_FOLDERS,
        "doctrine": vault.DOCTRINE,
        "notion": {k: v for k, v in vault.NOTION.items() if k != "thread_log_properties"},
        "notion_properties": list(vault.NOTION["thread_log_properties"]),
        "airtable": vault.AIRTABLE,
        "webhooks": vault.WEBHOOKS,
        "webhook_rule": vault.WEBHOOK_RULE,
        "workflows": vault.WORKFLOWS,
    }


@router.get("/flagship")
async def flagship_bar() -> Dict[str, Any]:
    """The ship gate: three clauses, twelve dimensions, and the thresholds."""
    return {
        "source": flagship.SOURCE,
        "clauses": [
            {"number": c.number, "title": c.title, "test": c.test} for c in flagship.CLAUSES
        ],
        "dimensions": list(flagship.DIMENSIONS),
        "thresholds": {
            "min_per_dimension": flagship.MIN_PER_DIMENSION,
            "min_mean": flagship.MIN_MEAN,
            "required_security": flagship.REQUIRED_SECURITY,
            "min_verification": flagship.MIN_VERIFICATION,
            "max_revision_cycles": flagship.MAX_REVISION_CYCLES,
        },
        "standing_rules": [
            "INSPECT, THEN HAND BACK. The human owns SHIP.",
            "FINDINGS CARRY EVIDENCE. Without one, the finding does not exist.",
            "NEVER CLAIM FIXED, TESTED, WORKS OR SAFE WITHOUT A SHOWN RUN.",
            "NEVER FABRICATE a failing input, execution id, test result or score.",
            "A SUCCESS RESPONSE IS A CLAIM, NOT A RECEIPT. READ THE STATE BACK.",
        ],
        "stale_artifact_class": {
            "shape": flagship.STALE_ARTIFACT_SHAPE,
            "defense": flagship.STALE_ARTIFACT_DEFENSE,
            "logged_instances": list(flagship.STALE_ARTIFACT_INSTANCES),
        },
    }


@router.get("/prompt")
async def devon_prompt() -> Dict[str, str]:
    """DEVON's assembled system prompt, so every surface can use the same one."""
    return {"system_prompt": persona.system_prompt()}
