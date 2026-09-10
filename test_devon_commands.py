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


# ---------------------------------------------------------------------------
# The 2026-09-10 enrichment, and the invariants it is not allowed to bend.
#
# The parser was widened because 14 of 24 realistic paraphrases were declined at
# 5ff4348. Widening a router is exactly the change that erodes a floor by
# accident, so the guards below are the price of the widening, and they are
# written to fail loudly rather than to pass quietly.
# ---------------------------------------------------------------------------

# INVARIANT 1. Every floor as it stood at 5ff4348, read off that commit rather
# than typed from memory. This table only ever moves up, and only on Tee's
# ruling: if a change needs a floor lowered to pass, the change is wrong.
FLOORS_AT_5FF4348 = {
    "capture": 0.80,
    "add_task": 0.80,
    "whats_on_my_plate": 0.78,
    "start_project": 0.82,
    "status_report": 0.80,
    "episode_idea": 0.82,
    "brief": 0.80,
    "log_thread": 0.84,
    "recall": 0.76,
    "triage": 0.80,
    "refresh_dashboard": 0.84,
    "refresh_brain_map": 0.84,
    "get_time": 0.72,
    "get_date": 0.72,
    "get_weather": 0.74,
    "get_news": 0.74,
    "search_web": 0.78,
    "play_youtube": 0.80,
    "open_app": 0.86,
    "take_screenshot": 0.84,
    "send_message": 0.88,
    "shutdown": 0.92,
    "restart": 0.92,
    "stop": 0.82,
}


@pytest.mark.parametrize("name,floor", sorted(FLOORS_AT_5FF4348.items()))
def test_no_floor_is_ever_lowered(name, floor):
    """INVARIANT 1. Not one, not by 0.01."""
    intent = commands.INTENTS_BY_NAME[name]
    assert intent.min_score >= floor, (
        f"{name} floor dropped from {floor} to {intent.min_score}. A floor is not "
        "a tuning knob; widen the phrases instead."
    )


def test_the_floor_table_covers_every_intent():
    """A guard that quietly stopped covering an intent would pass forever."""
    assert set(FLOORS_AT_5FF4348) == {i.name for i in commands.ALL_INTENTS}


# INVARIANT 2. An EFFECT intent is never offered as a suggestion, at any score.
# "fire up chrome" scored highest against "reboot the computer" at 5ff4348, so a
# naive did-you-mean built on the top candidate would ask a person to confirm
# rebooting their machine because they asked to open a browser.


def _below_floor_variants(phrase):
    """Mangle a phrase the way a microphone and a tired speaker do."""
    return [
        phrase[: max(1, len(phrase) - 3)],
        "the " + phrase + " thing",
        phrase.replace("a", "e"),
        " ".join(phrase.split()[:-1]) or phrase,
        phrase + " maybe",
        phrase[1:],
    ]


def test_no_effect_intent_is_ever_suggested():
    """INVARIANT 2, driven over every trigger of every effect intent."""
    declined = 0
    for intent in commands.effect_intents():
        for phrase in intent.triggers:
            for text in _below_floor_variants(phrase):
                result = parse(text)
                if result.understood:
                    continue  # cleared its own floor, which is the gate's job
                declined += 1
                assert (
                    result.suggestion is None
                    or result.suggestion.kind is not Kind.EFFECT
                ), f"{text!r} offered the effect intent {result.suggestion_name}"
    assert declined > 50, (
        f"only {declined} variants reached the decline path, so this test is not "
        "actually exercising the suggestion rule"
    )


def test_the_suggestion_gate_refuses_every_effect_intent_directly():
    """Belt and braces: call the gate itself, at scores that would otherwise pass."""
    for intent in commands.effect_intents():
        assert not commands.may_be_suggested(intent, intent.min_score - 0.01)
        assert not commands.may_be_suggested(intent, 0.99)


