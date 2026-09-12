"""In-estate knowledge loop: remember, approve, consume, commit, find.

The compiler in services.devon stays effect-free. Execution lives in
app.services.knowledge_loop and the soul HTTP write lane.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from services.devon.assistant import Devon

#: The approver's second credential. The JWT proposes; this key approves.
RULING_KEY = "test-ruling-key-not-a-jwt"


@pytest.fixture(autouse=True)
def _ruling_key_env(monkeypatch):
    monkeypatch.setenv("DEVON_RULING_KEY", RULING_KEY)


def _ruled(auth_headers):
    return {**auth_headers, "X-Devon-Ruling-Key": RULING_KEY}

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
        headers=_ruled(auth_headers),
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
        headers=_ruled(auth_headers),
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
        headers=_ruled(auth_headers),
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


def test_postgres_live_is_not_inferred_from_env_alone(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/db")
    from app.services import knowledge_loop as loop_mod
    raw = loop_mod._connector_honesty()
    assert raw["postgres"]["configured"] is True
    assert raw["postgres"]["live"] is False
    assert raw["postgres"]["written"] is False
    proven = loop_mod._connector_honesty(postgres_proven=True)
    assert proven["postgres"]["live"] is True
    assert proven["postgres"]["written"] is True


async def test_platform_console_serves_the_wired_loop_hud(client):
    response = await client.get("/console")
    assert response.status_code == 200, response.text
    html = response.text
    assert "Loop.propose" in html
    assert "rememberThroughLoop" in html
    assert "/api/v1/soul/propose" in html
    assert "devon.platform.jwt" in html
    assert "add_task" in html
    assert "KIND_FOR" in html


async def test_task_files_to_the_ledger_not_notion(client, auth_headers):
    committed = await _propose_approve_commit(
        client,
        auth_headers,
        "add a task to verify the D10 grid hash",
        kind="task",
    )
    assert committed["artifact"]["kind"] == "task"
    assert committed["connectors"]["notion"]["written"] is False
    assert committed["connectors"]["notion"]["live"] is False
    assert committed["soul"]["written"] is False
    assert committed["connectors"]["postgres"]["live"] is True

    found = await client.get(
        "/api/v1/soul/find?q=D10&kind=task",
        headers=auth_headers,
    )
    assert found.status_code == 200, found.text
    hits = found.json()["ledger"]
    assert hits, found.json()
    assert hits[0]["kind"] == "task"
    assert hits[0]["rank"] == "operator-file"
    assert "D10" in (hits[0]["body"] or "")


async def test_the_jwt_alone_cannot_approve(client, auth_headers):
    """The gate the loop exists for: propose hands the token back, so the
    token plus the same JWT must not be enough to approve. The ruling key is
    the second credential, and a refusal for a missing or wrong key must
    leave the single-use decision unspent."""
    proposed = await client.post(
        "/api/v1/soul/propose",
        headers=auth_headers,
        json={"text": "remember the gate needs two credentials"},
    )
    assert proposed.status_code == 201, proposed.text
    request_id = proposed.json()["approval"]["request_id"]
    token = proposed.json()["approval"]["token"]

    bare = await client.post(
        "/api/v1/soul/approve",
        headers=auth_headers,
        json={"request_id": request_id, "token": token},
    )
    assert bare.status_code == 403, bare.text
    assert "ruling key" in bare.json()["detail"].lower()

    wrong = await client.post(
        "/api/v1/soul/approve",
        headers={**auth_headers, "X-Devon-Ruling-Key": "not-the-key"},
        json={"request_id": request_id, "token": token},
    )
    assert wrong.status_code == 403, wrong.text

    # Both refusals happened before the decision was spent: the right key
    # still approves the very same request.
    ruled = await client.post(
        "/api/v1/soul/approve",
        headers=_ruled(auth_headers),
        json={"request_id": request_id, "token": token},
    )
    assert ruled.status_code == 200, ruled.text
    assert ruled.json()["approved"] is True


async def test_approve_lane_fails_closed_when_no_ruling_key_is_configured(
    client, auth_headers, monkeypatch
):
    monkeypatch.delenv("DEVON_RULING_KEY", raising=False)
    proposed = await client.post(
        "/api/v1/soul/propose",
        headers=auth_headers,
        json={"text": "remember the lane is propose-only without the key"},
    )
    assert proposed.status_code == 201, proposed.text
    body = proposed.json()["approval"]
    refused = await client.post(
        "/api/v1/soul/approve",
        headers=_ruled(auth_headers),
        json={"request_id": body["request_id"], "token": body["token"]},
    )
    assert refused.status_code == 403, refused.text
    assert "propose-only" in refused.json()["detail"]


async def test_a_second_approve_repairs_rather_than_wedges(client, auth_headers):
    """A commit that dies after a successful approve used to wedge: retrying
    hit 'already approved' forever. Approve is idempotent with a valid token
    now, so the HUD's retry path is approve again, then commit."""
    proposed = await client.post(
        "/api/v1/soul/propose",
        headers=auth_headers,
        json={"text": "remember the retry path must not wedge"},
    )
    assert proposed.status_code == 201, proposed.text
    request_id = proposed.json()["approval"]["request_id"]
    token = proposed.json()["approval"]["token"]

    first = await client.post(
        "/api/v1/soul/approve",
        headers=_ruled(auth_headers),
        json={"request_id": request_id, "token": token},
    )
    assert first.status_code == 200, first.text
    assert first.json()["already_approved"] is False

    second = await client.post(
        "/api/v1/soul/approve",
        headers=_ruled(auth_headers),
        json={"request_id": request_id, "token": token},
    )
    assert second.status_code == 200, second.text
    assert second.json()["already_approved"] is True

    # A wrong token still refuses on the already-approved path.
    forged = await client.post(
        "/api/v1/soul/approve",
        headers=_ruled(auth_headers),
        json={"request_id": request_id, "token": "forged-token"},
    )
    assert forged.status_code == 403, forged.text

    committed = await client.post(
        "/api/v1/soul/commit",
        headers=auth_headers,
        json={"request_id": request_id},
    )
    assert committed.status_code == 200, committed.text
    assert committed.json()["executed"] is True


