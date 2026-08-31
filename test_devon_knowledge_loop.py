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
    assert result["connectors"]["postgres"]["engine"] == "PostgreSQL"
    assert result["connectors"]["postgres"]["live"] is True
    assert result["artifact"]["body"]
    assert "Karrie" in result["artifact"]["body"]
    assert result["live"] is False

    found = await client.get(
        "/api/v1/soul/find?q=Karrie",
        headers=auth_headers,
    )
    assert found.status_code == 200, found.text
    hits = found.json()["ledger"]
    assert hits, found.json()
    assert any("Karrie" in (hit.get("text") or "") for hit in hits)
    assert any("Karrie" in (hit.get("body") or "") for hit in hits)
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


async def _propose_approve_commit(client, auth_headers, text, *, kind="lesson"):
    proposed = await client.post(
        "/api/v1/soul/propose",
        headers=auth_headers,
        json={"text": text, "kind": kind},
    )
    assert proposed.status_code == 201, proposed.text
    request_id = proposed.json()["approval"]["request_id"]
    token = proposed.json()["approval"]["token"]
    approved = await client.post(
        "/api/v1/soul/approve",
        headers=auth_headers,
        json={"request_id": request_id, "token": token, "decided_by": "Tee"},
    )
    assert approved.status_code == 200, approved.text
    committed = await client.post(
        "/api/v1/soul/commit",
        headers=auth_headers,
        json={"request_id": request_id},
    )
    assert committed.status_code == 200, committed.text
    return committed.json()


async def test_artifact_body_round_trips_on_find(client, auth_headers):
    payload = "ROUNDTRIP-BODY the pricing hold from Monday is still in force"
    committed = await _propose_approve_commit(client, auth_headers, payload)
    assert committed["artifact"]["body"] == payload
    assert committed["connectors"]["postgres"]["engine"] == "PostgreSQL"

    found = await client.get(
        "/api/v1/soul/find?q=ROUNDTRIP-BODY",
        headers=auth_headers,
    )
    assert found.status_code == 200, found.text
    hits = found.json()["ledger"]
    assert hits, found.json()
    assert hits[0]["body"] == payload
    assert hits[0]["text"] == payload
    assert hits[0]["store"] == "postgresql"


async def test_later_note_cannot_outrank_earlier_ruling(client, auth_headers):
    ruling = await _propose_approve_commit(
        client,
        auth_headers,
        "RANKTEST Tee ruled Karrie holds permanent veto",
        kind="ruling",
    )
    assert ruling["artifact"]["kind"] == "ruling"
    assert ruling["soul"]["written"] is False
    assert "Tee Soul" in ruling["soul"]["reason"] or "ruling" in ruling["soul"]["reason"].lower()

    note = await _propose_approve_commit(
        client,
        auth_headers,
        "RANKTEST later note about Karrie likes tea",
        kind="lesson",
    )
    assert note["artifact"]["kind"] == "lesson"

    found = await client.get(
        "/api/v1/soul/find?q=RANKTEST",
        headers=auth_headers,
    )
    assert found.status_code == 200, found.text
    hits = found.json()["ledger"]
    kinds = [hit["kind"] for hit in hits]
    assert kinds[0] == "ruling", hits
    assert "lesson" in kinds
    assert hits[0]["rank"] == "tee-ruling"
    assert "veto" in (hits[0]["body"] or "")
    # The later note exists but sits below the earlier ruling.
    note_hits = [hit for hit in hits if hit["kind"] != "ruling"]
    assert note_hits
    assert "tea" in (note_hits[0]["body"] or "")


def test_propose_docstring_does_not_claim_writes_nothing():
    loop = pathlib.Path("app/services/knowledge_loop.py").read_text(encoding="utf-8")
    api = pathlib.Path("app/api/v1/soul.py").read_text(encoding="utf-8")
    assert "Writes nothing" not in loop
    assert "Writes nothing" not in api
    assert "PostgreSQL" in loop
    assert "LEDGER_KINDS" in loop
