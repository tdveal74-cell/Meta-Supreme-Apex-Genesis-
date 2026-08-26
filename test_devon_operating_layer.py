"""Policy, handoff, audit, return-path, and API coverage for ChatGPT beside DEVON."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from services.devon.operating_layer import (
    SOURCES,
    ArtifactReference,
    AuditFinding,
    HandoffEnvelope,
    Need,
    Risk,
    SourceReference,
    Surface,
    TaskProfile,
    build_audit_plan,
    capability_status,
    evaluate_audit,
    plan_artifact_return,
    route,
    validate_handoff,
)

HASH_A = "a" * 64
ECOSYSTEM_RENDER_SHA256 = "1e4445c345e3197c0e3c39bdf677e89712c89faa99b94be82ef89954ba9a2ba1"
ROOT = Path(__file__).resolve().parent

OPERATING_LAYER_PATHS = {
    "/api/v1/devon/operating-layer/status",
    "/api/v1/devon/operating-layer/route",
    "/api/v1/devon/operating-layer/handoff/validate",
    "/api/v1/devon/operating-layer/audit/plan",
    "/api/v1/devon/operating-layer/audit/verdict",
    "/api/v1/devon/operating-layer/artifact-return/plan",
}


def test_chatgpt_is_the_operator_front_door_not_a_second_orchestrator():
    decision = route(TaskProfile(goal="Turn these notes into a concise plan"))
    assert decision.primary is Surface.CHATGPT
    assert decision.return_to is Surface.DEVON
    status = capability_status()
    assert status["canonical_orchestrator"] == "DEVON"
    assert status["second_orchestrator_created"] is False


def test_public_policy_sources_do_not_publish_connected_source_ids():
    assert all("drive_id" not in source for source in SOURCES.values())


@pytest.mark.parametrize(
    "project",
    ["The Quiet Operator", "The Shadow We Share", "NCO Forge", "Ascension Caudex"],
)
def test_ecosystem_map_and_command_center_name_every_portfolio_property(project):
    ecosystem_map = (
        ROOT / "docs/devon/SYS_SPEC_devon-ecosystem-control-map_v1_2026-08-26.md"
    ).read_text()
    command_center = (
        ROOT / "apps/web/components/command-center/UnifiedCommandCenter.tsx"
    ).read_text()
    assert project in ecosystem_map
    assert project in command_center


def test_rendered_ecosystem_map_matches_its_receipt_hash():
    rendered = (
        ROOT / "docs/devon/assets/SYS_PROOF_devon-ecosystem-control-map_v2_2026-08-26.jpg"
    ).read_bytes()
    assert rendered.startswith(b"\xff\xd8\xff")
    assert sha256(rendered).hexdigest() == ECOSYSTEM_RENDER_SHA256


@pytest.mark.parametrize(
    "needs,expected",
    [
        ((Need.CODE_CHANGE, Need.REPOSITORY_WRITE), Surface.CODEX),
        ((Need.LIVE_WEB, Need.DEEP_EVIDENCE), Surface.DEEP_RESEARCH),
        ((Need.FILE_ARTIFACT, Need.MULTI_SOURCE), Surface.WORK),
        ((Need.CONNECTED_APP_READ,), Surface.CONNECTED_APPS),
        ((Need.RECURRING,), Surface.SCHEDULED_TASKS),
        ((Need.SYSTEM_ARCHITECTURE,), Surface.CLAUDE),
        ((Need.CANON_WRITE,), Surface.CLAUDE),
        ((Need.HUMAN_RULING,), Surface.DEVON),
    ],
)
def test_routing_policy_selects_the_capability_not_the_starting_chat(needs, expected):
    decision = route(TaskProfile(goal="Do the work", needs=needs))
    assert decision.primary is expected
    assert decision.receipt_required


def test_scheduled_app_work_keeps_the_trigger_and_action_surfaces_distinct():
    decision = route(
        TaskProfile(
            goal="Run after an app event",
            needs=(Need.FUTURE_EVENT, Need.CONNECTED_APP_WRITE),
            risk=Risk.WRITE,
        )
    )
    assert decision.primary is Surface.SCHEDULED_TASKS
    assert Surface.CONNECTED_APPS in decision.companions
    assert decision.approval_required


def _valid_handoff() -> HandoffEnvelope:
    return HandoffEnvelope(
        handoff_id="sys-20260826-001",
        from_surface=Surface.CLAUDE,
        to_surface=Surface.CHATGPT,
        goal="Prepare the operator-facing handoff",
        context_summary="Claude inspected the canonical DEVON sources and produced a reviewable result.",
        canonical_sources=(
            SourceReference(
                title="current main",
                uri="https://github.com/tdveal74-cell/Meta-Supreme-Apex-Genesis-/tree/main",
                read_at="2026-08-26T08:00:00-04:00",
                revision="19d8ff3ed4ad374923d408cc8a8c0af5c00ebcf6",
            ),
        ),
        requested_output=("return a verified artifact and DEVON receipt",),
    )


def test_claude_chatgpt_handoff_requires_exact_sources_and_output_contract():
    assert validate_handoff(_valid_handoff()) == []

    invalid = HandoffEnvelope(
        handoff_id="x",
        from_surface=Surface.CODEX,
        to_surface=Surface.CHATGPT,
        goal="hand off",
        context_summary="context",
        canonical_sources=(),
    )
    issues = validate_handoff(invalid)
    assert {issue.field for issue in issues} >= {
        "surfaces",
        "canonical_sources",
        "requested_output",
    }


def test_unresolved_handoff_conflict_stops_instead_of_crossing_models():
    base = _valid_handoff()
    blocked = HandoffEnvelope(
        **{
            **base.__dict__,
            "conflicts": ("main and Drive disagree on the approval owner",),
        }
    )
    issues = validate_handoff(blocked)
    assert any(issue.field == "conflicts" and issue.severity == "error" for issue in issues)


def test_cross_model_audit_is_independent_and_evidence_gated():
    plan = build_audit_plan(Surface.CODEX, "code")
    assert plan.verifier is not plan.producer

    passed = evaluate_audit(
        producer=Surface.CODEX,
        verifier=Surface.CLAUDE,
        score=99,
        findings=(),
        verification_evidence=("pytest: 42 passed", "pnpm build: exit 0"),
        final_artifact_sha256=HASH_A,
    )
    assert passed.accepted

    failed = evaluate_audit(
        producer=Surface.CODEX,
        verifier=Surface.CODEX,
        score=100,
        findings=(
            AuditFinding(
                severity="high",
                claim="status collapses configured and live",
                evidence=("status payload",),
                resolved=False,
            ),
        ),
        verification_evidence=("pytest: 42 passed",),
        final_artifact_sha256=HASH_A,
    )
    assert not failed.accepted
    assert any("same surface" in reason for reason in failed.reasons)
    assert any("unresolved" in reason for reason in failed.reasons)


def test_artifact_return_stays_on_a_branch_and_requires_readback():
    plan = plan_artifact_return(
        handoff_id="sys-20260826-001",
        receipt_id="receipt-20260826-001",
        artifacts=(
            ArtifactReference(
                path="docs/devon/report.md",
                role="handoff report",
                sha256=HASH_A,
                media_type="text/markdown",
                verified=True,
            ),
        ),
    )
    assert plan.base_ref == "main"
    assert plan.proposed_branch.startswith("devon/handoff/")
    assert plan.approval_required
    assert "github.create_pull_request" in plan.write_tools
    assert any("read every returned path" in step for step in plan.verification)
    assert plan.issues == ()


def test_artifact_return_refuses_path_escape_and_unverified_hash_claims():
    plan = plan_artifact_return(
        handoff_id="safe-id",
        receipt_id="safe-receipt",
        artifacts=(
            ArtifactReference(
                path="../outside.txt",
                role="bad",
                verified=True,
            ),
        ),
    )
    assert any(issue.severity == "error" for issue in plan.issues)


def test_status_keeps_cerebras_as_intelligence_not_routing_authority():
    status = capability_status(runtime_commit="abc123")
    assert status["runtime_commit"] == "abc123"
    assert status["cerebras"]["routing_authority"] is False
    external = [item for item in status["surfaces"] if item["surface"] != "devon"]
    assert external
    assert all(item["status"] == "contract_ready" for item in external)
    assert all(item["live_verified"] is False for item in external)


def test_openapi_exposes_all_operating_layer_contracts():
    from app.main import app

    assert OPERATING_LAYER_PATHS <= set(app.openapi()["paths"])


@pytest.mark.asyncio
async def test_api_exposes_live_policy_and_route_without_executing():
    from app.api.v1.devon import OperatingRouteBody, operating_layer_status, route_operating_layer

    status = await operating_layer_status()
    assert status["canonical_orchestrator"] == "DEVON"

    result = await route_operating_layer(
        OperatingRouteBody(
            goal="Inspect and change the repository",
            needs=[Need.CODE_CHANGE, Need.REPOSITORY_WRITE],
            risk=Risk.WRITE,
        )
    )
    assert result["primary"] == "codex"
    assert result["approval_required"] is True
    assert result["return_to"] == "devon"
