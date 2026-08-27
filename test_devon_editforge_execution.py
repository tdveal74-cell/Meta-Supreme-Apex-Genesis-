"""Contract and HTTP-boundary tests for DEVON-controlled EditForge execution."""

from __future__ import annotations

import httpx
import pytest

from app.services.editforge_client import EditForgeClient, EditForgeConfig
from services.devon.editforge_execution import (
    EDIT_COMMAND_SCHEMA,
    EditForgeExecutionError,
    approval_consequence,
    approval_matches,
    build_command,
    validate_intent,
    validate_receipt,
)

HASH = "a" * 64


def test_openapi_exposes_the_governed_editforge_effect_lane():
    from app.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/devon/editforge/status" in paths
    assert "/api/v1/devon/editforge/authorize" in paths
    assert "/api/v1/devon/editforge/execute" in paths
    assert "/api/v1/devon/editforge/executions/{command_id}" in paths
    assert "/api/v1/devon/editforge/executions/{command_id}/{action}" in paths
    assert not any("publish" in path or "delete" in path for path in paths if "/devon/editforge/" in path)


def intent(**overrides):
    value = {
        "commandId": "cmd-20260826-001",
        "projectId": "project-tqo-001",
        "cutId": "cut-tqo-001",
        "property": "tqo",
        "deliverable": "long-form",
        "source": {"uri": "https://media.example/source.mp4", "sha256": HASH},
        "identity": {
            "cloneId": "tee-clone-v1",
            "voiceId": "tee-voice-v1",
            "version": "tee-identity-v1",
            "consentRecorded": True,
        },
        "canon": {"version": "tqo-canon-v1", "locked": True},
        "operations": [
            {"id": "motion", "type": "generate-full-motion", "params": {"maxCredits": 30}},
            {"id": "preview", "type": "render-preview", "params": {}},
        ],
        "output": {
            "mode": "preview",
            "width": 1920,
            "height": 1080,
            "fps": 24,
            "container": "mp4",
        },
    }
    value.update(overrides)
    return value


def test_exact_approval_hash_cannot_be_reused_for_changed_edits():
    original = intent()
    consequence = approval_consequence(original)
    assert approval_matches(what_happens=consequence, intent=original)
    changed = intent(output={**original["output"], "width": 3840})
    assert not approval_matches(what_happens=consequence, intent=changed)


def test_command_preserves_devon_as_authority_and_scopes_every_operation():
    command = build_command(intent(), approval_id="REQ-123", approved_by="Tee")
    assert command["schema"] == EDIT_COMMAND_SCHEMA
    assert command["issuedBy"] == "DEVON"
    assert command["authorization"]["approvalId"] == "REQ-123"
    assert command["authorization"]["scopes"] == [
        "edit:generate-full-motion",
        "edit:render-preview",
    ]


def test_micro_drama_without_full_motion_is_refused():
    value = intent(
        deliverable="micro-drama",
        operations=[{"id": "preview", "type": "render-preview", "params": {}}],
    )
    assert any("full motion" in issue for issue in validate_intent(value))


def test_provider_work_requires_an_exact_spend_ceiling():
    value = intent(
        operations=[
            {"id": "voice", "type": "synthesize-voice", "params": {"text": "Ready."}},
            {"id": "motion", "type": "generate-full-motion", "params": {}},
            {"id": "sync", "type": "lip-sync", "params": {"maxCredits": False}},
            {"id": "preview", "type": "render-preview", "params": {}},
        ]
    )
    issues = validate_intent(value)
    assert any("maxCharacters" in issue for issue in issues)
    assert sum("maxCredits" in issue for issue in issues) == 2


def test_provider_ceilings_are_visible_and_hash_bound_in_approval():
    value = intent(
        operations=[
            {"id": "voice", "type": "synthesize-voice", "params": {"text": "Ready.", "maxCharacters": 100}},
            {"id": "sync", "type": "lip-sync", "params": {"maxCredits": 20}},
            {"id": "preview", "type": "render-preview", "params": {}},
        ]
    )
    consequence = approval_consequence(value)
    assert "voice characters <= 100" in consequence
    assert "lip-sync credits <= 20" in consequence
    changed = intent(operations=[*value["operations"]])
    changed["operations"][1] = {**changed["operations"][1], "params": {"maxCredits": 40}}
    assert not approval_matches(what_happens=consequence, intent=changed)