def test_a_declined_effect_near_miss_names_nothing_a_person_could_confirm():
    """The decline reason reaches an API caller through DevonResponse.reason.

    So when the closest thing DEVON found was an effect, the reason may report
    the score and the floor but must not name the phrase. Otherwise a surface
    that renders it puts "reboot the computer" in front of somebody who asked
    for something else, which is the prompt this whole arc exists to prevent.
    """
    checked = 0
    for intent in commands.effect_intents():
        for phrase in intent.triggers:
            for text in _below_floor_variants(phrase):
                result = parse(text)
                if result.understood or "effect intent" not in result.reason:
                    continue
                checked += 1
                # A non effect fallback may still be offered here, and that is
                # the design: the effect is discarded and the best read or
                # capture candidate takes its place. What must not happen is the
                # effect itself reaching a person, in either field.
                assert (
                    result.suggestion is None
                    or result.suggestion.kind is not Kind.EFFECT
                )
                for word in commands.normalize(phrase).split():
                    if len(word) < 4:
                        continue
                    assert word not in result.reason, (
                        f"the decline reason for {text!r} names {word!r} from the "
                        f"effect phrase {phrase!r}"
                    )
    assert checked > 30, f"only {checked} effect near miss declines were seen"


# INVARIANT 3. A suggestion is a question to a person, never a route.


def test_a_suggestion_is_never_a_route():
    """INVARIANT 3. Declined stays declined, whatever came back beside it."""
    seen_a_suggestion = False
    for intent in commands.ALL_INTENTS:
        for phrase in intent.triggers:
            for text in _below_floor_variants(phrase):
                result = parse(text)
                if result.understood:
                    continue
                assert result.intent is None
                assert result.name == "unknown"
                assert result.requires_approval is False
                assert result.is_effect is False
                if result.suggestion is not None:
                    seen_a_suggestion = True
    assert seen_a_suggestion, "no suggestion was produced at all, so this proves nothing"


# INVARIANT 4, that services/devon stays effect free, lives in
# test_devon_integrity.py. Nothing added here can reach a provider, and that file
# proves it by reading the imports rather than by trusting this sentence.


# -- the widening is additive, and only additive -----------------------------

# Canon as it stood at 5ff4348, read off that commit. `phrases` carries what the
# two Drive documents and upstream actually say. Colloquial paraphrases go in
# `aliases`, so this table may not change without a source changing with it.
CANON_PHRASES_AT_5FF4348 = {
    "capture": ("remember", "remember this", "make a note", "note this", "capture this"),
    "add_task": ("add a task", "add task", "new task", "remind me to"),
    "whats_on_my_plate": (
        "what's on my plate",
        "whats on my plate",
        "what is on my plate",
        "what do i have on",
        "what's due",
    ),
    "start_project": (
        "start a project called",
        "start a project",
        "new project called",
        "new project",
    ),
    "status_report": ("status report", "give me a status report", "project status"),
    "episode_idea": ("new episode idea", "episode idea", "add an episode idea"),
    "brief": ("brief me", "give me the briefing", "morning briefing", "briefing"),
    "log_thread": ("log this thread", "log this conversation", "receipt", "file a receipt"),
    "recall": (
        "what do we already know about",
        "what do we know about",
        "what did we decide about",
        "have we discussed",
    ),
    "triage": ("show me untriaged captures", "untriaged captures", "what needs filing"),
    "refresh_dashboard": (
        "refresh my dashboard",
        "refresh the dashboard",
        "rebuild my dashboard",
    ),
    "refresh_brain_map": (
        "refresh my brain map",
        "refresh the brain map",
        "rebuild my brain map",
    ),
    "get_time": (
        "what time is it",
        "tell me the time",
        "current time",
        "what's the time",
        "time now",
    ),
    "get_date": (
        "what's the date",
        "what is the date",
        "today's date",
        "current date",
        "what date is it",
    ),
    "get_weather": (
        "what's the weather",
        "current weather",
        "weather report",
        "weather today",
        "how's the weather",
    ),
    "get_news": ("latest news", "tell me the news", "news headlines", "what's the news"),
    "search_web": ("search for", "look up", "google for", "find information about"),
    "play_youtube": ("play on youtube", "play youtube", "put on youtube"),
    "open_app": ("open calculator", "open browser", "open whatsapp", "launch"),
    "take_screenshot": ("take a screenshot", "capture screen", "screen capture"),
    "send_message": ("send a message to", "send message", "message"),
    "shutdown": ("shut down the computer", "shutdown the computer", "power off the computer"),
    "restart": ("restart the computer", "reboot the computer", "restart the system"),
    "stop": ("goodbye", "stop listening", "that's all", "exit"),
}


