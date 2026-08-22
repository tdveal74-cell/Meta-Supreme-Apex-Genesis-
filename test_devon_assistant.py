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
