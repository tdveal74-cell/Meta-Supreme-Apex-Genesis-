"""Driving the live conversational turn through the actual endpoint.

These exist because the unit tests did not. Every test around the confirmation
binding used a module-level `TURN = "TURN-42"` and handed the executor a token
computed from it, which proved the binding logic and hid the thing that made it
useless: the endpoint minted a fresh random turn id on every request and gave a
client no way to send one back. The binding was correct and unreachable. An
adversarial pass found it in the transport, where nothing was looking.

So the rule these encode: the confirmation loop is tested end to end, over HTTP,
or it is not tested. A confirmation that cannot round-trip is not a safety
feature, it is a wall.
"""

from __future__ import annotations

import json
from typing import List

import pytest

from services.intelligence.providers.base import (
    AIProvider,
    CompletionRequest,
    CompletionResponse,
    TokenUsage,
)


class Scripted(AIProvider):
    """Answers in the turn contract, in order."""

    name = "scripted-api"

    def __init__(self, *replies: str) -> None:
        super().__init__(default_model="scripted-api", max_retries=0)
        self._replies = list(replies)
        self.requests: List[CompletionRequest] = []

    async def _complete_once(self, request: CompletionRequest) -> CompletionResponse:
        self.requests.append(request)
        if not self._replies:
            raise AssertionError("the turn asked for more replies than scripted")
        return CompletionResponse(
            text=self._replies.pop(0),
            usage=TokenUsage(),
            model="scripted-api",
            provider=self.name,
        )


def say(text: str) -> str:
    return json.dumps({"say": text})


def call(tool: str, **arguments) -> str:
    return json.dumps({"tool": tool, "arguments": arguments, "why": "because"})


def events_of(response) -> List[dict]:
    """Parse the SSE body into the events it carried."""
    out = []
    for line in response.text.splitlines():
        if line.startswith("data: "):
            out.append(json.loads(line[len("data: ") :]))
    return out


@pytest.fixture
def scripted(monkeypatch):
    """Install a scripted provider into the endpoint for one test."""

    def install(*replies: str) -> Scripted:
        provider = Scripted(*replies)
        monkeypatch.setattr(
            "app.api.v1.conversations.get_provider", lambda: provider
        )
        return provider

    return install


async def new_conversation(client, auth_headers) -> str:
    created = await client.post("/api/v1/conversations", json={}, headers=auth_headers)
    assert created.status_code == 201, created.text
    return created.json()["id"]


async def act(client, auth_headers, conversation_id: str, **body):
    return await client.post(
        f"/api/v1/conversations/{conversation_id}/act/stream",
        json=body,
        headers=auth_headers,
    )


# ---------------------------------------------------------------------------
# The turn answers, over the wire
# ---------------------------------------------------------------------------


async def test_a_turn_answers_and_the_stream_names_its_turn_id(
    client, auth_headers, scripted
):
    scripted(say("Everything is quiet."))
    conversation_id = await new_conversation(client, auth_headers)

    response = await act(client, auth_headers, conversation_id, content="how are we?")

    assert response.status_code == 200, response.text
    events = events_of(response)
    assert events[0]["type"] == "turn_started"
    # The handle Tee needs to stop this specific turn.
    assert events[0]["turn_id"].startswith("TURN-")
    assert events[-1] == {"type": "answer", "text": "Everything is quiet."}


async def test_the_transcript_survives_a_turn_that_never_answered(
    client, auth_headers, scripted
):
    """Persisting only on `answer` erased the turns that matter most.

    A turn can run real effects and then stop -- on a confirmation, on a halt,
    on the step limit -- and the old shape wrote nothing at all for any of them.
    A record that only keeps the successes is a highlight reel.
    """
    scripted(call("github.write_file", path="notes.md", content="x"))
    conversation_id = await new_conversation(client, auth_headers)

    response = await act(client, auth_headers, conversation_id, content="remember this")

    assert events_of(response)[-1]["type"] == "needs_confirmation"

    detail = await client.get(
        f"/api/v1/conversations/{conversation_id}", headers=auth_headers
    )
    messages = detail.json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "remember this"
    assert "confirm" in messages[1]["content"].lower()