def test_project_canon_cannot_cross_properties():
    value = intent(property="tsws", canon={"version": "tqo-canon-v1", "locked": True})
    assert any("TSWS" in issue for issue in validate_intent(value))


def test_ids_are_stable_and_operation_ids_are_unique():
    value = intent(
        commandId="bad/path",
        operations=[
            {"id": "same", "type": "trim", "params": {}},
            {"id": "same", "type": "render-preview", "params": {}},
        ],
    )
    issues = validate_intent(value)
    assert any("commandId" in issue for issue in issues)
    assert "operation ids must be unique" in issues


def test_output_and_operation_shapes_fail_closed():
    value = intent(
        operations=[{"id": "trim", "type": "trim", "params": "not-an-object"}],
        output={"mode": "preview", "width": True, "height": 1080, "fps": 60, "container": "avi"},
    )
    issues = validate_intent(value)
    assert "every operation params value must be an object" in issues
    assert any("output.width" in issue for issue in issues)
    assert any("output.fps" in issue for issue in issues)
    assert any("output.container" in issue for issue in issues)


def test_public_execution_redacts_signed_media_urls():
    from app.api.v1.devon_editforge import _public_execution

    public = _public_execution(
        {
            "id": "cmd-1",
            "status": "dispatched",
            "command": {
                "commandId": "cmd-1",
                "projectId": "project-1",
                "cutId": "cut-1",
                "property": "tqo",
                "deliverable": "short-form",
                "source": {"uri": "https://source.example/file?secret=yes"},
                "operations": [{"id": "trim", "type": "trim", "params": {"start": 1}}],
                "output": {"mode": "preview", "uploadUrl": "https://upload.example/?secret=yes"},
            },
        }
    )
    encoded = str(public)
    assert "secret=yes" not in encoded
    assert public["command"]["operations"] == [{"id": "trim", "type": "trim"}]


def test_completed_receipt_requires_hashed_artifacts():
    issues = validate_receipt(
        {
            "schema": "editforge.edit-receipt.v1",
            "commandId": "cmd-1",
            "revisionId": "rev-1",
            "status": "completed",
            "artifacts": [{"uri": "https://media.example/out.mp4", "sha256": "bad"}],
        },
        command_id="cmd-1",
        revision_id="rev-1",
    )
    assert "artifact is missing a valid SHA-256 hash" in issues


@pytest.mark.asyncio
async def test_client_executes_with_bearer_auth_and_reads_receipt():
    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/edits":
            return httpx.Response(202, json={"execution": {"id": "cmd-20260826-001"}})
        return httpx.Response(
            200,
            json={
                "execution": {
                    "id": "cmd-20260826-001",
                    "receipt": {
                        "schema": "editforge.edit-receipt.v1",
                        "commandId": "cmd-20260826-001",
                        "revisionId": "rev-1",
                        "status": "completed",
                        "artifacts": [
                            {
                                "uri": "https://media.example/out.mp4",
                                "sha256": "b" * 64,
                            }
                        ],
                    },
                }
            },
        )

    client = EditForgeClient(
        EditForgeConfig("https://editforge.example", "secret"),
        transport=httpx.MockTransport(handler),
    )
    await client.execute(build_command(intent(), approval_id="REQ-1", approved_by="Tee"))
    result = await client.execution("cmd-20260826-001")
    assert result["execution"]["receipt"]["status"] == "completed"
    assert requests[0].headers["authorization"] == "Bearer secret"


@pytest.mark.asyncio
async def test_client_fails_closed_without_credentials():
    client = EditForgeClient(EditForgeConfig("", ""))
    with pytest.raises(EditForgeExecutionError, match="URL and token"):
        await client.execute({})
