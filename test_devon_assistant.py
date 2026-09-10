"""Tests for DEVON himself, and for the properties that keep him safe to import."""

from datetime import date

import pytest

from services.devon.approval import ApprovalQueue, ApprovalState
from services.devon.assistant import Devon
from services.devon.commands import Kind

TODAY = date(2026, 8, 22)


@pytest.fixture()
def devon():
    return Devon()


# -- captures are planned, never executed ------------------------------------


def test_a_capture_returns_a_plan_and_writes_nothing(devon):
    response = devon.ask(
        "Devon, remember the render infrastructure decision is blocking TQO go live",
        on_date=TODAY,
    )
    assert response.understood
    assert response.intent == "capture"
    assert response.plan is not None
    assert response.executed is False
    assert response.plan.to_dict()["executed"] is False


def test_a_capture_classifies_its_area_and_records_the_provenance(devon):
    response = devon.ask("Devon, remember the tqo channel monetization plan", on_date=TODAY)
    assert response.plan.area == "TQO"
    assert response.plan.area_provenance == "keyword classification"


def test_a_capture_builds_a_conforming_filename(devon):
    response = devon.ask("Devon, remember the n8n workflow needs a watchdog", on_date=TODAY)
    assert response.plan.filename.startswith("SYS_DOC_")
    assert response.plan.filename.endswith("_v1_2026-08-22.md")


def test_a_capture_with_no_identifiable_area_warns_rather_than_inventing_one(devon):
    response = devon.ask("Devon, remember the thing about the stuff", on_date=TODAY)
    assert response.plan.area is None
    assert any("will not invent" in w for w in response.plan.warnings)


def test_an_episode_idea_is_pinned_to_the_podcast_area(devon):
    response = devon.ask("Devon, new episode idea about grief and inheritance", on_date=TODAY)
    assert response.plan.area == "Podcast"
    assert response.plan.area_provenance == "fixed by intent"
    assert "Airtable Podcast HQ" in response.plan.destination


def test_a_capture_with_no_payload_asks_rather_than_filing_nothing(devon):
    response = devon.ask("Devon, remember", on_date=TODAY)
    assert response.plan is None
    assert "hold on to" in response.reply


# -- effects are gated -------------------------------------------------------


def test_shutdown_raises_an_approval_request_and_runs_nothing(devon):
    response = devon.ask("Devon, shut down the computer", on_date=TODAY)
    assert response.approval is not None
    assert response.approval.state is ApprovalState.PENDING
    assert response.executed is False
    assert "needs your ruling" in response.reply


def test_the_approval_request_states_what_happens(devon):
    response = devon.ask("Devon, restart the computer", on_date=TODAY)
    assert response.approval.what_happens.strip()
    assert "Reboots" in response.approval.what_happens


def test_the_approval_token_is_returned_once_for_the_caller(devon):
    response = devon.ask("Devon, take a screenshot", on_date=TODAY)
    assert response.approval_token
    result = devon.approvals.decide(
        response.approval.request_id, response.approval_token, "approve"
    )
    assert result.approved


def test_every_gated_intent_produces_an_approval_rather_than_an_action():
    devon = Devon()
    for utterance in [
        "Devon, shut down the computer",
        "Devon, restart the computer",
        "Devon, take a screenshot",
        "Devon, send a message to Karrie",
        "Devon, open calculator",
    ]:
        response = devon.ask(utterance, on_date=TODAY)
        assert response.approval is not None, utterance
        assert response.executed is False, utterance


def test_browser_effects_are_proposed_not_opened(devon):
    response = devon.ask("Devon, search for pgvector tuning", on_date=TODAY)
    assert response.kind is Kind.EFFECT
    assert response.executed is False
    assert "Ready to search" in response.reply


# -- honesty about live state ------------------------------------------------


def test_devon_refuses_to_invent_live_state(devon):
    response = devon.ask("Devon, what's on my plate?", on_date=TODAY)
    assert response.executed is False
    assert response.unverified
    assert "not read it this session" in response.reply


def test_a_briefing_names_the_lane_that_owns_the_data(devon):
    response = devon.ask("Devon, brief me", on_date=TODAY)
    assert "Notion" in response.reply
    assert response.unverified


def test_recall_points_at_the_thread_log(devon):
    response = devon.ask("Devon, what do we already know about the pack cut", on_date=TODAY)
    assert "Thread Log" in response.reason or "thread_log" in response.reason.lower()


def test_the_snapshot_warning_is_carried(devon):
    """The regenerated file lives in the session, not on Drive."""
    response = devon.ask("Devon, refresh my dashboard", on_date=TODAY)
    assert "not on Drive" in response.reply


# -- local answers still work ------------------------------------------------


def test_time_and_date_answer_locally(devon):
    assert devon.ask("what time is it", on_date=TODAY).executed
    response = devon.ask("what is the date", on_date=TODAY)
    assert response.executed
    assert "August" in response.reply


def test_an_unparsed_utterance_declines_without_acting(devon):
    response = devon.ask("blorp zzzz nonsense", on_date=TODAY)
    assert not response.understood
    assert response.plan is None
    assert response.approval is None


# -- receipts ----------------------------------------------------------------


def test_receipt_for_builds_a_valid_standing_receipt(devon):
    from services.devon import receipts

    text = devon.receipt_for(
        summary="Compiled the DEVON doctrine into executable checks.",
        area="Systems",
        decisions=["Doctrine is enforced in code"],
        open_threads=["The capture endpoint is still unauthenticated"],
        artifacts=["services/devon/"],
        files_opened=["SYS_SPEC_filing-laws-for-llms_v3"],
        on_date=TODAY,
    )
    receipt = receipts.parse_receipt(text)
    assert receipts.is_valid(receipt, TODAY)
    assert receipt.areas == ["Systems"]


