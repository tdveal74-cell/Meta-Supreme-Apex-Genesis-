"""In-estate knowledge loop: remember, approve, consume, commit, find.

The compiler in services.devon stays effect-free. Execution lives in
app.services.knowledge_loop and the soul HTTP write lane.
"""

from __future__ import annotations

import ast
import pathlib

from services.devon.assistant import Devon

NETWORK_FORBIDDEN = {
    "requests",
    "httpx",
    "urllib",
    "socket",
    "http",
    "subprocess",
    "ftplib",
    "smtplib",
    "telnetlib",
}


def test_the_executor_does_not_live_in_services_devon():
    devon = pathlib.Path("services/devon")
    names = {p.name for p in devon.glob("*.py")}
    assert "knowledge_loop.py" not in names
    assert pathlib.Path("app/services/knowledge_loop.py").is_file()


def test_services_devon_still_cannot_import_network_or_subprocess():
    for path in sorted(pathlib.Path("services/devon").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        for name in imported:
            assert name.split(".")[0] not in NETWORK_FORBIDDEN, path.name


def test_filing_plan_from_the_compiler_stays_unexecuted():
    response = Devon().ask("remember the pricing hold from Monday")
    assert response.plan is not None
    assert response.plan.to_dict()["executed"] is False
    assert response.executed is False


async def test_unapproved_soul_commit_is_refused(client, auth_headers):
    proposed = await client.post(
        "/api/v1/soul/propose",
        headers=auth_headers,
        json={"text": "remember the pricing hold from Monday"},
    )
    assert proposed.status_code == 201, proposed.text
    body = proposed.json()
    assert body["executed"] is False
    assert body["plan"]["executed"] is False
    request_id = body["approval"]["request_id"]

    committed = await client.post(
        "/api/v1/soul/commit",
        headers=auth_headers,
        json={"request_id": request_id},
    )
    assert committed.status_code == 403, committed.text
    assert "Unapproved" in committed.json()["detail"]


async def test_approved_consume_once_commit_writes_ledger_and_refuses_replay(
    client, auth_headers
):
    proposed = await client.post(
        "/api/v1/soul/propose",
        headers=auth_headers,
        json={"text": "remember Karrie holds permanent veto over her likeness"},
    )
    assert proposed.status_code == 201, proposed.text
    body = proposed.json()
    compiler_plan = body["plan"]
    assert compiler_plan["executed"] is False
    request_id = body["approval"]["request_id"]
    token = body["approval"]["token"]

    approved = await client.post(
        "/api/v1/soul/approve",
        headers=auth_headers,
        json={"request_id": request_id, "token": token, "decided_by": "Tee"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["approved"] is True
    assert approved.json()["executed"] is False

    committed = await client.post(
        "/api/v1/soul/commit",
        headers=auth_headers,
        json={"request_id": request_id},
    )
    assert committed.status_code == 200, committed.text
    result = committed.json()
    assert result["executed"] is True
    assert result["consumed"] is True
    assert result["plan"]["executed"] is False
    assert result["artifact"]["artifact_id"]
    assert result["receipt"]["receipt_id"]
    assert result["soul"]["written"] is False
    assert "unset" in result["soul"]["reason"].lower() or "off" in result["soul"]["reason"].lower()
    assert result["n8n"]["routed"] is False
    assert result["connectors"]["notion"]["written"] is False
    assert result["live"] is False

    found = await client.get(
        "/api/v1/soul/find?q=Karrie",
        headers=auth_headers,
    )
    assert found.status_code == 200, found.text
    hits = found.json()["ledger"]
    assert hits, found.json()
    assert any("Karrie" in (hit.get("text") or "") for hit in hits)
    assert found.json()["findable_without_vault_tools"] is True

    replay = await client.post(
        "/api/v1/soul/commit",
        headers=auth_headers,
        json={"request_id": request_id},
    )
    assert replay.status_code == 403, replay.text
    detail = replay.json()["detail"]
    assert "already spent" in detail.lower() or "consumed" in detail.lower()


async def test_emergency_stop_blocks_action_started(client, auth_headers):
    proposed = await client.post(
        "/api/v1/soul/propose",
        headers=auth_headers,
        json={"text": "remember stop the next filing"},
    )
    assert proposed.status_code == 201, proposed.text
    request_id = proposed.json()["approval"]["request_id"]
    token = proposed.json()["approval"]["token"]

    approved = await client.post(
        "/api/v1/soul/approve",
        headers=auth_headers,
        json={"request_id": request_id, "token": token},
    )
    assert approved.status_code == 200, approved.text

    stopped = await client.post(
        "/api/v1/ledger/emergency-stop",
        headers=auth_headers,
        json={"reason": "knowledge-loop stop test"},
    )
    assert stopped.status_code == 200, stopped.text

    committed = await client.post(
        "/api/v1/soul/commit",
        headers=auth_headers,
        json={"request_id": request_id},
    )
    assert committed.status_code == 403, committed.text
    assert "Emergency stop" in committed.json()["detail"]


async def test_tee_soul_layer_is_refused_at_propose(client, auth_headers):
    response = await client.post(
        "/api/v1/soul/propose",
        headers=auth_headers,
        json={"text": "remember a ruling", "layer": 1},
    )
    assert response.status_code == 403, response.text
    assert "Tee Soul" in response.json()["detail"]


async def test_soul_write_lane_requires_authentication(client):
    assert (await client.post("/api/v1/soul/propose", json={"text": "x"})).status_code == 401
    assert (
        await client.post(
            "/api/v1/soul/approve", json={"request_id": "REQ-1", "token": "x"}
        )
    ).status_code == 401
    assert (
        await client.post("/api/v1/soul/commit", json={"request_id": "REQ-1"})
    ).status_code == 401
    assert (await client.get("/api/v1/soul/find?q=x")).status_code == 401
