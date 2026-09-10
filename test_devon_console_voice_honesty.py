"""The console's voice controls may not offer a state the Voice object refuses.

WHY THIS FILE EXISTS

The rented browser voice came out of deploy/soul/console.html on 2026-09-09 and
was replaced by a stub that refuses: `supported: false`, and a `speak()` that
calls the caller's onEnd and says nothing. Three controls over it were left
wired to the voice that had gone.

The worst was the mute button. Clicking it flipped the stub's muted flag and
relabelled itself to say speech was on. The stub does not read that flag, so the
page announced a mode it cannot enter. DEVON's standing rule is that he never
claims something ran when it did not, and a button is a claim.

Beside it, a rate slider wrote a property the stub does not declare, and an
`onVoicesReady` function built a voice picker from a voices list and a chosen
voice, two more properties it does not have. That one was already dead: the
speechSynthesis handler that called it went out with the rented voice.

WHAT IS ACTUALLY GUARDED

The invariant is a coupling, not a spelling: every property the page touches on
Voice has to be one the Voice object declares. That is what catches the whole
family. A restored picker reading a voices list goes red, because declaring the
property means writing a real one.

The checks are deliberately absence shaped where they can be. An absence
assertion has no decoy that satisfies it while the bug returns, which is why the
comments above and in the console avoid dotted property syntax and the on label
they describe. A presence assertion can be satisfied by a neighbour; an absence
assertion cannot.

Both copies are checked. test_deploy_soul.py already holds them byte identical,
so this is belt and braces against a change landing in only one.

No database, and no network.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Set

import pytest

ROOT = Path(__file__).resolve().parent

COPIES = {
    "deploy/soul/console.html": ROOT / "deploy" / "soul" / "console.html",
    "docs/devon/assets/SYS_OPS_devon-console_v10_2026-09-01.html": (
        ROOT
        / "docs"
        / "devon"
        / "assets"
        / "SYS_OPS_devon-console_v10_2026-09-01.html"
    ),
}

#: The stub's own keys. Named here so a scraper that silently degrades to an
#: empty or garbage set fails instead of certifying everything.
_KEY_FLOOR = {"supported", "muted", "reason", "init", "speak", "stop"}

_KEY_LINE = re.compile(r"\s*([A-Za-z_$][\w$]*)\s*[:(]")
_VOICE_REF = re.compile(r"\bVoice\.([A-Za-z_$][\w$]*)")
#: An assignment, not a comparison: `Voice.muted =` but not `Voice.muted ===`.
_VOICE_WRITE = re.compile(r"\bVoice\.[A-Za-z_$][\w$]*\s*(?:\+|-|\|\||&&|\?\?)?=(?!=)")


def _literal_span(text: str) -> tuple[int, int]:
    """Character span of the `const Voice = { ... }` object literal.

    Brace counted from the declaration. The literal's own string values carry no
    braces today, and if one ever does this scraper breaks loudly through the
    key floor assertion rather than quietly returning the wrong span.
    """
    start = text.find("const Voice = {")
    assert start != -1, (
        "the Voice object is no longer declared as `const Voice = {`, so this "
        "file cannot tell which properties the page is allowed to touch"
    )
    depth = 0
    index = start
    for line in text[start:].splitlines(keepends=True):
        depth += line.count("{") - line.count("}")
        index += len(line)
        if depth <= 0:
            return start, index
    raise AssertionError("the Voice object literal never closes")


def _declared_keys(text: str) -> Set[str]:
    start, end = _literal_span(text)
    keys: Set[str] = set()
    depth = 0
    for line in text[start:end].splitlines():
        if depth == 1:
            match = _KEY_LINE.match(line)
            if match:
                keys.add(match.group(1))
        depth += line.count("{") - line.count("}")
    return keys


@pytest.mark.parametrize("name", sorted(COPIES))
def test_the_key_scraper_still_reads_the_voice_object(name: str) -> None:
    """Anti-vacuity. Every coupling below is a subset test against these keys."""
    keys = _declared_keys(COPIES[name].read_text(encoding="utf-8"))
    missing = _KEY_FLOOR - keys
    assert not missing, (
        f"{name}: the Voice property scraper did not find {sorted(missing)}. "
        "Either the stub dropped a property the page still needs, or the scraper "
        "has stopped reading the object and the subset tests below would pass on "
        "an empty set"
    )
    assert len(keys) < 25, (
        f"{name}: the scraper found {len(keys)} keys, which is more than an "
        "object literal this size can have. It is reading past the closing brace"
    )


@pytest.mark.parametrize("name", sorted(COPIES))
def test_every_voice_property_the_page_touches_is_one_it_declares(name: str) -> None:
    text = COPIES[name].read_text(encoding="utf-8")
    keys = _declared_keys(text)
    referenced = set(_VOICE_REF.findall(text))
    assert referenced, (
        f"{name}: nothing references Voice at all. The console speaks through it, "
        "so either the page stopped using it or this scan is broken"
    )
    undeclared = referenced - keys
    assert not undeclared, (
        f"{name}: the page reads {sorted(undeclared)} on Voice and the object "
        "does not declare them. That is how the voice picker and the rate slider "
        "survived the voice they drove: a control reading undefined does nothing "
        "and says nothing, and looks live either way. Declare a real property or "
        "take the control out"
    )


@pytest.mark.parametrize("name", sorted(COPIES))
def test_nothing_outside_the_voice_object_reassigns_its_state(name: str) -> None:
    text = COPIES[name].read_text(encoding="utf-8")
    start, end = _literal_span(text)
    outside = text[:start] + text[end:]
    writes = _VOICE_WRITE.findall(outside)
    assert not writes, (
        f"{name}: something outside the Voice object assigns to it ({writes}). "
        "The stub's state is fixed because the capability is absent, so a write "
        "is a control claiming it changed a mode the page cannot enter. That was "
        "the mute button"
    )


@pytest.mark.parametrize("name", sorted(COPIES))
def test_no_control_offers_a_speech_on_state(name: str) -> None:
    text = COPIES[name].read_text(encoding="utf-8")
    assert "SPEECH ON" not in text, (
        f"{name}: a control labels itself SPEECH ON. Voice.speak returns without "
        "speaking, so any on label is the console claiming something ran when it "
        "did not. If the owned voice on the presence service is wired up here, "
        "the label comes back with a speak() that speaks"
    )


@pytest.mark.parametrize("name", sorted(COPIES))
def test_the_dead_voice_controls_ship_inert_and_carry_the_reason(name: str) -> None:
    """A control the page cannot honour has to be unusable, not merely useless."""
    text = COPIES[name].read_text(encoding="utf-8")
    for element, ident in (("button", "muteBtn"), ("input", "rate")):
        tag = re.search(rf"<{element}[^>]*id=\"{ident}\"[^>]*>", text)
        assert tag is not None, f"{name}: no <{element}> carries id={ident}"
        assert re.search(r"\bdisabled\b", tag.group(0)), (
            f"{name}: #{ident} ships enabled while voice out refuses. A live "
            f"looking control over a capability the page does not have invites a "
            f"click that changes nothing: {tag.group(0)}"
        )

    # The reason is the stub's own, rendered rather than restated, so the page
    # and the object cannot drift into two different explanations.
    assert "Voice.reason" in text, (
        f"{name}: the page never shows Voice.reason. Disabling the controls "
        "silently tells Tee the page is broken; the stub already carries why it "
        "refuses and the page has to say it"
    )
