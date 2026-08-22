"""Tests for the command router, including the upstream bugs it fixes."""

import pytest

from services.devon import commands
from services.devon.commands import Kind, Method, parse

# -- wake word ---------------------------------------------------------------


def test_strips_a_leading_wake_word():
    assert commands.strip_wake_word("Devon, brief me") == "brief me"
    assert commands.strip_wake_word("devon brief me") == "brief me"
    assert commands.strip_wake_word("Jarvis: brief me") == "brief me"


def test_strips_the_wake_word_only_once_and_only_leading():
    """Stripping every occurrence would eat the word out of a capture about Devon."""
    text = "Devon, remember Devon owes me a callback"
    assert commands.strip_wake_word(text) == "remember Devon owes me a callback"


def test_leaves_text_without_a_wake_word_alone():
    assert commands.strip_wake_word("what time is it") == "what time is it"


# -- the DEVON command language ---------------------------------------------


@pytest.mark.parametrize(
    "utterance,expected",
    [
        ("Devon, remember the render decision is open", "capture"),
        ("Devon, add a task to verify the grid hash", "add_task"),
        ("Devon, what's on my plate?", "whats_on_my_plate"),
        ("Devon, start a project called ACX pilot", "start_project"),
        ("Devon, status report", "status_report"),
        ("Devon, new episode idea about the shared shadow", "episode_idea"),
        ("Devon, brief me", "brief"),
        ("Devon, log this thread", "log_thread"),
        ("receipt", "log_thread"),
        ("Devon, what do we already know about the pack cut", "recall"),
        ("Devon, refresh my dashboard", "refresh_dashboard"),
        ("Devon, refresh my brain map", "refresh_brain_map"),
    ],
)
def test_every_canon_command_phrase_routes(utterance, expected):
    result = parse(utterance)
    assert result.understood, f"{utterance} was not understood: {result.reason}"
    assert result.name == expected


def test_capture_extracts_its_payload():
    result = parse("Devon, remember the render infrastructure decision is still open")
    assert result.name == "capture"
    assert result.payload == "the render infrastructure decision is still open"


def test_add_task_strips_the_trailing_preposition():
    """Longest lead-in wins, so 'add a task to' beats 'add a task'."""
    result = parse("Devon, add a task to verify the grid hash on device")
    assert result.payload == "verify the grid hash on device"


def test_start_project_extracts_the_name():
    result = parse("Devon, start a project called NCO Forge relaunch")
    assert result.payload == "NCO Forge relaunch"


def test_recall_extracts_the_topic():
    result = parse("Devon, what do we already know about the Airtable quota")
    assert result.name == "recall"
    assert result.payload == "the Airtable quota"


# -- the upstream substring bug ---------------------------------------------


def test_open_no_longer_swallows_any_sentence_containing_it():
    """Upstream routed on `if "open" in query`, so this hit the app launcher."""
    result = parse("Devon, remember I need to open up to Karrie about the schedule")
    assert result.name == "capture"
    assert result.name != "open_app"


def test_a_real_open_request_still_routes():
    result = parse("Devon, open calculator")
    assert result.name == "open_app"


# -- confidence floors on destructive intents -------------------------------


def test_destructive_intents_carry_the_highest_floors():
    for name in ("shutdown", "restart"):
        assert commands.INTENTS_BY_NAME[name].min_score >= 0.92


def test_a_loose_match_does_not_trigger_a_shutdown():
    """Upstream matched every intent at a flat 60 percent, shutdown included."""
    result = parse("shut the door down the hall")
    assert result.name != "shutdown"


def test_every_effect_intent_scores_above_a_read_intent_floor():
    reads = [i for i in commands.ALL_INTENTS if i.kind is Kind.READ]
    effects = [i for i in commands.ALL_INTENTS if i.kind is Kind.EFFECT]
    assert min(e.min_score for e in effects) >= min(r.min_score for r in reads)


def test_the_approval_gated_set_covers_the_irreversible_intents():
    gated = {i.name for i in commands.approval_gated_intents()}
    assert {"shutdown", "restart", "send_message", "open_app", "take_screenshot"} <= gated


def test_every_gated_intent_is_an_effect():
    for intent in commands.approval_gated_intents():
        assert intent.kind is Kind.EFFECT


# -- declining ---------------------------------------------------------------


def test_declines_rather_than_guessing():
    result = parse("wubba lubba dub dub")
    assert not result.understood
    assert "below its floor" in result.reason or result.reason == "no candidate"


def test_empty_input_declines():
    assert not parse("").understood
    assert not parse("Devon").understood


def test_the_reason_names_the_score_and_the_floor():
    result = parse("something entirely unrelated to any command")
    assert not result.understood
    assert result.score >= 0.0


# -- matching methods --------------------------------------------------------


def test_exact_match_is_reported_as_exact():
    assert parse("what time is it").method is Method.EXACT


def test_fuzzy_match_handles_a_misheard_phrase():
    result = parse("what tyme is it")
    assert result.understood
    assert result.name == "get_time"
    assert result.method is Method.FUZZY


def test_intent_names_are_unique():
    names = [i.name for i in commands.ALL_INTENTS]
    assert len(names) == len(set(names))
