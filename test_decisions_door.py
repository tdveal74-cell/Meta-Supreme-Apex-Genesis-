"""
The three facts about /decisions that the web decision record is built on.

apps/web/components/council/decision-record.ts encodes each of these as a rule,
and scripts/decisions-check.ts proves the web side holds to them. Nothing proved
the API side actually behaves this way, so the rules were read off the source
rather than measured. These measure them.

Each one is a real trap rather than a restatement of the route:

  1. update_decision advances an open decision to "decided" by itself whenever
     chosen_option arrives with no status. Choice D on the deliberate page asks
     the Council to look again, which is the opposite of a final call, so the web
     side sends status explicitly on every ruling. If the route ever stopped
     honouring an explicit "open", that ruling would silently close a decision
     nobody made.
  2. question is capped at 2000 characters. The web side REFUSES an over-length
     question rather than trimming it, because a trimmed question is a different
     question stored under the human's name. That refusal is only worth having
     while the cap is real.
  3. outcome_notes is capped at 20000, and the same refusal applies to it.
"""


async def test_explicit_open_status_survives_a_chosen_option(client, auth_headers):
    """A recorded call that is deliberately not final must stay open."""
    created = await client.post(
        "/api/v1/decisions",
        json={"question": "Should we ship the pilot?", "options": ["ship", "wait"]},
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    decision_id = created.json()["id"]
    assert created.json()["status"] == "open"

    ruled = await client.patch(
        f"/api/v1/decisions/{decision_id}",
        json={
            "chosen_option": "D. Request another round on a specific point",
            "status": "open",
            "outcome_notes": "Look again at the cost line.",
        },
        headers=auth_headers,
    )
    assert ruled.status_code == 200, ruled.text
    body = ruled.json()
    assert body["chosen_option"] == "D. Request another round on a specific point"
    assert body["outcome_notes"] == "Look again at the cost line."
    assert body["status"] == "open", (
        "an explicitly open ruling was advanced to decided anyway, so asking the "
        "Council for another round would close a decision nobody made"
    )


async def test_an_omitted_status_is_what_advances_the_decision(client, auth_headers):
    """The other half of the trap: omitting status is not neutral."""
    created = await client.post(
        "/api/v1/decisions",
        json={"question": "Which region?", "options": ["us-east", "eu-west"]},
        headers=auth_headers,
    )
    decision_id = created.json()["id"]

    ruled = await client.patch(
        f"/api/v1/decisions/{decision_id}",
        json={"chosen_option": "us-east"},
        headers=auth_headers,
    )
    assert ruled.status_code == 200, ruled.text
    assert ruled.json()["status"] == "decided", (
        "the route no longer advances on an omitted status. That is a fine "
        "change, and it means the web side's reason for always sending the key "
        "has changed with it, so update the note in decision-record.ts"
    )


async def test_an_over_length_question_is_refused_by_the_route(client, auth_headers):
    """The cap the web side refuses against is real."""
    at_cap = await client.post(
        "/api/v1/decisions",
        json={"question": "q" * 2000},
        headers=auth_headers,
    )
    assert at_cap.status_code == 201, at_cap.text

    over_cap = await client.post(
        "/api/v1/decisions",
        json={"question": "q" * 2001},
        headers=auth_headers,
    )
    assert over_cap.status_code == 422, (
        "a 2001 character question was accepted, so QUESTION_MAX in "
        "decision-record.ts is refusing against a cap that no longer exists"
    )


async def test_an_over_length_note_is_refused_by_the_route(client, auth_headers):
    """Same, for the free text field a human writes their reasoning into."""
    created = await client.post(
        "/api/v1/decisions",
        json={"question": "Which vendor?"},
        headers=auth_headers,
    )
    decision_id = created.json()["id"]

    at_cap = await client.patch(
        f"/api/v1/decisions/{decision_id}",
        json={"chosen_option": "a", "status": "decided", "outcome_notes": "n" * 20_000},
        headers=auth_headers,
    )
    assert at_cap.status_code == 200, at_cap.text

    over_cap = await client.patch(
        f"/api/v1/decisions/{decision_id}",
        json={"chosen_option": "a", "status": "decided", "outcome_notes": "n" * 20_001},
        headers=auth_headers,
    )
    assert over_cap.status_code == 422, (
        "a 20001 character note was accepted, so LONG_TEXT_MAX in "
        "decision-record.ts is refusing against a cap that no longer exists"
    )
