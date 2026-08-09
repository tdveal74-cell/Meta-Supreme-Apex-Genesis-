"""Memory tests — transparent, editable, deletable; recall into the Council."""


async def test_council_exchange_persists_transparent_memory(client, auth_headers):
    conversation = await client.post(
        "/api/v1/conversations", json={}, headers=auth_headers
    )
    sent = await client.post(
        f"/api/v1/conversations/{conversation.json()['id']}/messages",
        json={"content": "Should we expand into the European market?"},
        headers=auth_headers,
    )
    assert sent.status_code == 200

    memories = (await client.get("/api/v1/memory", headers=auth_headers)).json()
    assert len(memories) == 1
    memory = memories[0]
    assert memory["memory_type"] == "context"
    assert memory["metadata"]["origin"] == "council_interaction"
    assert "European market" in memory["content"]
    assert 1 <= memory["importance"] <= 10


async def test_memory_recall_feeds_future_interactions(client, auth_headers):
    conversation = await client.post(
        "/api/v1/conversations", json={}, headers=auth_headers
    )
    conversation_id = conversation.json()["id"]

    first = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Should we expand into the European market?"},
        headers=auth_headers,
    )
    assert first.json()["assistant_message"]["metadata"]["memories_recalled"] == 0

    # A related follow-up in a fresh conversation recalls the stored memory.
    second_conversation = await client.post(
        "/api/v1/conversations", json={}, headers=auth_headers
    )
    second = await client.post(
        f"/api/v1/conversations/{second_conversation.json()['id']}/messages",
        json={"content": "What did we consider about the European market expansion?"},
        headers=auth_headers,
    )
    assert second.json()["assistant_message"]["metadata"]["memories_recalled"] >= 1


async def test_memory_crud_is_user_controlled(client, auth_headers):
    created = await client.post(
        "/api/v1/memory",
        json={
            "content": "Prefers concise answers with explicit tradeoffs.",
            "memory_type": "preference",
            "importance": 8,
        },
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    memory = created.json()
    assert memory["metadata"]["origin"] == "user"

    # Editable
    updated = await client.patch(
        f"/api/v1/memory/{memory['id']}",
        json={"content": "Prefers concise answers.", "importance": 9, "is_active": False},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["content"] == "Prefers concise answers."
    assert updated.json()["importance"] == 9
    assert updated.json()["is_active"] is False

    # Deletable — gone means gone.
    deleted = await client.delete(
        f"/api/v1/memory/{memory['id']}", headers=auth_headers
    )
    assert deleted.status_code == 204
    assert (await client.get("/api/v1/memory", headers=auth_headers)).json() == []


async def test_memory_ownership_enforced(client, auth_headers):
    created = await client.post(
        "/api/v1/memory",
        json={"content": "Private context.", "memory_type": "context"},
        headers=auth_headers,
    )
    memory_id = created.json()["id"]

    await client.post(
        "/api/v1/auth/register",
        json={"email": "other-m@example.com", "password": "password-123456"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "other-m@example.com", "password": "password-123456"},
    )
    other = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert (await client.get("/api/v1/memory", headers=other)).json() == []
    assert (
        await client.delete(f"/api/v1/memory/{memory_id}", headers=other)
    ).status_code == 404
