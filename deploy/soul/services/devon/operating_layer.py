"""DEVON policy for the complementary ChatGPT operating layer.

This module adds contracts, not a second orchestrator. DEVON remains the
executive control plane. The policy decides which surface should receive work,
what evidence must travel with a handoff, how another model verifies the actual
artifact, and how artifacts return to this repository through a reviewable,
approval-gated branch.

The module is deliberately effect free. It does not call a model, GitHub,
ChatGPT, Claude, an app, or a scheduler. Capability adapters and human-approved
callers perform those effects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

SOURCES = {
    "repo": {
        "name": "tdveal74-cell/Meta-Supreme-Apex-Genesis-",
        "ref": "main",
        "governs": "executable DEVON behavior and Command Center state",
    },
    "standing_instructions": {
        "title": "SYS_SPEC_llm-standing-instructions_v3_2026-08-21.md",
        "version": "3",
        "governs": "cross-model behavior and receipts",
        "access": "resolve through an authorized DEVON source read",
    },
    "precedence_doctrine": {
        "title": "SYS_SPEC_precedence-doctrine_v2_2026-08-06.md",
        "version": "2",
        "governs": "version precedence and human conflict rulings",
        "access": "resolve through an authorized DEVON source read",
    },
    "capture_protocol": {
        "title": "DEVON Cross-Platform Capture Protocol.md",
        "version": "1",
        "governs": "cross-platform artifact and receipt return",
        "access": "resolve through an authorized DEVON source read",
    },
    "openai_work": {
        "url": "https://learn.chatgpt.com/docs/get-started-with-work",
        "read_on": "2026-08-26",
    },
    "openai_scheduled_tasks": {
        "url": "https://learn.chatgpt.com/docs/automations",
        "read_on": "2026-08-26",
    },
    "openai_deep_research": {
        "url": "https://developers.openai.com/api/docs/guides/deep-research",
        "read_on": "2026-08-26",
    },
}

POLICY_VERSION = "devon.operating-layer.v1"
HANDOFF_VERSION = "devon.handoff.v1"
AUDIT_VERSION = "devon.cross-model-audit.v1"
RETURN_VERSION = "devon.artifact-return.v1"
QUALITY_THRESHOLD = 99
CANONICAL_REPOSITORY = "tdveal74-cell/Meta-Supreme-Apex-Genesis-"
CANONICAL_REF = "main"


class Surface(str, Enum):
    """A capability surface DEVON may route to."""

    DEVON = "devon"
    CLAUDE = "claude"
    CHATGPT = "chatgpt"
    CODEX = "codex"
    DEEP_RESEARCH = "deep_research"
    WORK = "work"
    CONNECTED_APPS = "connected_apps"
    SCHEDULED_TASKS = "scheduled_tasks"


class Need(str, Enum):
    """Task properties used by the deterministic routing policy."""

    CONVERSATION = "conversation"
    SYSTEM_ARCHITECTURE = "system_architecture"
    CODE_CHANGE = "code_change"
    REPOSITORY_READ = "repository_read"
    REPOSITORY_WRITE = "repository_write"
    LIVE_WEB = "live_web"
    DEEP_EVIDENCE = "deep_evidence"
    MULTI_SOURCE = "multi_source"
    FILE_ARTIFACT = "file_artifact"
    CONNECTED_APP_READ = "connected_app_read"
    CONNECTED_APP_WRITE = "connected_app_write"
    RECURRING = "recurring"
    FUTURE_EVENT = "future_event"
    LOCAL_MACHINE = "local_machine"
    CANON_WRITE = "canon_write"
    HUMAN_RULING = "human_ruling"


class Risk(str, Enum):
    READ = "read"
    WRITE = "write"
    HIGH_IMPACT = "high_impact"


SURFACE_POLICIES: Dict[Surface, Dict[str, Any]] = {
    Surface.CLAUDE: {
        "use_when": [
            "DEVON canon or cross-system architecture needs the established Claude lane",
            "Notion, Airtable, n8n, Drive, and repository facts must be reconciled",
            "ChatGPT hands back a source conflict that it cannot resolve",
        ],
        "must_not": ["make Tee's ruling", "silently supersede a contradiction"],
    },
    Surface.CHATGPT: {
        "use_when": [
            "the task is conversational synthesis, planning, critique, or a short draft",
            "the operator needs one front door across Work, apps, research, and tasks",
            "Claude hands off a reviewable result for operator-facing completion",
        ],
        "must_not": ["replace DEVON", "claim external capability is live without a probe"],
    },
    Surface.CODEX: {
        "use_when": [
            "the task changes, tests, audits, or reviews a real code repository",
            "local files, shell commands, CI evidence, or a reviewable patch are required",
        ],
        "must_not": ["merge an approval-gated write without authority"],
    },
    Surface.DEEP_RESEARCH: {
        "use_when": [
            "current multi-source research needs citations and source comparison",
            "the question cannot be answered from canonical DEVON sources alone",
        ],
        "must_not": ["write canon", "treat a search result as proof without opening it"],
    },
    Surface.WORK: {
        "use_when": [
            "a multi-step knowledge task must produce a reviewable file or workflow",
            "multiple sources, plugins, tools, or substantial execution time are involved",
        ],
        "must_not": ["bypass a consequential-action approval"],
    },
    Surface.CONNECTED_APPS: {
        "use_when": [
            "the source of truth lives in an authorized external service",
            "the task needs a read or a specifically approved action in that service",
        ],
        "must_not": ["guess identity, scope, access, or write success"],
    },
    Surface.SCHEDULED_TASKS: {
        "use_when": [
            "work must recur, run later, or wake from a supported app event",
            "the prompt and durable source material have been tested first",
        ],
        "must_not": ["hide cadence in the prompt", "assume local files are available to web runs"],
    },
}


SOURCE_OF_TRUTH_RULES: Tuple[str, ...] = (
    "Tee's explicit current ruling outranks every model and artifact.",
    "Current main owns executable DEVON behavior and the current Command Center.",
    "Current DEVON records own studio canon, prior decisions, and external system facts after a live read.",
    "A same-artifact version may use precedence. A load-bearing contradiction never does.",
    "When main and a DEVON record disagree on a load-bearing fact, DEVON opens a conflict and Tee rules.",
    "A model output is a proposal until the artifact is read back and its evidence is verified.",
    "Configured, available, live, and verified are separate states and must be reported separately.",
)


@dataclass(frozen=True)
class TaskProfile:
    goal: str
    needs: Tuple[Need, ...] = ()
    risk: Risk = Risk.READ
    source_systems: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.goal.strip():
            raise ValueError("task goal is empty")


@dataclass(frozen=True)
class RoutingDecision:
    policy_version: str
    primary: Surface
    companions: Tuple[Surface, ...]
    reason_codes: Tuple[str, ...]
    rationale: str
    approval_required: bool
    tee_ruling_required: bool
    receipt_required: bool
    required_evidence: Tuple[str, ...]
    return_to: Surface = Surface.DEVON

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_version": self.policy_version,
            "primary": self.primary.value,
            "companions": [surface.value for surface in self.companions],
            "reason_codes": list(self.reason_codes),
            "rationale": self.rationale,
            "approval_required": self.approval_required,
            "tee_ruling_required": self.tee_ruling_required,
            "receipt_required": self.receipt_required,
            "required_evidence": list(self.required_evidence),
            "return_to": self.return_to.value,
            "orchestrator": "DEVON",
        }


def _ordered_unique(surfaces: Iterable[Surface]) -> Tuple[Surface, ...]:
    seen: set[Surface] = set()
    ordered: List[Surface] = []
    for surface in surfaces:
        if surface not in seen:
            seen.add(surface)
            ordered.append(surface)
    return tuple(ordered)


def route(profile: TaskProfile) -> RoutingDecision:
    """Select a capability surface without executing or delegating the task."""

    needs = set(profile.needs)
    approval_required = profile.risk is not Risk.READ or bool(
        needs
        & {
            Need.REPOSITORY_WRITE,
            Need.CONNECTED_APP_WRITE,
            Need.CANON_WRITE,
            Need.HUMAN_RULING,
        }
    )
    tee_ruling_required = Need.HUMAN_RULING in needs or Need.CANON_WRITE in needs
    evidence: List[str] = [
        "exact canonical source identifiers and the time they were read",
        "artifact paths or URLs returned by the selected surface",
    ]
    companions: List[Surface] = []

    if Need.HUMAN_RULING in needs:
        primary = Surface.DEVON
        codes = ("human-ruling", "hold-at-control-plane")
        rationale = "No model receives the ruling. DEVON holds the conflict for Tee."
    elif Need.CANON_WRITE in needs:
        primary = Surface.CLAUDE
        codes = ("canon-write", "established-canon-lane")
        rationale = "Claude receives the canon proposal, while DEVON and Tee retain authority."
        evidence.append("newest sibling read and explicit conflict check before any write")
    elif needs & {Need.CODE_CHANGE, Need.REPOSITORY_READ, Need.REPOSITORY_WRITE, Need.LOCAL_MACHINE}:
        primary = Surface.CODEX
        codes = ("repository-work", "testable-patch")
        rationale = "Codex owns repository inspection, implementation, and executable verification."
        evidence.extend(("base commit SHA", "commands run with exit codes", "final diff read-back"))
    elif needs & {Need.RECURRING, Need.FUTURE_EVENT}:
        primary = Surface.SCHEDULED_TASKS
        codes = ("deferred-or-recurring", "durable-trigger")
        rationale = "Scheduled Tasks owns the trigger. DEVON still owns routing and receipt acceptance."
        if Need.CONNECTED_APP_READ in needs or Need.CONNECTED_APP_WRITE in needs:
            companions.append(Surface.CONNECTED_APPS)
        elif Need.LIVE_WEB in needs and Need.DEEP_EVIDENCE in needs:
            companions.append(Surface.DEEP_RESEARCH)
        elif Need.FILE_ARTIFACT in needs or Need.MULTI_SOURCE in needs:
            companions.append(Surface.WORK)
        else:
            companions.append(Surface.CHATGPT)
        evidence.append("saved schedule or event trigger plus first successful run read-back")
    elif needs & {Need.CONNECTED_APP_READ, Need.CONNECTED_APP_WRITE}:
        primary = Surface.CONNECTED_APPS
        codes = ("connected-source", "authorized-app")
        rationale = "The connected app owns the external source read or approved effect."
        if Need.MULTI_SOURCE in needs or Need.FILE_ARTIFACT in needs:
            companions.append(Surface.WORK)
        evidence.append("connector read-back from the exact item acted on")
    elif Need.LIVE_WEB in needs and (
        Need.DEEP_EVIDENCE in needs or Need.MULTI_SOURCE in needs
    ):
        primary = Surface.DEEP_RESEARCH
        codes = ("current-research", "source-comparison")
        rationale = "Deep Research owns current multi-source evidence and citations."
        evidence.append("opened primary sources with publication and event dates")
    elif Need.FILE_ARTIFACT in needs or Need.MULTI_SOURCE in needs:
        primary = Surface.WORK
        codes = ("reviewable-artifact", "multi-step-work")
        rationale = "ChatGPT Work owns substantial multi-step work that produces a reviewable artifact."
        evidence.append("reviewable output file and source manifest")
    elif Need.SYSTEM_ARCHITECTURE in needs:
        primary = Surface.CLAUDE
        codes = ("system-architecture", "cross-system-reconciliation")
        rationale = "Claude receives cross-system architecture that depends on the established DEVON lane."
        evidence.append("actual DEVON sources opened in the current session")
    else:
        primary = Surface.CHATGPT
        codes = ("conversation", "operator-front-door")
        rationale = "ChatGPT owns direct synthesis, planning, critique, and short drafts."

    if primary in {Surface.CLAUDE, Surface.CHATGPT, Surface.WORK, Surface.DEEP_RESEARCH}:
        if Need.CODE_CHANGE in needs:
            companions.append(Surface.CODEX)
    if primary is not Surface.DEVON:
        companions.append(Surface.DEVON)

    return RoutingDecision(
        policy_version=POLICY_VERSION,
        primary=primary,
        companions=_ordered_unique(companions),
        reason_codes=codes,
        rationale=rationale,
        approval_required=approval_required,
        tee_ruling_required=tee_ruling_required,
        receipt_required=True,
        required_evidence=tuple(evidence),
    )


@dataclass(frozen=True)
class SourceReference:
    title: str
    uri: str
    read_at: str
    revision: str = ""
    content_hash: str = ""


@dataclass(frozen=True)
class ArtifactReference:
    path: str
    role: str
    sha256: str = ""
    media_type: str = "application/octet-stream"
    verified: bool = False


@dataclass(frozen=True)
class HandoffEnvelope:
    handoff_id: str
    from_surface: Surface
    to_surface: Surface
    goal: str
    context_summary: str
    canonical_sources: Tuple[SourceReference, ...]
    locked_decisions: Tuple[str, ...] = ()
    constraints: Tuple[str, ...] = ()
    requested_output: Tuple[str, ...] = ()
    artifacts: Tuple[ArtifactReference, ...] = ()
    verification_commands: Tuple[str, ...] = ()
    unverified_claims: Tuple[str, ...] = ()
    conflicts: Tuple[str, ...] = ()
    risk: Risk = Risk.READ
    approval_state: str = "not_required"
    contract_version: str = HANDOFF_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "handoff_id": self.handoff_id,
            "from_surface": self.from_surface.value,
            "to_surface": self.to_surface.value,
            "goal": self.goal,
            "context_summary": self.context_summary,
            "canonical_sources": [source.__dict__ for source in self.canonical_sources],
            "locked_decisions": list(self.locked_decisions),
            "constraints": list(self.constraints),
            "requested_output": list(self.requested_output),
            "artifacts": [artifact.__dict__ for artifact in self.artifacts],
            "verification_commands": list(self.verification_commands),
            "unverified_claims": list(self.unverified_claims),
            "conflicts": list(self.conflicts),
            "risk": self.risk.value,
            "approval_state": self.approval_state,
            "return_to": "DEVON",
        }


@dataclass(frozen=True)
class ContractIssue:
    field: str
    severity: str
    message: str


def validate_handoff(envelope: HandoffEnvelope) -> List[ContractIssue]:
    """Validate the Claude to ChatGPT or ChatGPT to Claude transfer contract."""

    issues: List[ContractIssue] = []
    allowed_pair = {envelope.from_surface, envelope.to_surface} == {
        Surface.CLAUDE,
        Surface.CHATGPT,
    }
    if not allowed_pair:
        issues.append(
            ContractIssue(
                "surfaces",
                "error",
                "This contract is reserved for Claude and ChatGPT handoffs.",
            )
        )
    if not envelope.handoff_id.strip():
        issues.append(ContractIssue("handoff_id", "error", "handoff id is required"))
    if not envelope.goal.strip():
        issues.append(ContractIssue("goal", "error", "goal is required"))
    if not envelope.context_summary.strip():
        issues.append(ContractIssue("context_summary", "error", "context summary is required"))
    if not envelope.canonical_sources:
        issues.append(
            ContractIssue(
                "canonical_sources",
                "error",
                "At least one exact source reference is required.",
            )
        )
    for index, source in enumerate(envelope.canonical_sources):
        if not source.title.strip() or not source.uri.strip() or not source.read_at.strip():
            issues.append(
                ContractIssue(
                    f"canonical_sources[{index}]",
                    "error",
                    "title, uri, and read_at are required",
                )
            )
    if envelope.risk is not Risk.READ and envelope.approval_state not in {
        "requested",
        "approved",
        "refused",
    }:
        issues.append(
            ContractIssue(
                "approval_state",
                "error",
                "Write and high-impact handoffs must carry an explicit approval state.",
            )
        )
    if envelope.conflicts and envelope.approval_state != "refused":
        issues.append(
            ContractIssue(
                "conflicts",
                "error",
                "A handoff with unresolved conflicts must stop for Tee instead of proceeding.",
            )
        )
    for index, artifact in enumerate(envelope.artifacts):
        issues.extend(_artifact_issues(artifact, f"artifacts[{index}]"))
    if not envelope.requested_output:
        issues.append(
            ContractIssue(
                "requested_output",
                "warning",
                "The receiving surface has no explicit output contract.",
            )
        )
    return issues


@dataclass(frozen=True)
class AuditFinding:
    severity: str
    claim: str
    evidence: Tuple[str, ...] = ()
    resolved: bool = False


@dataclass(frozen=True)
class AuditPlan:
    audit_version: str
    producer: Surface
    verifier: Surface
    artifact_kind: str
    stages: Tuple[str, ...]
    acceptance: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audit_version": self.audit_version,
            "producer": self.producer.value,
            "verifier": self.verifier.value,
            "artifact_kind": self.artifact_kind,
            "stages": list(self.stages),
            "acceptance": list(self.acceptance),
            "threshold": QUALITY_THRESHOLD,
            "final_authority": "Tee",
        }


def build_audit_plan(producer: Surface, artifact_kind: str) -> AuditPlan:
    """Choose a different surface to verify the artifact that actually exists."""

    kind = artifact_kind.strip().lower()
    if not kind:
        raise ValueError("artifact kind is empty")
    if kind in {"code", "repository", "api", "command_center"}:
        verifier = Surface.CLAUDE if producer is Surface.CODEX else Surface.CODEX
    elif producer is Surface.CLAUDE:
        verifier = Surface.CHATGPT
    else:
        verifier = Surface.CLAUDE
    if verifier is producer:
        verifier = Surface.CHATGPT if producer is not Surface.CHATGPT else Surface.CLAUDE
    return AuditPlan(
        audit_version=AUDIT_VERSION,
        producer=producer,
        verifier=verifier,
        artifact_kind=kind,
        stages=(
            "Producer returns the exact artifact, source manifest, and claimed checks.",
            "Independent verifier opens the artifact and reruns applicable checks.",
            "Verifier records evidence-backed findings without rewriting the claim history.",
            "Producer repairs failed elements and returns a new artifact hash.",
            "Verifier reruns failed checks plus regression checks against the new hash.",
            "DEVON accepts the receipt or routes unresolved conflict to Tee.",
        ),
        acceptance=(
            f"evidence-backed score is at least {QUALITY_THRESHOLD}",
            "no unresolved critical or high finding remains",
            "producer and verifier are different surfaces",
            "verification evidence names commands, outputs, or opened artifacts",
            "the accepted receipt references the final artifact hash",
        ),
    )


@dataclass(frozen=True)
class AuditVerdict:
    accepted: bool
    score: int
    reasons: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {"accepted": self.accepted, "score": self.score, "reasons": list(self.reasons)}


def evaluate_audit(
    *,
    producer: Surface,
    verifier: Surface,
    score: int,
    findings: Sequence[AuditFinding],
    verification_evidence: Sequence[str],
    final_artifact_sha256: str,
) -> AuditVerdict:
    reasons: List[str] = []
    if producer is verifier:
        reasons.append("producer and verifier are the same surface")
    if score < QUALITY_THRESHOLD:
        reasons.append(f"score {score} is below {QUALITY_THRESHOLD}")
    unresolved = [
        finding
        for finding in findings
        if finding.severity.lower() in {"critical", "high"} and not finding.resolved
    ]
    if unresolved:
        reasons.append(f"{len(unresolved)} unresolved critical or high finding(s) remain")
    missing_evidence = [finding for finding in findings if not finding.evidence]
    if missing_evidence:
        reasons.append(f"{len(missing_evidence)} finding(s) have no evidence")
    if not any(item.strip() for item in verification_evidence):
        reasons.append("no verification evidence was returned")
    if not re.fullmatch(r"[0-9a-f]{64}", final_artifact_sha256.lower()):
        reasons.append("final artifact sha256 is missing or invalid")
    return AuditVerdict(accepted=not reasons, score=score, reasons=tuple(reasons))


@dataclass(frozen=True)
class ArtifactReturnPlan:
    return_version: str
    repository: str
    base_ref: str
    proposed_branch: str
    handoff_manifest_path: str
    receipt_path: str
    artifacts: Tuple[ArtifactReference, ...]
    approval_required: bool
    write_tools: Tuple[str, ...]
    verification: Tuple[str, ...]
    issues: Tuple[ContractIssue, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "return_version": self.return_version,
            "repository": self.repository,
            "base_ref": self.base_ref,
            "proposed_branch": self.proposed_branch,
            "handoff_manifest_path": self.handoff_manifest_path,
            "receipt_path": self.receipt_path,
            "artifacts": [artifact.__dict__ for artifact in self.artifacts],
            "approval_required": self.approval_required,
            "write_tools": list(self.write_tools),
            "verification": list(self.verification),
            "issues": [issue.__dict__ for issue in self.issues],
            "executed": False,
            "merge_authority": "Tee through DEVON approval",
        }


def _safe_segment(value: str, field_name: str) -> str:
    cleaned = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,119}", cleaned):
        raise ValueError(f"{field_name} is not a safe repository path segment")
    return cleaned


def _artifact_issues(artifact: ArtifactReference, field_name: str) -> List[ContractIssue]:
    issues: List[ContractIssue] = []
    path = PurePosixPath(artifact.path)
    if path.is_absolute() or ".." in path.parts or str(path) in {"", "."}:
        issues.append(ContractIssue(field_name, "error", "artifact path must stay inside the repository"))
    if artifact.sha256 and not re.fullmatch(r"[0-9a-f]{64}", artifact.sha256.lower()):
        issues.append(ContractIssue(field_name, "error", "artifact sha256 is invalid"))
    if artifact.verified and not artifact.sha256:
        issues.append(ContractIssue(field_name, "error", "a verified artifact must carry its sha256"))
    return issues


def plan_artifact_return(
    *,
    handoff_id: str,
    receipt_id: str,
    artifacts: Sequence[ArtifactReference],
    base_ref: str = CANONICAL_REF,
) -> ArtifactReturnPlan:
    """Plan the reviewable return path. The caller still owns every effect."""

    if base_ref != CANONICAL_REF:
        raise ValueError("artifact returns must start from current main")
    safe_handoff = _safe_segment(handoff_id, "handoff_id")
    safe_receipt = _safe_segment(receipt_id, "receipt_id")
    issues: List[ContractIssue] = []
    for index, artifact in enumerate(artifacts):
        issues.extend(_artifact_issues(artifact, f"artifacts[{index}]"))
    if not artifacts:
        issues.append(ContractIssue("artifacts", "error", "at least one artifact is required"))
    return ArtifactReturnPlan(
        return_version=RETURN_VERSION,
        repository=CANONICAL_REPOSITORY,
        base_ref=CANONICAL_REF,
        proposed_branch=f"devon/handoff/{safe_handoff}",
        handoff_manifest_path=f"docs/devon/handoffs/{safe_handoff}.json",
        receipt_path=f"docs/devon/receipts/{safe_receipt}.json",
        artifacts=tuple(artifacts),
        approval_required=True,
        write_tools=(
            "github.create_branch",
            "github.write_file",
            "github.create_pull_request",
        ),
        verification=(
            "read every returned path at the created commit SHA",
            "compare each read-back sha256 with the manifest",
            "run repository-native tests against the returned commit",
            "read the pull request status and checks before claiming return complete",
            "merge only after Tee's ruling through the existing approval authority",
        ),
        issues=tuple(issues),
    )


def capability_status(runtime_commit: Optional[str] = None) -> Dict[str, Any]:
    """Represent what this API can prove without inventing external live state."""

    external = {
        Surface.CLAUDE,
        Surface.CHATGPT,
        Surface.CODEX,
        Surface.DEEP_RESEARCH,
        Surface.WORK,
        Surface.CONNECTED_APPS,
        Surface.SCHEDULED_TASKS,
    }
    surfaces = []
    for surface in Surface:
        if surface is Surface.DEVON:
            surfaces.append(
                {
                    "surface": surface.value,
                    "role": "executive control plane",
                    "contract_ready": True,
                    "live_verified": True,
                    "status": "live",
                    "evidence": "this DEVON API returned the status payload",
                }
            )
            continue
        policy = SURFACE_POLICIES[surface]
        surfaces.append(
            {
                "surface": surface.value,
                "role": policy["use_when"][0],
                "contract_ready": surface in external,
                "live_verified": False,
                "status": "contract_ready",
                "evidence": "policy and handoff contract are present. External session state is not introspectable here",
            }
        )
    return {
        "policy_version": POLICY_VERSION,
        "canonical_orchestrator": "DEVON",
        "second_orchestrator_created": False,
        "repository": CANONICAL_REPOSITORY,
        "canonical_ref": CANONICAL_REF,
        "runtime_commit": runtime_commit,
        "source_of_truth_rules": list(SOURCE_OF_TRUTH_RULES),
        "surfaces": surfaces,
        "cerebras": {
            "role": "preserved intelligence provider layer",
            "routing_authority": False,
            "live_status_source": "/api/v1/intelligence/status",
            "note": "Provider identity remains separate from work-surface routing.",
        },
        "preserved_boundaries": [
            "existing DEVON approval authority",
            "passkey and password recovery path",
            "operator bridge and dedicated real-shell boundary",
            "effect receipts, leases, and idempotency ledger",
            "heartbeat and DEVON persona",
            "current Unified Command Center",
        ],
    }