@pytest.mark.parametrize("name,phrases", sorted(CANON_PHRASES_AT_5FF4348.items()))
def test_canon_phrases_are_never_edited_to_make_something_route(name, phrases):
    """Widening happens in `aliases`. Canon says what the sources say."""
    assert commands.INTENTS_BY_NAME[name].phrases == phrases


def test_every_trigger_routes_to_its_own_intent():
    """An alias that steals another intent's utterance is a misroute shipped."""
    for intent in commands.ALL_INTENTS:
        for trigger in intent.triggers:
            result = parse(trigger)
            assert result.understood, f"{intent.name} trigger {trigger!r} declines"
            assert result.name == intent.name, (
                f"{intent.name} trigger {trigger!r} routes to {result.name}"
            )


def test_no_two_intents_claim_the_same_trigger():
    """Two intents sharing a trigger is a silent misroute: exact match returns
    the first one declared, so the loser would never be reachable.

    Within one intent a duplicate is harmless and there is one: canon carries
    both "what's on my plate" and "whats on my plate" for `whats_on_my_plate`,
    which the normaliser now joins into the same string. That is canon, so it
    stays as the source wrote it rather than being tidied away.
    """
    owners = {}
    for intent in commands.ALL_INTENTS:
        for trigger in intent.triggers:
            key = commands.normalize(trigger)
            assert key, f"{intent.name} trigger {trigger!r} normalises to nothing"
            owner = owners.get(key)
            assert owner in (None, intent.name), (
                f"{trigger!r} is claimed by both {owner} and {intent.name}"
            )
            owners[key] = intent.name


def test_no_one_word_alias_on_an_approval_gated_intent():
    """A one word alias at the front of a sentence is the upstream bug returning.

    Canon is exempt, because "message" and "launch" are what the sources say and
    this module does not get to edit them. An alias is ours, so it has to earn
    its place, and every one word alias tried on a gated intent took more than
    it gave back.
    """
    offenders = [
        (intent.name, alias)
        for intent in commands.approval_gated_intents()
        for alias in intent.aliases
        if len(commands.normalize(alias).split()) < 2
    ]
    assert len(offenders) <= commands.MAX_ONE_WORD_ALIASES_ON_GATED_INTENTS, offenders


# -- an effect can only be reached deliberately ------------------------------


def test_an_effect_phrase_buried_in_prose_does_not_reach_the_effect():
    """Measured at 5ff4348: the first three of these routed to a gated effect.

    "launch" was matched inside "relaunch" with no word boundary, and a phrase
    found anywhere in the sentence beat one the speaker actually opened with.
    """
    for text in (
        "the podcast launch is on Friday",
        "kick off a project called NCO relaunch",
        "I left a message for Karrie on her desk",
        "her message was pretty blunt",
        "the search for a new editor is on",
        "open questions remain on the render",
    ):
        result = parse(text)
        assert not (result.understood and result.is_effect), (
            f"{text!r} reached the effect intent {result.name}"
        )


def test_a_capture_that_mentions_an_effect_stays_a_capture():
    for text in (
        "remember to search the web for the grid spec",
        "remember to launch the campaign on Friday",
        "remember I need to open up to Karrie about the schedule",
        "remember to take a screenshot of the ledger",
        "note that the launch slipped a week",
    ):
        result = parse(text)
        assert result.understood, f"{text!r} declined"
        assert result.intent.kind is Kind.CAPTURE, f"{text!r} routed to {result.name}"


