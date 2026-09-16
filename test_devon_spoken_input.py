"""The command parser, driven with speech shaped input rather than typed strings.

WHY THIS FILE EXISTS

`services/devon/commands.py` was rebuilt from a voice assistant and carries
`strip_wake_word` and `_strip_fillers`, which only make sense for speech. It had
never been given any. On 2026-09-16, the day DEVON's ears were priced, a
gauntlet crossed every working intent with the lead-ins and trailers a person
actually says: 10,176 phrasings, of which 30.2 percent were declined.

The pattern was sharp rather than diffuse. "um" and "uh" were already in
`LEADING_FILLERS` and came through clean; nothing else in that family was there.
Hedges declined 59.5 percent of the time, self corrections 59.0, discourse
markers 41.0. Widening the vocabulary took the whole corpus to 3.6 percent, and
not one confidence floor moved, which is the same answer the 2026-09-10 change
reached from the paraphrase direction.

The residual 3.6 percent is deliberate and is pinned below. It is trailing
words on EFFECT intents, whose floors sit at a mean of 0.853 against 0.784 for
everything else. "Refresh my dashboard right now" is declined because the extra
words dilute the match under a floor that exists so a partial token match can
never reach `shutdown`. Loosening that is a ruling for Tee, not a repair, and
this file fails if somebody makes it quietly.
"""

from __future__ import annotations

import itertools

import pytest

from services.devon.commands import (
    ALL_INTENTS,
    LEADING_FILLERS,
    TRAILING_FILLERS,
    Kind,
    normalize,
    parse,
)

#: Lead-ins the 2026-09-16 gauntlet found declining, with the decline rate it
#: measured before the vocabulary was widened. Each one must now be understood.
THE_OFFENDERS = (
    ("actually no", 0.760),
    ("essentially", 0.760),
    ("obviously", 0.698),
    ("yo", 0.667),
    ("actually", 0.667),
    ("basically", 0.667),
    ("honestly", 0.667),
    ("literally", 0.667),
    ("you know", 0.667),
    ("hold on", 0.661),
    ("kind of", 0.661),
    ("no wait", 0.661),
    ("right so", 0.661),
    ("sort of", 0.661),
    ("and then", 0.604),
    ("anyway", 0.531),
    ("i mean", 0.505),
    ("maybe", 0.469),
    ("sorry", 0.464),
    ("wait", 0.401),
    ("well", 0.401),
    ("like", 0.396),
    ("hmm", 0.271),
    ("uhh", 0.271),
    ("umm", 0.271),
    ("ah", 0.172),
    ("er", 0.172),
)

#: A spoken phrasing of a capture, chosen because `log_thread` is the one the
#: live ElevenLabs probe used on 2026-09-16.
SPOKEN = "log this thread"


def _working_intents():
    """Intents whose own canon phrase parses, which is what the gauntlet measured."""
    return [i for i in ALL_INTENTS if i.phrases and parse(i.phrases[0]).understood]


@pytest.mark.parametrize("filler,was_declining", THE_OFFENDERS)
def test_a_lead_in_the_gauntlet_found_is_now_understood(filler: str, was_declining: float) -> None:
    said = f"Devon, {filler}, {SPOKEN}."
    result = parse(said)
    assert result.understood, (
        f"{said!r} is declined. The 2026-09-16 gauntlet measured {filler!r} "
        f"declining {was_declining:.1%} of the corpus, and widening "
        f"LEADING_FILLERS fixed it. If this fails, the vocabulary shrank."
    )
    assert result.name == "log_thread", f"{said!r} resolved to {result.name}"


def test_no_filler_eats_a_canon_phrase_or_alias() -> None:
    """The guard that keeps the vocabulary honest.

    `LEADING_FILLERS` already excludes "now" and "today" because they would
    delete the canon phrases "time now" and "weather today". Every entry added
    on 2026-09-16 was checked this way first, against all 299 canon phrases and
    aliases. This is that check, kept, so the next addition cannot skip it.
    """
    damaged = []
    for intent in ALL_INTENTS:
        for text in tuple(intent.phrases) + tuple(intent.aliases):
            result = parse(text)
            if not result.understood or result.name != intent.name:
                got = result.name if result.understood else "unknown"
                damaged.append(f"{text!r} is canon for {intent.name} and parses as {got}")
    assert not damaged, "a filler is eating canon:\n  " + "\n  ".join(damaged)


def _first_and_last_words_of_canon():
    """Every word that opens or closes a canon phrase or alias."""
    firsts, lasts = {}, {}
    for intent in ALL_INTENTS:
        for text in tuple(intent.phrases) + tuple(intent.aliases):
            words = text.lower().replace("\u2019", "").replace("'", "").split()
            if not words:
                continue
            firsts.setdefault(words[0], []).append((text, intent.name))
            lasts.setdefault(words[-1], []).append((text, intent.name))
    return firsts, lasts