async def test_find_treats_ilike_metacharacters_as_literals(client, auth_headers):
    await _propose_approve_commit(
        client, auth_headers, "ESCTEST one hundred percent of the plan holds"
    )
    # A bare % used to be an all-wildcards pattern that matched everything.
    wildcard = await client.get(
        "/api/v1/soul/find", params={"q": "%"}, headers=auth_headers
    )
    assert wildcard.status_code == 200, wildcard.text
    assert wildcard.json()["ledger"] == []

    await _propose_approve_commit(
        client, auth_headers, "ESCPCT Karrie holds 100% veto over her likeness"
    )
    literal = await client.get(
        "/api/v1/soul/find", params={"q": "100% veto"}, headers=auth_headers
    )
    assert literal.status_code == 200, literal.text
    hits = literal.json()["ledger"]
    assert hits, literal.json()
    assert "100% veto" in (hits[0]["body"] or "")


async def test_multi_artifact_intents_do_not_crowd_out_matches(
    client, auth_headers, db_session
):
    """The result window is limit DISTINCT intents. An intent carrying many
    artifacts used to eat the whole raw-join window and silently drop other
    matching captures."""
    from sqlalchemy import select

    from app.models.live_state_ledger import IntentRecord
    from app.services.live_state_ledger import ledger

    first = await _propose_approve_commit(client, auth_headers, "CROWDTEST alpha capture")
    second = await _propose_approve_commit(client, auth_headers, "CROWDTEST beta capture")

    row = await db_session.execute(
        select(IntentRecord).where(IntentRecord.id == first["intent_id"])
    )
    owner_id = row.scalars().one().owner_id
    for n in range(45):
        await ledger.record_artifact(
            db_session,
            owner_id=owner_id,
            intent_id=first["intent_id"],
            path=f"estate://ledger/captures/test/crowd-{n}",
            body="CROWDTEST alpha capture",
            kind="lesson",
        )

    hits = await ledger.search_receipted_captures(
        db_session, owner_id=owner_id, query="CROWDTEST", limit=2
    )
    found_intents = {hit["intent_id"] for hit in hits}
    assert found_intents == {first["intent_id"], second["intent_id"]}, hits


def test_services_memory_points_at_receipted_artifacts_not_localstorage():
    from services import memory
    assert memory.STORE == "postgresql"
    assert "devon.learning.v1" in memory.NOT_MEMORY_KEYS
    pointed = memory.from_receipted_artifacts(
        [{"kind": "task", "body": "verify hash", "text": "verify hash"}]
    )
    assert pointed[0]["store"] == "postgresql"
    assert pointed[0]["localStorage"] is False
    assert pointed[0]["rank"] == "operator-file"
    assert memory.rank_kind("ruling") < memory.rank_kind("task") < memory.rank_kind("lesson")