# -- the normaliser ----------------------------------------------------------


def test_contractions_are_joined_so_a_fuzzy_match_becomes_an_exact_one():
    assert commands.normalize("what's the date") == commands.normalize("whats the date")
    assert parse("whats the date").method is Method.EXACT


def test_politeness_does_not_change_which_intent_is_chosen():
    for core in ("brief me", "status report", "what time is it", "shut down the computer"):
        expected = parse(core).name
        for wrapper in ("please %s", "can you %s", "%s please", "%s for me", "hey devon %s"):
            result = parse(wrapper % core)
            assert result.understood, f"{wrapper % core!r} declined"
            assert result.name == expected


def test_normalize_is_idempotent_and_never_empties_a_trigger():
    for intent in commands.ALL_INTENTS:
        for trigger in intent.triggers:
            once = commands.normalize(trigger)
            assert once, f"{trigger!r} normalises to nothing"
            assert commands.normalize(once) == once


def test_the_split_compounds_speech_to_text_produces_are_repaired():
    assert parse("take a screen shot").name == "take_screenshot"
    assert parse("put on you tube the render cut").name == "play_youtube"


def test_a_wake_word_behind_politeness_is_still_stripped():
    assert parse("hey devon brief me").name == "brief"


def test_a_suggestion_must_share_a_word_that_carries_meaning():
    """Measured 2026-09-10: without this, letter overlap alone drew "did you mean
    get time" out of "what about the render" at 0.69."""
    assert not commands.shares_meaning("what about the render", "what time is it")
    assert commands.shares_meaning("give me the status", "give me a status report")


# -- the utterances this arc was opened for ----------------------------------

# Every one of these was declined at 5ff4348, verbatim from that run. They sit
# here so that a later change which re-breaks them has to say so.
THE_FOURTEEN_MISSES_AT_5FF4348 = [
    ("jot that down", "capture"),
    ("stick a task on the list", "add_task"),
    ("whats my day looking like", "whats_on_my_plate"),
    ("give me the status", "status_report"),
    ("wheres everything at", "status_report"),
    ("I have an idea for an episode", "episode_idea"),
    ("log this to the thread", "log_thread"),
    ("pull up what we said before", "recall"),
    ("triage that", "triage"),
    ("give me the headlines", "get_news"),
    ("look that up for me", "search_web"),
    ("put on some music", "play_youtube"),
    ("fire up chrome", "open_app"),
    ("grab a screenshot", "take_screenshot"),
]


@pytest.mark.parametrize("utterance,expected", THE_FOURTEEN_MISSES_AT_5FF4348)
def test_the_paraphrases_that_were_declined_at_5ff4348_now_route(utterance, expected):
    result = parse(utterance)
    assert result.understood, f"{utterance!r} still declines: {result.reason}"
    assert result.name == expected


def test_the_two_gated_ones_still_have_to_pass_the_gate():
    """Routing them is the point. Running them without a ruling never was."""
    for utterance in ("fire up chrome", "grab a screenshot"):
        result = parse(utterance)
        assert result.requires_approval, f"{utterance!r} stopped being approval gated"


def test_the_phrase_the_speaker_opened_with_wins():
    """Anchored beats incidental, and this test exists because it had to.

    A negative control on 2026-09-10 replaced `anchored or incidental` with
    `anchored + incidental`, restoring the 5ff4348 longest-wins rule, and every
    other test in this file still passed. The effect misroutes it used to cause
    are now held shut by a separate rule (an incidental hit may not claim an
    EFFECT intent at all), so nothing was left watching this one.

    What it still decides is which capture lane an utterance lands in, and that
    is worth pinning: a person who opens with "remember" gets a capture every
    time, rather than having the destination depend on which later phrase in
    their sentence happened to be the longest.
    """
    for utterance in (
        "remember to add a task to verify the hash",
        "note that we should start a project called X",
        "remember a new episode idea about the shadow",
    ):
        result = parse(utterance)
        assert result.name == "capture", (
            f"{utterance!r} routed to {result.name}; a phrase found later in the "
            "sentence beat the one the speaker opened with"
        )


