"""Fix PR 4 from the DEVON and Hermes audit, H2: the EditForge HTTP lane.

Execute never spent its approval, so one human ruling rendered N times and
spent provider credit N times; requested_by was never compared to the
caller, so a second account could execute with the first account's approval;
retry and cancel proxied straight to EditForge behind any JWT. Now execute
spends the approval before the command leaves, only the account that raised
the approval can use it, and retry and cancel are gated on the spent approval
that ran the command.
"""

from __future__ import annotations

import pytest

from app.api.v1 import devon_editforge
from app.api.v1.devon import _queue
from services.devon.approval import ApprovalState

HASH = "a" * 64


def draft(command_id: str = "cmd-20260902-001") -> dict:
    return {
        "command_id": command_id,
        "project_id": "project-tqo-001",
        "cut_id": "cut-tqo-001",
        "property": "tqo",
        "deliverable": "long-form",
        "source": {"uri": "https://media.example/source.mp4", "sha256": HASH},
        "identity": {
            "clone_id": "tee-clone-v1",
            "voice_id": "tee-voice-v1",
            "version": "tee-identity-v1",
            "consent_recorded": True,
        },
        "canon": {"version": "tqo-canon-v1", "locked": True},
        "operations": [
            {"id": "motion", "type": "generate-full-motion", "params": {"maxCredits": 30}},
            {"id": "preview", "type": "render-preview", "params": {}},
        ],
        "output": {"mode": "preview", "width": 1920, "height": 1080, "fps": 24, "container": "mp4"},
    }


class FakeEditForge:
    """Counts what would have been sent to the studio."""

    def __init__(self) -> None:
        self.executed: list = []
        self.actions: list = []

    async def execute(self, command):
        self.executed.append(command)
        return {"execution": {"commandId": command["commandId"], "status": "queued"}}

    async def action(self, command_id, action):
        self.actions.append((command_id, action))
        return {"ok": True, "commandId": command_id, "action": action}


@pytest.fixture
def studio(monkeypatch):
    fake = FakeEditForge()
    monkeypatch.setattr(devon_editforge, "_client", lambda: fake)
    return fake


async def _approved(client, auth_headers, body: dict) -> str:
    raised = await client.post("/api/v1/devon/editforge/authorize", headers=auth_headers, json=body)
    assert raised.status_code == 200, raised.text
    request_id = raised.json()["request_id"]
    ruled = await client.post(
        "/api/v1/devon/approvals/decide",
        headers=auth_headers,
        json={"request_id": request_id, "token": raised.json()["approval_token"], "decision": "approve"},
    )
    assert ruled.status_code == 200, ruled.text
    assert ruled.json()["approved"] is True
    return request_id


async def _second_account(client) -> dict:
    email, password = "second-editor@example.com", "another-strong-password-123"
    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Second Editor"},
    )
    assert registered.status_code == 201, registered.text
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def test_one_approval_executes_once(client, auth_headers, studio):
    body = draft()
    request_id = await _approved(client, auth_headers, body)

    first = await client.post(
        "/api/v1/devon/editforge/execute",
        headers=auth_headers,
        json={"approval_id": request_id, "draft": body},
    )
    assert first.status_code == 200, first.text
    assert first.json()["approval_id"] == request_id
    assert _queue.get(request_id).state is ApprovalState.CONSUMED

    again = await client.post(
        "/api/v1/devon/editforge/execute",
        headers=auth_headers,
        json={"approval_id": request_id, "draft": body},
    )
    assert again.status_code == 409, again.text
    assert "consumed" in again.json()["detail"]
    assert len(studio.executed) == 1, "the studio saw the command once"


async def test_another_account_cannot_execute_with_someone_elses_approval(
    client, auth_headers, studio
):
    body = draft("cmd-20260902-002")
    request_id = await _approved(client, auth_headers, body)
    other = await _second_account(client)

    stolen = await client.post(
        "/api/v1/devon/editforge/execute",
        headers=other,
        json={"approval_id": request_id, "draft": body},
    )
    assert stolen.status_code == 404, stolen.text
    unknown = await client.post(
        "/api/v1/devon/editforge/execute",
        headers=other,
        json={"approval_id": "REQ-DOESNOTEXIST", "draft": body},
    )
    assert unknown.status_code == 404, unknown.text
    assert stolen.json()["detail"] == unknown.json()["detail"]
    assert _queue.get(request_id).state is ApprovalState.APPROVED, "the refusal spent nothing"
    assert studio.executed == []

    owner = await client.post(
        "/api/v1/devon/editforge/execute",
        headers=auth_headers,
        json={"approval_id": request_id, "draft": body},
    )
    assert owner.status_code == 200, owner.text


async def test_retry_and_cancel_are_gated_on_the_spent_approval(client, auth_headers, studio):
    body = draft("cmd-20260902-003")
    request_id = await _approved(client, auth_headers, body)
    control = f"/api/v1/devon/editforge/executions/{body['command_id']}"

    bare = await client.post(f"{control}/retry", headers=auth_headers)
    assert bare.status_code == 422, bare.text

    early = await client.post(
        f"{control}/cancel", headers=auth_headers, json={"approval_id": request_id}
    )
    assert early.status_code == 409, early.text
    assert "executed" in early.json()["detail"]

    executed = await client.post(
        "/api/v1/devon/editforge/execute",
        headers=auth_headers,
        json={"approval_id": request_id, "draft": body},
    )
    assert executed.status_code == 200, executed.text

    wrong_command = await client.post(
        "/api/v1/devon/editforge/executions/cmd-someone-else/retry",
        headers=auth_headers,
        json={"approval_id": request_id},
    )
    assert wrong_command.status_code == 409, wrong_command.text
    assert "does not name this command" in wrong_command.json()["detail"]

    other = await _second_account(client)
    theirs = await client.post(
        f"{control}/cancel", headers=other, json={"approval_id": request_id}
    )
    assert theirs.status_code == 404, theirs.text

    retried = await client.post(
        f"{control}/retry", headers=auth_headers, json={"approval_id": request_id}
    )
    assert retried.status_code == 200, retried.text
    cancelled = await client.post(
        f"{control}/cancel", headers=auth_headers, json={"approval_id": request_id}
    )
    assert cancelled.status_code == 200, cancelled.text
    assert studio.actions == [(body["command_id"], "retry"), (body["command_id"], "cancel")]