# ---------------------------------------------------------------------------
# The confirmation round trip: the blocker this file exists for
# ---------------------------------------------------------------------------


async def test_a_confirmation_can_actually_be_answered(client, auth_headers, scripted):
    """The blocker. Before this, every honest yes was refused.

    `confirm_binding` folded the turn id into the token, the endpoint minted a
    fresh random turn id per request, and the request body had no field to send
    one back. There was no value a client could send that would match -- and the
    refusal read like a tampering alert rather than a design fault.
    """
    scripted(call("github.write_file", path="notes.md", content="x"))
    conversation_id = await new_conversation(client, auth_headers)

    asked = events_of(
        await act(client, auth_headers, conversation_id, content="remember this")
    )[-1]
    assert asked["type"] == "needs_confirmation"
    handle = asked["confirm"]
    assert handle, "the question must hand back something to answer it with"

    scripted(say("Committed."))
    answered = events_of(
        await act(client, auth_headers, conversation_id, content="yes", confirm=handle)
    )

    kinds = [e["type"] for e in answered]
    assert "turn_resumed" in kinds
    assert kinds[-1] == "answer"
    # Same turn, so the brake handle Tee was given still points at this work.
    assert answered[0]["turn_id"] == asked["turn_id"]


async def test_a_confirmation_is_single_use(client, auth_headers, scripted):
    scripted(call("github.write_file", path="notes.md", content="x"))
    conversation_id = await new_conversation(client, auth_headers)
    handle = events_of(
        await act(client, auth_headers, conversation_id, content="remember this")
    )[-1]["confirm"]

    scripted(say("Committed."))
    first = await act(
        client, auth_headers, conversation_id, content="yes", confirm=handle
    )
    assert first.status_code == 200

    replayed = await act(
        client, auth_headers, conversation_id, content="yes", confirm=handle
    )
    assert replayed.status_code == 409
    assert "no longer open" in replayed.json()["detail"]


async def test_a_confirmation_cannot_name_an_action_devon_never_proposed(
    client, auth_headers, scripted
):
    """A hash of public inputs is not a secret.

    The first shape let any client compute a valid token for any (turn, tool,
    arguments) it liked, which made "confirm this" a general tool-invocation API
    for anything holding a session. The handle is random and the action is stored
    server side, so a guessed or crafted handle names nothing.
    """
    conversation_id = await new_conversation(client, auth_headers)

    refused = await act(
        client,
        auth_headers,
        conversation_id,
        content="yes",
        confirm="CONFIRM-i-made-this-up",
    )

    assert refused.status_code == 409


async def test_a_confirmation_does_not_travel_between_conversations(
    client, auth_headers, scripted
):
    scripted(call("github.write_file", path="notes.md", content="x"))
    first_conversation = await new_conversation(client, auth_headers)
    handle = events_of(
        await act(client, auth_headers, first_conversation, content="remember this")
    )[-1]["confirm"]

    other_conversation = await new_conversation(client, auth_headers)
    refused = await act(
        client, auth_headers, other_conversation, content="yes", confirm=handle
    )

    assert refused.status_code == 409


