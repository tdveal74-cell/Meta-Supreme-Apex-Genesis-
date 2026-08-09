"""Integration tests: one-shot intelligence endpoints."""


async def test_status_reports_provider_transparently(client, auth_headers):
    response = await client.get("/api/v1/intelligence/status", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "mock"
    assert body["simulated"] is True  # transparent by default
    assert body["agents_available"] == 9


async def test_ask_runs_one_shot_council(client, auth_headers):
    response = await client.post(
        "/api/v1/intelligence/ask",
        json={"message": "Explain the tradeoffs of a monorepo."},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["response"]
    assert body["intent"] == "analysis"
    assert body["agents_consulted"] == ["analyst", "librarian", "skeptic"]
    assert all(c["status"] == "completed" for c in body["contributions"])

    # One-shot means nothing persisted: no conversations were created.
    conversations = await client.get("/api/v1/conversations", headers=auth_headers)
    assert conversations.json() == []


async def test_ask_requires_auth(client):
    response = await client.post(
        "/api/v1/intelligence/ask", json={"message": "hi"}
    )
    assert response.status_code == 401