def test_receipt_for_defaults_the_load_bearing_fields_to_none_not_missing(devon):
    from services.devon import receipts

    text = devon.receipt_for(summary="A short session.", area="Systems", on_date=TODAY)
    receipt = receipts.parse_receipt(text)
    assert receipt.files_opened == ["NONE"]
    assert receipt.unverified == ["NONE"]
    assert receipts.is_valid(receipt, TODAY)


def test_receipt_for_refuses_an_invented_area(devon):
    from services.devon.areas import AreaError

    with pytest.raises(AreaError):
        devon.receipt_for(summary="x", area="Business", on_date=TODAY)


# -- the gate is shared ------------------------------------------------------


def test_an_injected_queue_is_used(devon):
    queue = ApprovalQueue()
    assistant = Devon(approvals=queue)
    assistant.ask("Devon, shut down the computer", on_date=TODAY)
    assert len(queue.pending()) == 1


# -- the decline that carries a near miss, added 2026-09-10 ------------------
#
# Before this, a declined utterance threw away everything the parse knew and
# told the person to start again. `reason` was sitting right beside it holding
# the near miss. What the reply may say is governed by the same rule as the
# parse: an EFFECT intent is never offered, so a person who says "fire up
# chrome" is never handed "reboot the computer" to confirm.


@pytest.mark.parametrize(
    "utterance,expected,canonical",
    [
        ("give me a project status update", "status_report", "status report"),
        ("log the conversation we just had", "log_thread", "log this thread"),
        ("what is my plate looking like", "whats_on_my_plate", "what's on my plate"),
        ("what captures need triage", "triage", "show me untriaged captures"),
    ],
)
def test_a_near_miss_decline_names_what_devon_almost_understood(
    devon, utterance, expected, canonical
):
    """The near miss was already in `reason` at 5ff4348 and was thrown away.

    Each of these is the intent the person plainly meant, sitting just under its
    floor. DEVON still will not act on it, and now he says which one it was and
    what to say instead, quoting canon rather than whichever alias matched.
    """
    response = devon.ask(utterance, on_date=TODAY)
    assert not response.understood, f"{utterance!r} routed; pick another near miss"
    assert response.suggestion == expected
    assert response.suggestion_phrase == canonical
    assert canonical in response.reply
    assert 0.0 < response.suggestion_score < 1.0


def test_a_decline_with_no_honest_near_miss_says_so_and_offers_nothing(devon):
    response = devon.ask("wubba lubba dub dub", on_date=TODAY)
    assert not response.understood
    assert response.suggestion is None
    assert response.suggestion_phrase is None
    assert "take it from the top" in response.reply


def test_a_suggested_decline_still_does_nothing_at_all(devon):
    """A suggestion is a question. It is not a plan, a card, or an execution."""
    for text in ("log this to the thred log", "an idee for an episode", "give me a stat"):
        response = devon.ask(text, on_date=TODAY)
        if response.understood:
            continue
        assert response.executed is False
        assert response.plan is None
        assert response.approval is None
        assert response.approval_token is None
        assert response.intent == "unknown"


def test_no_decline_ever_offers_an_effect_to_confirm(devon):
    """INVARIANT 2 at the surface a person actually reads.

    Drives every trigger of every effect intent below its floor and checks both
    halves of what comes back: the structured suggestion, and the reply text,
    which must not name the intent or quote any phrase that routes to it.
    """
    from services.devon import commands as commands_mod

    effect_triggers = [
        commands_mod.normalize(trigger)
        for intent in commands_mod.effect_intents()
        for trigger in intent.triggers
    ]
    effect_names = {intent.name.replace("_", " ") for intent in commands_mod.effect_intents()}

    declined = 0
    for intent in commands_mod.effect_intents():
        for trigger in intent.triggers:
            for text in (
                trigger[: max(1, len(trigger) - 3)],
                "the " + trigger + " thing",
                trigger.replace("a", "e"),
                trigger + " maybe",
            ):
                response = devon.ask(text, on_date=TODAY)
                if response.understood:
                    continue
                declined += 1
                assert response.suggestion not in {
                    i.name for i in commands_mod.effect_intents()
                }, f"{text!r} suggested the effect {response.suggestion}"

                spoken = commands_mod.normalize(response.reply)
                padded = " " + spoken + " "
                for banned in effect_triggers:
                    assert f" {banned} " not in padded, (
                        f"{text!r} produced a reply quoting the effect trigger {banned!r}"
                    )
                for banned in effect_names:
                    assert f" {banned} " not in padded, (
                        f"{text!r} produced a reply naming the effect intent {banned!r}"
                    )
    assert declined > 30, f"only {declined} declines were exercised; this proves little"


def test_the_specific_case_this_arc_was_opened_for(devon):
    """"fire up chrome" must never produce a prompt containing "reboot the computer"."""
    for text in ("fire up chrom", "fire up", "fyre up chrom"):
        response = devon.ask(text, on_date=TODAY)
        assert "reboot" not in response.reply.lower()
        assert "restart" not in response.reply.lower()
        assert "shut down" not in response.reply.lower()


def test_the_suggestion_survives_the_json_a_surface_would_render(devon):
    response = devon.ask("wubba lubba dub dub", on_date=TODAY)
    payload = response.to_dict()
    assert payload["understood"] is False
    assert payload["executed"] is False
    assert payload["suggestion"] is None
    assert "suggestion_phrase" in payload
    assert "suggestion_score" in payload