def test_the_load_bearing_half_is_that_an_incidental_hit_cannot_be_an_effect():
    """Stated as a property of the data rather than of one utterance.

    This is the rule that closed the three gated effect misroutes measured at
    5ff4348, so it gets its own check rather than sharing one.
    """
    for text in (
        "the launch went well on Friday",
        "her message was pretty blunt",
        "the search for a new editor is on",
        "I want to text Karrie later this week",
        "put the youtube link in the doc",
    ):
        result = parse(text)
        assert not (result.understood and result.is_effect), (
            f"{text!r} reached the effect intent {result.name} from mid sentence"
        )


# -- the rules that had no test behind them ----------------------------------
#
# Added 2026-09-10 by the parser lane critic. Each of the six blocks below was
# found by mutating the real source and watching the whole suite stay green:
# the rule was doing real work and nothing was watching it, which is worse than
# no rule because the rule gets credited. Every one of these was re-driven
# against the same mutation afterwards and went red.


def test_a_mid_utterance_hit_must_land_on_both_word_boundaries():
    """Mutation: replace `_contains_whole_phrase` with a plain `in`.

    Measured 2026-09-10: the whole suite stayed green, because the separate rule
    that an incidental hit may never claim an EFFECT intent had taken over the
    cases the boundary check was written for. It still decides the capture
    lanes, where a substring match reaches straight past the speaker's meaning:
    "recapture this moment on film" contains "capture this".
    """
    for text in (
        "recapture this moment on film",
        "the recaptured footage looks better",
    ):
        result = parse(text)
        assert not result.understood, (
            f"{text!r} routed to {result.name}; a trigger matched inside a longer "
            "word, which is the 'relaunch' bug in a different lane"
        )


def test_a_one_word_trigger_may_not_claim_an_utterance_it_does_not_open():
    """Mutation: MIN_WORDS_FOR_MID_UTTERANCE_MATCH 2 -> 1. Suite stayed green.

    The constant carries its reasoning in a comment and nothing was checking it.
    "remember" is canon for `capture` and one word, so at a threshold of one it
    claims any sentence that happens to contain the verb.
    """
    for text in (
        "I will remember to call her",
        "you should remember that",
    ):
        result = parse(text)
        assert not result.understood, (
            f"{text!r} routed to {result.name}; a one word trigger claimed a "
            "sentence the speaker did not open with it"
        )


def test_a_mid_utterance_hit_must_belong_to_a_payload_taking_intent():
    """Mutation: drop `intent.takes_payload` from the incidental branch. Green.

    An intent that takes no payload has nowhere to put the rest of the sentence,
    so a phrase found in the middle of one is the speaker talking about the
    thing rather than asking for it.
    """
    for text in (
        "the project status is fine as of this morning",
        "the untriaged captures pile grew again",
    ):
        result = parse(text)
        assert not result.understood, (
            f"{text!r} routed to {result.name}; a non payload intent claimed a "
            "phrase from the middle of a sentence"
        )


# The three checks below are the suggestion quality rules, driven through
# `parse` rather than by calling the helper. `test_a_suggestion_must_share_a_word
# _that_carries_meaning` calls `shares_meaning` directly, which passes even when
# `parse` has stopped consulting it: measured 2026-09-10, forcing
# `shares_meaning` to return True left all 143 tests green while
# "what about the render" started drawing "did you mean get time" at 0.69.


def test_the_content_word_rule_is_wired_into_parse():
    """The exact utterances the rule was written for, through the real router."""
    for text in ("what about the render", "i dunno what i want"):
        result = parse(text)
        assert not result.understood
        assert result.suggestion is None, (
            f"{text!r} drew the suggestion {result.suggestion_name} at "
            f"{result.suggestion_score}, sharing no word that carries meaning"
        )