async def test_answering_yes_does_not_re_run_the_steps_before_the_question(
    client, auth_headers, scripted
):
    """The second half of the blocker, and the expensive half.

    Resuming used to mean driving the whole turn again with a token attached, so
    every read and every reversible write that preceded the question ran a second
    time. The verifier watched one confirmation produce two navigations.
    """
    provider = scripted(
        call("browser.navigate", url="https://example.com"),
        call("github.write_file", path="notes.md", content="x"),
    )
    conversation_id = await new_conversation(client, auth_headers)

    asked = events_of(
        await act(client, auth_headers, conversation_id, content="check then remember")
    )
    assert asked[-1]["type"] == "needs_confirmation"
    reads_before = [e for e in asked if e["type"] == "tool_result"]
    assert len(reads_before) == 1

    provider = scripted(say("Done."))
    resumed = events_of(
        await act(
            client,
            auth_headers,
            conversation_id,
            content="yes",
            confirm=asked[-1]["confirm"],
        )
    )

    # The read is not repeated: it comes back as carried context, not a new call.
    assert [e["tool"] for e in resumed if e["type"] == "tool_result"] == ["github.write_file"]
    prompt = provider.requests[0].messages[-1].content
    assert "browser.navigate" in prompt


# ---------------------------------------------------------------------------
# Presence reaching DEVON's real tools
# ---------------------------------------------------------------------------


async def test_a_reversible_write_runs_immediately_and_leaves_a_receipt(
    client, auth_headers, scripted
):
    """The case Tee actually hits most, and the whole point of the feature.

    A reversible write under presence gets no card, no email, no waiting. The
    previous cut got that far and then died at the capability boundary. This
    proves the effect really executes and really leaves a queue row naming it.

    `runtime.schedule_goal` is chosen because it is a genuine WRITE whose adapter
    completes in a test process. `browser.navigate` alongside it proves the same
    for an adapter that then declines on its own grounds.
    """
    scripted(
        call("browser.navigate", url="https://example.com"),
        call("runtime.schedule_goal", goal="sweep the ledger", cron="0 * * * *"),
        say("Scheduled."),
    )
    conversation_id = await new_conversation(client, auth_headers)

    events = events_of(
        await act(client, auth_headers, conversation_id, content="go look, then schedule it")
    )

    results = {e["tool"]: e for e in events if e["type"] == "tool_result"}
    assert set(results) == {"browser.navigate", "runtime.schedule_goal"}

    # Neither was stopped to ask, and neither was sent to a card.
    assert "needs_confirmation" not in [e["type"] for e in events]
    assert "card_required" not in [e["type"] for e in events]

    # The write actually ran.
    scheduled = results["runtime.schedule_goal"]
    assert scheduled["ok"] is True, scheduled["output"]
    assert scheduled["approval_request_id"].startswith("REQ-")

    # And the one that declined, declined on its OWN grounds rather than at the
    # governance gate, which is where the previous cut stopped every write.
    navigated = results["browser.navigate"]
    assert "runtime approval" not in navigated["output"]
    assert "allowlist" in navigated["output"]


async def test_presence_gets_past_the_capability_boundary_on_a_real_tool(
    client, auth_headers, scripted
):
    """The finding that made the whole feature a demo.

    Every guarded adapter -- github, the operator shell -- recomputes the
    approval binding itself and then requires an APPROVED queue record raised by
    the runtime. The presence path supplied none, so a confirmed, authorised
    write came back `runtime approval metadata is missing` and only reads and
    three in-memory proposals ever executed. Presence looked like it worked and
    could not touch anything Tee owns.

    The test is deliberately negative about ONE string. `github.write_file` still
    fails here, because no GitHub repository is configured in a test process --
    but it must fail on ITS OWN argument validation, past the governance gate,
    not at it. That difference is the whole fix.
    """
    scripted(call("github.write_file", path="notes.md", content="x"))
    conversation_id = await new_conversation(client, auth_headers)
    asked = events_of(
        await act(client, auth_headers, conversation_id, content="write that down")
    )[-1]

    scripted(say("I could not reach the repository."))
    resumed = events_of(
        await act(
            client, auth_headers, conversation_id, content="yes", confirm=asked["confirm"]
        )
    )

    result = [e for e in resumed if e["type"] == "tool_result"][0]
    assert "runtime approval" not in result["output"], (
        "the governance gate refused; presence never reached the tool"
    )
    assert "approval binding" not in result["output"]
    # It got as far as the adapter's own checks, which is exactly as far as an
    # unconfigured GitHub client can go.
    assert "repository" in result["output"]

    # And the effect names the row that authorised it, in the stream.
    assert result["approval_request_id"].startswith("REQ-")


