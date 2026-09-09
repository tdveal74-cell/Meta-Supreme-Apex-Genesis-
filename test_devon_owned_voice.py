"""
The owned voice, checked on every push.

WHY THIS FILE EXISTS, AND WHY IT IS PYTHON

Tee's standing rule is voice and identity owned, never rented, and it carries no
exception path. On 2026-09-09 he opened /devon and DEVON answered in a stock
female browser voice. The fix banned window.speechSynthesis across the served
surfaces, and a fresh critic then found the ban itself unreachable:

    apps/web/scripts/control-check.ts holds the ban.
    It runs in exactly one workflow, .github/workflows/web-ci.yml.
    That workflow is path filtered to apps/web, packages/ui and three root files.
    deploy/soul/console.html matches none of them.

So a pull request that restored the rented voice in the served console, and
nowhere else, kept the two console copies byte identical, passed all 97 console
tests, never triggered web-ci at all, and would have landed with every job
green. The exact finding the previous critic raised was reintroducible without
CI noticing, because the guard lived on the wrong side of a path filter.

Adding those roots to web-ci's filter is done and is the narrow fix. This file
is the load bearing one: ci.yml has no path filter, so a compliance rule that
must never lapse is checked on every push to every path rather than only when
somebody happens to touch the web workspace. A rule with an exception path is
not the rule Tee stated.

WHY IT GLOBS

The TypeScript ban began as four hardcoded paths. The same critic added a fifth
file, components/devon/DevonVoiceFallback.tsx, carrying the exact implementation
this arc removed, and the check reported ok at 26 checks passed. A fixed list
cannot guard the file that does not exist yet. So this globs the estate and
asserts a FLOOR on what the glob found, the pattern test_devon_integrity.py
already uses, because a glob that silently matches nothing passes vacuously and
reads identically to a glob that matched everything.
"""

from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).parent

# Every authored web source. .next and node_modules are generated; a vendored
# dependency reaching for speech synthesis is not this estate speaking as DEVON.
#
# apps/web/scripts is excluded because that is where the ban LIVES: control-check
# names all three marks in its own regex, so scanning it fails on the guard
# rather than on a surface. Nothing under scripts reaches a browser; they are
# node processes CI runs. That exclusion is not left on trust either, see
# test_the_typescript_ban_still_names_all_three_marks below, which turns the hole
# into a positive assertion.
WEB_FILES = sorted(
    path
    for pattern in ("**/*.ts", "**/*.tsx")
    for path in (ROOT / "apps" / "web").glob(pattern)
    if ".next" not in path.parts
    and "node_modules" not in path.parts
    and "scripts" not in path.parts
)

# The served consoles. app.main picks the newest non SUPERSEDED_ asset and
# test_deploy_soul.py holds it byte identical to deploy/soul/console.html. The
# SUPERSEDED_ copies are dated archives that nothing serves, so they keep the
# history they were written with.
SERVED_HTML = sorted(
    path
    for directory in (ROOT / "deploy" / "soul", ROOT / "docs" / "devon" / "assets")
    for path in directory.glob("*.html")
    if not path.name.startswith("SUPERSEDED_")
)

VOICE_SURFACES = WEB_FILES + SERVED_HTML

# WHERE THIS BAN DELIBERATELY STOPS.
#
# The same critic restored a fully working rented voice past the marks below with
# window['speech' + 'Synthesis'] and this.synth['get' + 'Voices'](), and it
# passed. That is true and it is not being closed, because the fix is either
# banning computed member access across the estate, which breaks correct code, or
# an arms race against string concatenation, which the next critic wins again with
# a different split.
#
# The judgement: nobody writes that by accident. This guard exists to stop a
# regression, a copy paste, or a convenient shortcut, and all three of those name
# the API. Deliberate obfuscation to defeat a compliance check is a different
# problem than a source check solves, and pretending otherwise would make this
# file look stronger than it is. Graded low and recorded rather than papered over.

# A rented voice is whatever that machine happens to have installed, chosen by a
# vendor, different on every device. These three marks are how a browser offers
# one; getVoices is the tell for picking one off the machine without naming the
# API directly.
RENTED = re.compile(r"speechSynthesis|SpeechSynthesisUtterance|\.getVoices\s*\(")

BLOCK_COMMENT = re.compile(r"/\*.*?\*/|<!--.*?-->", re.DOTALL)


def _authored_code(text: str) -> str:
    """The file with comments removed, so its own history cannot satisfy a ban."""
    without_blocks = BLOCK_COMMENT.sub("", text)
    return "\n".join(
        line for line in without_blocks.splitlines() if not line.strip().startswith("//")
    )


def test_the_glob_reaches_the_estate_and_not_a_lane():
    # The floor. Counted from the estate on 2026-09-09, not from a lane and not
    # from a doc: 55 web sources (36 components, 9 app, 8 lib, 2 root config) and
    # three served consoles. These assert the glob still WORKS, so a moved
    # directory fails loudly here instead of turning the ban into a no-op.
    assert len(WEB_FILES) >= 50, f"the web glob found {len(WEB_FILES)} files; the glob is wrong"
    assert len(SERVED_HTML) >= 3, f"the console glob found {len(SERVED_HTML)} files; the glob is wrong"

    names = {p.name for p in SERVED_HTML}
    assert "console.html" in names, "deploy/soul/console.html is served and the glob did not reach it"
    assert any(
        n.startswith("SYS_OPS_devon-console_v") for n in names
    ), "the served console asset is not in the glob"

    # And the surface the breach was found on is specifically in scope.
    assert any(p.name == "DevonChat.tsx" for p in WEB_FILES)


@pytest.mark.parametrize("path", VOICE_SURFACES, ids=lambda p: p.name)
def test_no_surface_speaks_as_devon_in_a_rented_voice(path: pathlib.Path):
    found = RENTED.findall(_authored_code(path.read_text(encoding="utf-8")))
    assert not found, (
        f"{path.relative_to(ROOT)} reaches for the browser's speech synthesis "
        f"({', '.join(sorted(set(found)))}). Voice and identity are owned, never "
        "rented, and that rule has no exception path. DEVON's voice is the "
        "presence service's Cartesia clone, reached through POST /tts."
    )


def test_the_owned_lane_is_the_one_that_is_wired():
    """The ban alone would be satisfied by a surface that says nothing at all."""
    chat = (ROOT / "apps" / "web" / "components" / "devon" / "DevonChat.tsx").read_text(
        encoding="utf-8"
    )
    assert "${PRESENCE_BASE}/tts" in chat, (
        "DevonChat no longer streams from the presence service, so banning the "
        "rented voice has left the chat silent rather than owned"
    )


def test_the_typescript_ban_still_names_all_three_marks():
    """
    apps/web/scripts is the one tree this file does not scan, so what it holds is
    asserted rather than assumed. control-check runs in web-ci and reads the same
    estate through its own glob; if somebody weakens it there, this fails here,
    on every push, with no path filter in the way.
    """
    guard = (ROOT / "apps" / "web" / "scripts" / "control-check.ts").read_text(
        encoding="utf-8"
    )
    for mark in ("speechSynthesis", "SpeechSynthesisUtterance", "getVoices"):
        assert mark in guard, (
            f"control-check.ts no longer names {mark}, so the web-ci copy of the "
            "owned voice ban has been weakened"
        )
    assert "voiceSurfaces()" in guard, (
        "control-check.ts no longer globs its voice surfaces, so it is back to a "
        "fixed list that the next new file walks straight past"
    )