def test_the_suggestion_band_is_wired_into_parse():
    """Mutation: SUGGESTION_MARGIN 0.15 -> 0.90. Suite stayed green.

    "a receipt somewhere" scores 0.63 against `log_thread`, whose floor is 0.84.
    That is a long way under, and offering it invites a person to say a phrase
    they did not mean.
    """
    result = parse("a receipt somewhere")
    assert not result.understood
    assert result.suggestion is None, (
        f"a candidate {result.suggestion_score} below its own floor was offered "
        f"as {result.suggestion_name}"
    )


def test_the_absolute_suggestion_minimum_is_dormant_and_says_so():
    """SUGGESTION_MIN_SCORE cannot decide anything against the floors as they are.

    Measured 2026-09-10: lowering it from 0.55 to 0.0 changed no test and no
    parse output. The reason is arithmetic rather than luck. The lowest floor in
    the table is 0.72, so the lowest band floor is 0.72 minus a 0.15 margin,
    which is 0.57, and that is already above 0.55. The margin decides every
    case and the absolute minimum decides none.

    A first attempt at this guard drove an utterance through `parse` and passed
    for the wrong reason, which is exactly the vacuous guard this block exists
    to stop, so it was replaced with the arithmetic. It goes red if the minimum
    is raised into the live range or a floor drops far enough to let it through,
    either of which makes it the rule that decides and earns it a driven test.
    """
    band_floors = [
        intent.min_score - commands.SUGGESTION_MARGIN for intent in commands.ALL_INTENTS
    ]
    assert commands.SUGGESTION_MIN_SCORE <= min(band_floors), (
        f"SUGGESTION_MIN_SCORE {commands.SUGGESTION_MIN_SCORE} now binds ahead of "
        f"the margin for at least one intent (lowest band floor {min(band_floors):.2f}). "
        "Drive a case through parse and pin it; the margin no longer decides alone."
    )


# ---------------------------------------------------------------------------
# Added 2026-09-10 by the parent, after an adversary measured that widening the
# trigger vocabulary widened the one lane the floors never defended.
# ---------------------------------------------------------------------------


def test_prose_that_opens_with_an_effect_trigger_does_not_raise_a_card():
    """The regression this lane caused, and the rule that closes it.

    An anchored prefix hit takes a flat 0.95 and never consults the intent's
    floor. Widening 91 triggers to 299 widened exactly that. Measured before the
    fix: of 299 triggers followed by neutral prose, 197 routed, 49 to an EFFECT
    and 24 to an approval gated one, and every one of the utterances below
    DECLINED at 5ff4348 and then began raising a durable card.

    The gate held throughout, so nothing ever executed. The harm is a stream of
    approval cards nobody asked for, which is how a gate stops being read.
    """
    was_declining_at_5ff4348 = [
        "restart the machine learning job",
        "turn off the computer in the studio",
        "fire up the grill on Saturday",
        "reboot the machine that runs the encoder",
        "reboot the system prompt for the agent",
        "restart the machine learning pipeline tomorrow",
        "boot up sequence for the rig takes ten minutes",
        "shut the machine down before you leave",
        "refresh the dashboard numbers we discussed are wrong",
        "take a screenshot approach to this problem",
    ]
    leaked = []
    for utterance in was_declining_at_5ff4348:
        command = parse(utterance)
        if command.intent is not None and command.intent.kind is Kind.EFFECT:
            leaked.append(f"{utterance!r} -> {command.name}")
    assert leaked == [], (
        "prose reached an effect intent through the anchored prefix branch:\n"
        + "\n".join(leaked)
    )


