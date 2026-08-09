"""Integration tests: conversations + Council message flow against Postgres."""


async def test_conversation_lifecycle(client, auth_headers):
    # Create
    created = await client.post(
        "/api/v1/conversations", json={"title": "Strategy session"}, headers=auth_headers
    )
    assert created.status_code == 201, created.text
    conversation = created.json()
    assert conversation["title"] == "Strategy session"
    assert conversation["status"] == "active"

    # List
    listed = await client.get("/api/v1/conversations", headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    # Rename + archive
    patched = await client.patch(
        f"/api/v1/conversations/{conversation['id']}",
        json={"title": "Renamed", "status": "archived"},
        headers=auth_headers,
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Renamed"
    assert patched.json()["status"] == "archived"


async def test_send_message_runs_the_council(client, auth_headers):
    created = await client.post(
        "/api/v1/conversations", json={}, headers=auth_headers
    )
    conversation_id = created.json()["id"]

    sent = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Should we launch the beta next month?"},
        headers=auth_headers,
    )
    assert sent.status_code == 200, sent.text
    body = sent.json()

    # Decision intent routes to the four decision agents.
    assert body["intent"] == "decision"
    assert body["agents_consulted"] == ["analyst", "strategist", "guardian", "skeptic"]
    assert len(body["contributions"]) == 4
    assert all(c["status"] == "completed" for c in body["contributions"])
    # Transparency: provider identity + synthesis metadata is exposed.
    assert body["provider"] == "mock"
    assert body["synthesis_mode"] in ("model", "fallback")
    assert body["assistant_message"]["metadata"]["agents_consulted"] == body[
        "agents_consulted"
    ]
    assert body["total_input_tokens"] > 0

    # Both messages persisted, conversation auto-titled from first message.
    detail = await client.get(
        f"/api/v1/conversations/{conversation_id}", headers=auth_headers
    )
    assert detail.status_code == 200
    data = detail.json()
    assert data["title"].startswith("Should we launch")
    roles = [m["role"] for m in data["messages"]]
    assert roles == ["user", "assistant"]

    # Agent runs recorded for the audit trail.
    runs = await client.get(
        f"/api/v1/conversations/{conversation_id}/runs", headers=auth_headers
    )
    assert runs.status_code == 200
    run_rows = runs.json()
    assert len(run_rows) == 4
    assert {r["agent_slug"] for r in run_rows} == {
        "analyst", "strategist", "guardian", "skeptic",
    }
    assert all(r["status"] == "completed" for r in run_rows)
    assert all(r["token_usage"]["total_tokens"] > 0 for r in run_rows)


async def test_full_council_flag_consults_all_nine(client, auth_headers):
    created = await client.post("/api/v1/conversations", json={}, headers=auth_headers)
    conversation_id = created.json()["id"]

    sent = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Give me the complete picture.", "full_council": True},
        headers=auth_headers,
    )
    assert sent.status_code == 200, sent.text
    assert len(sent.json()["contributions"]) == 9


async def test_explicit_agent_selection(client, auth_headers):
    created = await client.post("/api/v1/conversations", json={}, headers=auth_headers)
    conversation_id = created.json()["id"]

    sent = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Long-term view please.", "agents": ["oracle"]},
        headers=auth_headers,
    )
    assert sent.status_code == 200
    assert sent.json()["agents_consulted"] == ["oracle"]

    rejected = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "hi", "agents": ["not-a-real-agent"]},
        headers=auth_headers,
    )
    assert rejected.status_code == 422


async def test_conversation_ownership_is_enforced(client, auth_headers):
    created = await client.post("/api/v1/conversations", json={}, headers=auth_headers)
    conversation_id = created.json()["id"]

    # Second user cannot see or post into the first user's conversation.
    await client.post(
        "/api/v1/auth/register",
        json={"email": "intruder@example.com", "password": "password-123456"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "intruder@example.com", "password": "password-123456"},
    )
    intruder = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert (
        await client.get(f"/api/v1/conversations/{conversation_id}", headers=intruder)
    ).status_code == 404
    assert (
        await client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"content": "let me in"},
            headers=intruder,
        )
    ).status_code == 404


async def test_conversations_require_auth(client):
    assert (await client.get("/api/v1/conversations")).status_code == 401
    assert (await client.post("/api/v1/conversations", json={})).status_code == 401
