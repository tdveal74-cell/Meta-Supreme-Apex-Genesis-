"""The hearing door: machine authenticated, read only, structurally inert.

`POST /api/v1/devon/hear` is how the devon-hears lane asks what DEVON
understood in a transcript. It exists because the lane has no account behind
it and an account token expires in 24 hours, so a workflow holding one breaks
by the next morning.

Two properties are worth more than the rest of this file, and each has a test
whose failure would be a real incident rather than a style complaint:

1. **An unset key closes the door, it does not open it.** The settings default
   is `""`. A caller sending no header presents `""`. A naive equality check
   matches those and authenticates a stranger, and the deployment reads as
   configured the whole time. `test_an_unset_key_refuses_an_empty_header` is
   that exact bug written down.

2. **The door cannot act.** It calls `parse`, a pure function in an effect free
   package, and never `Devon.ask`, which gates an intent and raises an approval
   card. That is checked two ways here: the gate is replaced with something
   that explodes and the door still answers, and the function's own AST is read
   for a call it must never contain. The second one survives a refactor that
   the first would not notice.
"""

import ast
import inspect

import pytest

from app.api.v1.devon import hear
from app.core.config import settings
from app.security.service_key import (
    MINIMUM_KEY_LENGTH,
    SERVICE_KEY_HEADER,
    SERVICE_PRINCIPAL,
)

HEAR = "/api/v1/devon/hear"

#: A key that is not a real one anywhere. The repository is public.
TEST_KEY = "test-service-key-not-a-real-one"


@pytest.fixture
def keyed(monkeypatch):
    """Configure the service key for the duration of one test."""
    monkeypatch.setattr(settings, "DEVON_SERVICE_KEY", TEST_KEY, raising=False)
    return {SERVICE_KEY_HEADER: TEST_KEY}


@pytest.fixture
def unset(monkeypatch):
    """The state a deployment lands in when nobody sets the variable."""
    monkeypatch.setattr(settings, "DEVON_SERVICE_KEY", "", raising=False)


# ---------------------------------------------------------------------------
# The door is closed until a key is set


@pytest.mark.asyncio
async def test_an_unset_key_refuses_an_empty_header(client, unset):
    """The load bearing test. Nothing compared against nothing is not a match.

    A service that forgot DEVON_SERVICE_KEY must serve nobody. If this ever
    returns 200 the door is open to the whole internet while every dashboard
    still reads green, which is the failure mode the estate's first law is
    written about.
    """
    answered = await client.post(
        HEAR, json={"text": "what time is it"}, headers={SERVICE_KEY_HEADER: ""}
    )
    assert answered.status_code == 503, answered.text
    assert "DEVON_SERVICE_KEY" in answered.json()["detail"]


@pytest.mark.asyncio
async def test_an_unset_key_refuses_a_plausible_key(client, unset):
    answered = await client.post(
        HEAR,
        json={"text": "what time is it"},
        headers={SERVICE_KEY_HEADER: "looks-like-a-key"},
    )
    assert answered.status_code == 503, answered.text


@pytest.mark.asyncio
async def test_an_unset_key_refuses_no_header_at_all(client, unset):
    answered = await client.post(HEAR, json={"text": "what time is it"})
    assert answered.status_code == 503, answered.text


@pytest.mark.asyncio
async def test_a_short_key_is_refused_even_when_the_caller_has_it(client, monkeypatch):
    """A guessable key is a misconfigured service, not a guarded door.

    The caller here presents the configured key exactly and still gets nothing.
    Without this floor a one character key authenticates and the deployment
    reads as configured, which is the unset bug wearing a different hat.
    """
    short = "x" * (MINIMUM_KEY_LENGTH - 1)
    monkeypatch.setattr(settings, "DEVON_SERVICE_KEY", short, raising=False)
    answered = await client.post(
        HEAR, json={"text": "what time is it"}, headers={SERVICE_KEY_HEADER: short}
    )
    assert answered.status_code == 503, answered.text
    assert str(MINIMUM_KEY_LENGTH) in answered.json()["detail"]


@pytest.mark.asyncio
async def test_a_key_exactly_at_the_floor_is_accepted(client, monkeypatch):
    """The boundary is inclusive, so the floor is a floor and not a fence."""
    exact = "k" * MINIMUM_KEY_LENGTH
    monkeypatch.setattr(settings, "DEVON_SERVICE_KEY", exact, raising=False)
    answered = await client.post(
        HEAR, json={"text": "what time is it"}, headers={SERVICE_KEY_HEADER: exact}
    )
    assert answered.status_code == 200, answered.text


def test_the_floor_is_at_least_128_bits_of_a_random_key():
    """24 URL safe characters is about 143 bits. Below this is thin for a key
    that never rotates and sits in front of a parse door."""
    assert MINIMUM_KEY_LENGTH >= 22


# ---------------------------------------------------------------------------
# With a key set, only the key gets in


@pytest.mark.asyncio
async def test_a_missing_header_refuses(client, keyed):
    answered = await client.post(HEAR, json={"text": "what time is it"})
    assert answered.status_code == 401, answered.text


@pytest.mark.asyncio
async def test_a_wrong_key_refuses(client, keyed):
    answered = await client.post(
        HEAR,
        json={"text": "what time is it"},
        headers={SERVICE_KEY_HEADER: "not-the-key"},
    )
    assert answered.status_code == 401, answered.text