def test_a_real_command_to_every_effect_intent_still_routes():
    """The other half, or the rule above is just a way of understanding less.

    The fix was chosen over two alternatives BY MEASUREMENT against this corpus.
    Making an anchored effect clear its own floor closes the leaks and breaks
    'search for the grid spec', because a query dilutes the score far below
    search_web's 0.78. A flat payload word cap closes them and breaks 'send a
    message to Marcus about the render'. Declaring the bound per intent closes
    all ten leaks and breaks none of these.
    """
    real = [
        ("send a message to Karrie", "send_message"),
        ("send a message to Marcus about the render", "send_message"),
        ("search for the grid spec", "search_web"),
        ("look up the pgvector docs", "search_web"),
        ("search for the best microphone for voiceover work", "search_web"),
        ("play on youtube the new trailer", "play_youtube"),
        ("put on youtube some lofi", "play_youtube"),
        ("open chrome", "open_app"),
        ("fire up chrome", "open_app"),
        ("open calculator", "open_app"),
        ("take a screenshot", "take_screenshot"),
        ("shut down the computer", "shutdown"),
        ("restart the computer", "restart"),
        ("reboot the computer", "restart"),
        ("refresh my dashboard", "refresh_dashboard"),
        ("refresh the brain map", "refresh_brain_map"),
        ("power off the computer", "shutdown"),
    ]
    broken = []
    for utterance, expected in real:
        command = parse(utterance)
        if not command.understood or command.name != expected:
            got = command.name if command.understood else "DECLINED"
            broken.append(f"{utterance!r} wanted {expected}, got {got}")
    assert broken == [], (
        "the anchored effect rule refused a real command:\n" + "\n".join(broken)
    )


def test_an_effect_intent_with_no_payload_accepts_no_remainder():
    """The rule itself, stated directly rather than only through its corpus.

    An effect intent that takes no payload has nowhere to put a remainder, so a
    request for it is the trigger and nothing else. This is what makes the rule
    safe to apply without consulting a score: it cannot refuse a real command,
    because a real command to such an intent has no remainder by construction.
    """
    for intent in commands.ALL_INTENTS:
        if intent.kind is not Kind.EFFECT or intent.takes_payload:
            continue
        for phrase in intent.triggers:
            alone = parse(phrase)
            assert alone.name == intent.name, (
                f"{phrase!r} alone no longer reaches {intent.name}; the rule is "
                "refusing a bare trigger, which is the one thing it must never do"
            )
            trailed = parse(f"{phrase} and then some unrelated prose about Friday")
            assert trailed.intent is None or trailed.intent.kind is not Kind.EFFECT, (
                f"{phrase!r} with a prose tail still reached the effect "
                f"{trailed.name}; {intent.name} takes no payload, so the tail is "
                "unexplained and cannot be part of the request"
            )


def test_a_bounded_payload_intent_refuses_a_payload_longer_than_it_declares():
    """max_payload_words is load bearing, not decoration.

    open_app is the only intent that declares one today. Its real payload is an
    application name: measured at 0, 1, 0 and 0 words over real commands, against
    4 for 'the grill on Saturday' and 7 for 'sequence for the rig takes ten
    minutes'. send_message deliberately declares none, because 'Marcus about the
    render' is a legitimate 4 word payload, and a single global cap that fits
    both is the bug this field exists to avoid.
    """
    bounded = [i for i in commands.ALL_INTENTS if i.max_payload_words is not None]
    assert bounded, (
        "no intent declares max_payload_words any more, so the bound is dead and "
        "an approval gated payload intent will take a whole sentence again"
    )
    for intent in bounded:
        assert intent.kind is Kind.EFFECT and intent.takes_payload, (
            f"{intent.name} declares a payload bound and is not a payload taking "
            "effect, where the bound is the only thing consulted"
        )
        long_tail = " ".join(["word"] * (intent.max_payload_words + 3))
        command = parse(f"{intent.phrases[0]} {long_tail}")
        assert command.intent is None or command.intent.name != intent.name, (
            f"{intent.name} accepted a payload of "
            f"{intent.max_payload_words + 3} words against a declared bound of "
            f"{intent.max_payload_words}"
        )
