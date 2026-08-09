"""Decision tracking tests — the Council recommends, the human decides."""


async def test_manual_decision_lifecycle(client, auth_headers):
    created = await client.post(
        "/api/v1/decisions",
        json={
            "question": "Which cloud provider should we standardize on?",
            "options": ["AWS", "GCP", "Azure"],
            "recommendation": "GCP for the ML tooling, per the platform team's analysis.",
        },
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    decision = created.json()
    assert decision["status"] == "open"
    assert decision["options"] == ["AWS", "GCP", "Azure"]
    assert decision["chosen_option"] is None  # nothing decided yet

    # The human records the final call — status advances to decided.
    decided = await client.patch(
        f"/api/v1/decisions/{decision['id']}",
        json={"chosen_option": "GCP"},
        headers=auth_headers,
    )
    assert decided.status_code == 200
    assert decided.json()["chosen_option"] == "GCP"
    assert decided.json()["status"] == "decided"

    # Later: outcome review.
    reviewed = await client.patch(
        f"/api/v1/decisions/{decision['id']}",
        json={
            "status": "reviewed",
            "outcome": "Migration completed in Q3.",
            "outcome_notes": "Costs 12% under forecast.",
        },
        headers=auth_headers,
    )
    assert reviewed.json()["status"] == "reviewed"
    assert reviewed.json()["outcome"] == "Migration completed in Q3."


async def test_decision_from_council_exchange(client, auth_headers):
    conversation = await client.post(
        "/api/v1/conversations", json={}, headers=auth_headers
    )
    sent = await client.post(
        f"/api/v1/conversations/{conversation.json()['id']}/messages",
        json={"content": "Should we launch the beta next month?"},
        headers=auth_headers,
    )
    assert sent.status_code == 200
    body = sent.json()
    assistant_id = body["assistant_message"]["id"]

    created = await client.post(
        "/api/v1/decisions/from-message",
        json={"message_id": assistant_id},
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    decision = created.json()
    # Question is the triggering user message; recommendation is the synthesis.
    assert decision["question"] == "Should we launch the beta next month?"
    assert decision["recommendation"] == body["assistant_message"]["content"]
    assert decision["options"] == body["recommended_actions"]
    assert decision["status"] == "open"  # the human has not decided yet
    assert decision["metadata"]["origin"] == "council"
    assert decision["metadata"]["agents_consulted"] == body["agents_consulted"]

    listed = await client.get("/api/v1/decisions", headers=auth_headers)
    assert len(listed.json()) == 1


async def test_decision_from_message_rejects_foreign_and_user_messages(
    client, auth_headers
):
    conversation = await client.post(
        "/api/v1/conversations", json={}, headers=auth_headers
    )
    sent = await client.post(
        f"/api/v1/conversations/{conversation.json()['id']}/messages",
        json={"content": "Plan the rollout."},
        headers=auth_headers,
    )
    user_message_id = sent.json()["user_message"]["id"]
    assistant_id = sent.json()["assistant_message"]["id"]

    # User messages cannot be tracked as decisions.
    rejected = await client.post(
        "/api/v1/decisions/from-message",
        json={"message_id": user_message_id},
        headers=auth_headers,
    )
    assert rejected.status_code == 404

    # Another user cannot track a decision from someone else's exchange.
    await client.post(
        "/api/v1/auth/register",
        json={"email": "other-d@example.com", "password": "password-123456"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "other-d@example.com", "password": "password-123456"},
    )
    other = {"Authorization": f"Bearer {login.json()['access_token']}"}
    foreign = await client.post(
        "/api/v1/decisions/from-message",
        json={"message_id": assistant_id},
        headers=other,
    )
    assert foreign.status_code == 404