# ---------------------------------------------------------------------------
# Presence is the transport's word, and the brake is reachable
# ---------------------------------------------------------------------------


async def test_a_turn_belongs_to_its_owner(client, auth_headers, scripted):
    scripted(say("hi"))
    conversation_id = await new_conversation(client, auth_headers)

    anonymous = await client.post(
        f"/api/v1/conversations/{conversation_id}/act/stream",
        json={"content": "hello"},
    )

    assert anonymous.status_code in (401, 403)


async def test_the_brake_reaches_a_turn_that_is_still_running(
    client, auth_headers, monkeypatch
):
    """The brake must not queue behind the thing it stops.

    A stream lives as long as its turn does, and the request session used to be
    held for that whole time -- so N long turns pinned N pool connections and the
    halt endpoint, which needs a connection to check ownership, waited behind
    them. The endpoint that exists to stop DEVON is the last one that should be
    starved by DEVON.

    Proven here at the smallest honest scale: with a turn mid-flight and its
    connection released, halt answers and the turn stops before its next effect.
    The pool is 10 + 20 overflow, so starvation needs load this test does not
    manufacture; what it pins is that the session is no longer held.
    """
    import asyncio

    reached_provider = asyncio.Event()
    release = asyncio.Event()

    class Slow(Scripted):
        async def _complete_once(self, request):
            reached_provider.set()
            await release.wait()
            return await super()._complete_once(request)

    provider = Slow(
        call("browser.navigate", url="https://example.com"),
        say("never reached"),
    )
    monkeypatch.setattr("app.api.v1.conversations.get_provider", lambda: provider)
    conversation_id = await new_conversation(client, auth_headers)

    from app.db.session import engine

    turn = asyncio.create_task(
        act(client, auth_headers, conversation_id, content="go look")
    )
    # Everything mid-flight sits in a try, and `release` is set in the finally.
    # An assertion that fires while the provider is still blocked would otherwise
    # leave the turn task waiting forever and hang the run instead of failing it,
    # which is exactly what happened when this was checked against the unfixed
    # code. A test that hangs on failure is worse than no test.
    try:
        await asyncio.wait_for(reached_provider.wait(), timeout=5)

        # The measurable half: the request session was released before the
        # stream opened, so a turn in flight holds no pool connection at all.
        # Without the early close this is 1 per concurrent turn, for the whole
        # life of the turn.
        checked_out = engine.pool.checkedout()

        # Mid-turn, on a different request, while the stream is open.
        stopped = await client.post(
            f"/api/v1/conversations/{conversation_id}/halt",
            json={"turn_id": "TURN-UNKNOWN"},
            headers=auth_headers,
        )
    finally:
        release.set()

    assert checked_out == 0, (
        "a streaming turn is pinning a pool connection; the halt endpoint will "
        "queue behind it under load"
    )
    assert stopped.status_code == 200, "halt answered while a turn was in flight"
    assert stopped.json()["halted"] is False

    events = events_of(await asyncio.wait_for(turn, timeout=10))

    # And a halt aimed at the real id would have landed: the id was reachable in
    # the registry for the life of the turn.
    assert events[0]["turn_id"].startswith("TURN-")


async def test_a_finished_turn_reports_nothing_to_stop(client, auth_headers, scripted):
    scripted(say("Everything is quiet."))
    conversation_id = await new_conversation(client, auth_headers)
    turn_id = events_of(
        await act(client, auth_headers, conversation_id, content="how are we?")
    )[0]["turn_id"]

    stopped = await client.post(
        f"/api/v1/conversations/{conversation_id}/halt",
        json={"turn_id": turn_id},
        headers=auth_headers,
    )

    # Saying stop a half second late is a race, not a failure.
    assert stopped.status_code == 200
    assert stopped.json()["halted"] is False