@pytest.mark.asyncio
async def test_the_comparison_is_exact_rather_than_loose(client, keyed):
    """Case and truncation are both refused; compare_digest is not a prefix."""
    for wrong in (TEST_KEY.upper(), TEST_KEY[:-1], TEST_KEY + "x"):
        answered = await client.post(
            HEAR, json={"text": "what time is it"}, headers={SERVICE_KEY_HEADER: wrong}
        )
        assert answered.status_code == 401, f"{wrong!r} got in: {answered.text}"


@pytest.mark.asyncio
async def test_a_refusal_never_echoes_the_configured_key(client, keyed):
    answered = await client.post(
        HEAR, json={"text": "what time is it"}, headers={SERVICE_KEY_HEADER: "wrong"}
    )
    assert TEST_KEY not in answered.text


# ---------------------------------------------------------------------------
# What it answers


@pytest.mark.asyncio
async def test_a_query_comes_back_understood(client, keyed):
    answered = await client.post(HEAR, json={"text": "what time is it"}, headers=keyed)
    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["understood"] is True
    assert body["intent"] == "get_time"
    assert body["kind"] == "read"
    assert body["refused"] is False
    assert body["principal"] == SERVICE_PRINCIPAL


@pytest.mark.asyncio
async def test_a_capture_carries_its_payload(client, keyed):
    answered = await client.post(
        HEAR,
        json={"text": "Devon, remember the render farm bills on the 3rd"},
        headers=keyed,
    )
    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["intent"] == "capture"
    assert body["kind"] == "capture"
    assert "render farm" in body["payload"]
    assert body["refused"] is False


@pytest.mark.asyncio
async def test_an_effect_is_refused_rather_than_gated(client, keyed):
    """Voice cannot run effects. Ruled by Tee 2026-09-16 on an inline card."""
    answered = await client.post(
        HEAR, json={"text": "Devon, shut down the computer"}, headers=keyed
    )
    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["refused"] is True
    assert body["understood"] is False
    assert body["intent"] is None
    assert body["kind"] == "effect"
    assert "never acts" in body["reason"]


@pytest.mark.asyncio
async def test_a_refused_effect_carries_no_payload(client, keyed):
    """A lane that ignores `refused` still gets nothing it could act on."""
    answered = await client.post(
        HEAR,
        json={"text": "Devon, send a message to Marcus saying the cut is locked"},
        headers=keyed,
    )
    body = answered.json()
    assert body["refused"] is True
    assert body["payload"] == ""


@pytest.mark.asyncio
async def test_transcript_confidence_is_carried_straight_back(client, keyed):
    answered = await client.post(
        HEAR,
        json={"text": "what time is it", "source": "devon-hears", "transcript_confidence": 0.62},
        headers=keyed,
    )
    body = answered.json()
    assert body["transcript_confidence"] == pytest.approx(0.62)
    assert body["source"] == "devon-hears"


@pytest.mark.asyncio
async def test_a_confidence_outside_zero_to_one_is_refused(client, keyed):
    answered = await client.post(
        HEAR,
        json={"text": "what time is it", "transcript_confidence": 1.4},
        headers=keyed,
    )
    assert answered.status_code == 422, answered.text


@pytest.mark.asyncio
async def test_a_declined_parse_still_answers(client, keyed):
    """Declining is a legitimate outcome, not an error the lane must handle."""
    answered = await client.post(
        HEAR, json={"text": "mmm the thing about the thing"}, headers=keyed
    )
    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["understood"] is False
    assert body["refused"] is False


# ---------------------------------------------------------------------------
# It cannot act, proven twice


@pytest.mark.asyncio
async def test_the_door_answers_with_the_gate_broken(client, keyed, monkeypatch):
    """Replace the thing that raises approval cards with a landmine.

    If the door ever reaches `Devon.ask` this turns red. A behavioural proof
    that no branch here touches the approval rail.
    """
    import app.api.v1.devon as devon_api

    def landmine(*args, **kwargs):  # pragma: no cover - the point is not calling it
        raise AssertionError("the hearing door reached the approval gate")

    monkeypatch.setattr(devon_api._devon, "ask", landmine)

    for utterance in (
        "what time is it",
        "Devon, shut down the computer",
        "Devon, remember the render farm bills on the 3rd",
    ):
        answered = await client.post(HEAR, json={"text": utterance}, headers=keyed)
        assert answered.status_code == 200, answered.text


def test_the_door_never_names_the_gate_in_its_own_source():
    """The structural half, which survives a refactor the landmine would miss.

    A future edit could reach the queue through a helper rather than through
    `_devon.ask`, and the landmine above would stay green. This reads the
    function's AST instead: it must call `parse` and must name no attribute
    that routes, gates, approves or asks.
    """
    tree = ast.parse(inspect.getsource(hear))
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    named = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "parse" in named, "the door stopped calling the parser"

    forbidden = {"ask", "gate", "_gate", "raise_request", "approve", "decide", "commit"}
    trespass = forbidden & (called | named)
    assert not trespass, (
        f"the hearing door now calls {sorted(trespass)}. It is read only by "
        "construction, not by a flag: route effects through an account, never "
        "through this door."
    )