def test_no_filler_is_the_first_or_last_word_of_a_canon_phrase() -> None:
    """The structural guard, and the only one that can see this failure.

    A behavioural check cannot. When a filler collapses a canon phrase, the
    phrase and its own trigger normalise in lockstep, so the phrase still
    resolves to its own intent and nothing looks wrong. The damage is only
    visible from outside, as a shorter string that now matches.

    Measured on 2026-09-16 while writing this file. "look" was a candidate
    filler and is the first word of the canon phrase "look up", so with it
    stripped a bare "up" matched `search_web` at 1.0. "see" is the first word
    of "see you", so a bare "you" matched `stop` at 1.0. Both were withdrawn.
    `LEADING_FILLERS` was already obeying this rule for "now" and "today"; this
    states it.
    """
    firsts, lasts = _first_and_last_words_of_canon()

    bad_lead = [(f, firsts[f]) for f in LEADING_FILLERS if f in firsts]
    bad_tail = [(f, lasts[f]) for f in TRAILING_FILLERS if f in lasts]

    assert not bad_lead, "a leading filler opens a canon phrase:\n  " + "\n  ".join(
        f"{f!r} opens {texts[0][0]!r} ({texts[0][1]})" for f, texts in bad_lead
    )
    assert not bad_tail, "a trailing filler closes a canon phrase:\n  " + "\n  ".join(
        f"{f!r} closes {texts[0][0]!r} ({texts[0][1]})" for f, texts in bad_tail
    )


def test_that_structural_guard_can_actually_fail() -> None:
    """Anti vacuity. The module's own comment names the case: "now" is kept out
    of the trailing list because `get_time` carries the canon phrase "time now".
    Both words must be the kind the guard rejects."""
    firsts, lasts = _first_and_last_words_of_canon()
    assert "time" in firsts, "'time' no longer opens a canon phrase; the guard lost its teeth"
    assert "now" in lasts, "'now' no longer closes a canon phrase; the guard lost its teeth"
    assert "time" not in LEADING_FILLERS and "now" not in TRAILING_FILLERS, (
        "the two words the module's own comment excludes are now in the vocabulary"
    )


def test_the_vocabulary_still_peels_what_it_was_added_for() -> None:
    swallowed = normalize("you know log this thread")
    assert swallowed == "log this thread", (
        f"the new vocabulary should peel 'you know' and leave the command, got {swallowed!r}"
    )


def test_the_confidence_floors_did_not_move() -> None:
    """The whole 2026-09-16 change was vocabulary. No floor may ride along.

    Effect intents sit higher than everything else on purpose, because a
    partial token match to a destructive intent is not consent. If a later
    session widens speech support by lowering a floor instead, this fails.
    """
    pinned = {
        "open_app": 0.86,
        "play_youtube": 0.80,
        "refresh_brain_map": 0.84,
        "refresh_dashboard": 0.84,
        "restart": 0.92,
        "search_web": 0.78,
        "send_message": 0.88,
        "shutdown": 0.92,
        "take_screenshot": 0.84,
    }
    live = {i.name: i.min_score for i in ALL_INTENTS if i.kind is Kind.EFFECT}
    assert live == pytest.approx(pinned), (
        "an effect intent's floor moved, or the set of effect intents changed. "
        "The 2026-09-16 speech work touched vocabulary only and must stay that "
        "way. If a floor genuinely needs to move, that is Tee's ruling and this "
        "dict is where you record it.\n"
        f"  pinned: {sorted(pinned.items())}\n"
        f"  live:   {sorted(live.items())}"
    )

    effect = list(live.values())
    other = [i.min_score for i in ALL_INTENTS if i.kind is not Kind.EFFECT]
    assert sum(effect) / len(effect) > sum(other) / len(other), (
        "effect intents no longer sit above everything else on average"
    )


def test_a_trailing_phrase_still_declines_an_effect_intent() -> None:
    """The deliberate residual, pinned so loosening it is a decision.

    This reads like a bug and is not. The gauntlet's remaining 3.6 percent is
    entirely trailing words on effect intents. The same dilution that declines
    this is what stops a loose match reaching `shutdown`.
    """
    declined = parse("Devon, refresh my dashboard right now")
    assert not declined.understood, (
        "'refresh my dashboard right now' is now accepted. That may be correct, "
        "but it is Tee's ruling: the floor that declines it is the floor that "
        "protects shutdown and restart. Change this test deliberately."
    )
    assert parse("Devon, refresh my dashboard").understood, (
        "the bare form must still work, or this is a different failure"
    )


def test_the_spoken_corpus_declines_only_the_effect_trailers() -> None:
    """The gauntlet itself, reduced enough to run in CI.

    Every working intent crossed with one lead-in from each family the 2026-09-16
    run measured. Anything declined must be an effect intent with a trailer, and
    nothing else.
    """
    leadins = ("", "Devon, ", "Hey Devon, ", "um, ", "you know, ", "basically, ",
               "no wait, ", "can you ", "Yo Devon, ")
    trailers = ("", " please", " for me", " thanks")

    declined = []
    for intent in _working_intents():
        for lead, trail in itertools.product(leadins, trailers):
            said = f"{lead}{intent.phrases[0]}{trail}"
            if not parse(said).understood:
                declined.append((intent.name, intent.kind, said))

    unexpected = [d for d in declined if d[1] is not Kind.EFFECT]
    assert not unexpected, (
        "non effect intents are declining spoken input:\n  "
        + "\n  ".join(f"{name} :: {said!r}" for name, _, said in unexpected[:10])
    )
