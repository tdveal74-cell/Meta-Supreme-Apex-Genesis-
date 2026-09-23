"""
The show canon, lifted out of the node and into rules that know whether they
bend.

Upstream: node `Build Script Prompt` in workflow `TQO FINAL V5`
(`qEkGOUsNyVaRAmm6` on the VPS instance), read from the live n8n public API on
2026-09-17 at workflow `updatedAt` 2026-09-16T14:02:48.875Z, and mirrored
verbatim into `n8n/tqo-v5/build_script_prompt.js`. Every rule below is derived
from that mirror, and `test_devon_tqo_canon.py` fails if a rule's text stops
appearing in it. That test is the reason this file can be trusted as a copy
rather than a paraphrase.

WHAT WAS ACTUALLY THERE, MEASURED RATHER THAN QUOTED

The teardown that prompted this work said the canon was roughly four thousand
words. It is not, and the number matters because it was the whole cost argument.
Measured from the mirror on 2026-09-17, after the dash fix below: the TQO block
is 805 words and 4,831 characters, the NCO block is 543 words and 3,558
characters. Before that fix they were 805 and 4,822, and 550 and 3,543. The teardown is
dated 14 August and the workflow has moved since, so treat its figure as stale
rather than wrong at the time; either way this file counts from the artifact.
Re-measured on 2026-09-23, after the episode promises ruling put a Learning
Objective, a 3 to 5 step checklist and a one question close into the TQO block:
973 words and 5,790 characters. The NCO block did not change.

Two more of its claims did not survive contact. There is no `Write Script
(Claude)` node: the writer is `Write Script (Cerebras)` and the prompt is built
in `Build Script Prompt`, which emits an Anthropic shaped body that
`Token Budget: Script` converts. And the canon is not a single undifferentiated
block: it already branches on show, and the taglines were already lifted into
`Show Context: Script` as data, which the node's own first comment calls the
identity board. Part of the job the teardown asks for was already done.

WHAT IS GENUINELY MISSING, AND IS WHY THIS FILE EXISTS

No exception layer. Every line in both blocks reads as unconditional, including
the ones that plainly are not, so a model handed a topic the rule does not fit
either obeys it stupidly or breaks it silently.

No separation of the rules that may never bend from the rules that are craft.
The dash ban and the owned presenter sit in the same undifferentiated prose as
the hook formulas and the b-roll count.

No way to diff a change. Until the mirror landed beside this file, a change to
what writes every episode left no trace in any repository.

THE LIVE CONTRADICTION THIS SPLIT FOUND, AND WHAT WAS DONE ABOUT IT

The NCO branch instructed the model to emit `NCO Forge `, a banned mark, and the
tagline, as "this exact line", in the description of every episode. Tee's first
hard rule bans that mark studio wide with no exceptions, and the QC gate in the
same workflow caps the voice dimension at 3 for any occurrence and requires it
in the findings. An NCO episode that followed its own script prompt exactly was
built to be marked down by its own quality gate.

Seventeen banned marks were in that node, across sixteen lines. Tee ruled on a
card on 2026-09-17 to fix all of them, and the live node was edited the same
day: every one restructured into sentences rather than given a substitute mark,
which is what hard rule 1 asks for. The node was read back byte identical to the
mirror afterwards, exactly one node of 240 changed, connections untouched and
the workflow still active.

Whether the mandated mark ever reached a published description was never
established, and the check that looked was close to vacuous: the `nco_content`
data table holds 25 rows and not one of them has a description written, so there
was nothing there to check. Recorded as unproven rather than clean.

THE LINE

This module holds the canon and assembles it. It does not write to n8n, and
nothing here changes what the live lane sends. Wiring the assembly in front of
the model call changes what the audience receives and is Tee's to authorize,
behind the blind comparison the teardown specifies.
"""

from __future__ import annotations

import pathlib
from typing import Dict, Tuple

from services.devon.rule_ledger import (
    Bend,
    Rule,
    RuleClass,
    RuleLedger,
)

SOURCE = {
    "upstream": "n8n node 'Build Script Prompt' in TQO FINAL V5",
    "workflow_id": "qEkGOUsNyVaRAmm6",
    "workflow_updated_at": "2026-09-16T14:02:48.875Z",
    "mirror": "n8n/tqo-v5/build_script_prompt.js",
    "read": "2026-09-17",
}

#: The mirrored node, which is the artifact every rule below is checked against.
MIRROR = pathlib.Path(__file__).resolve().parents[2] / "n8n" / "tqo-v5" / "build_script_prompt.js"

#: Measured from the mirror on 2026-09-17, so the assembly floor is a number
#: somebody counted rather than a default somebody liked. `check_assembly`
#: takes no default for exactly this reason.
MEASURED_WORDS: Dict[str, int] = {"tqo": 973, "nco": 543}
MEASURED_CHARS: Dict[str, int] = {"tqo": 5790, "nco": 3558}

#: Built from code points rather than written out, so this file needs no
#: exemption marker and no formatter can quietly rewrite the literal back.
BANNED_MARKS: Tuple[str, ...] = tuple(chr(point) for point in (0x2014, 0x2013))


def banned_marks(text: str) -> Tuple[str, ...]:
    """Every line of `text` carrying a mark hard rule 1 bans.

    Compliance grade, so it is a function rather than a note. Pointed at the
    mirrored NCO branch it returns the contradiction described above.
    """
    return tuple(
        line.strip()
        for line in text.splitlines()
        if any(mark in line for mark in BANNED_MARKS)
    )


# ---------------------------------------------------------------------------
# Compliance. These do not bend, they carry no scope, and they are in every
# assembly by construction. Each one is Tee's standing rule or a platform
# obligation, not craft.
# ---------------------------------------------------------------------------

COMPLIANCE: Tuple[Rule, ...] = (
    Rule(
        id="compliance.no-banned-dashes",
        text=(
            "Never use an em dash or an en dash, anywhere, in any field. "
            "Restructure the sentence rather than swapping the punctuation."
        ),
        rule_class=RuleClass.COMPLIANCE,
        source="Tee hard rule 1, studio wide; QC gate caps voice at 3 on any occurrence",
    ),
    Rule(
        id="compliance.owned-presenter",
        text=(
            "Terrance Veal presents every episode himself, in his own likeness and "
            "his own cloned voice. Never write a line that only works as voiceover "
            "over stock footage of a stranger."
        ),
        rule_class=RuleClass.COMPLIANCE,
        source="build_script_prompt.js TQO branch; channel identity, never rented",
    ),
    Rule(
        id="compliance.no-stolen-valor",
        text=(
            "The narrator speaks from NCO experience in general terms and never "
            "invents named operations he claims to have been on."
        ),
        rule_class=RuleClass.COMPLIANCE,
        source="build_script_prompt.js NCO branch, no stolen valor specifics",
    ),
    Rule(
        id="compliance.sourced-claims",
        text=(
            "Never present an external statistic, study or survey as fact without "
            "naming its source. Never write experts say, studies show or reports "
            "suggest. Never fabricate a date or misattribute a quote."
        ),
        rule_class=RuleClass.COMPLIANCE,
        source="build_qc_prompt.js hard blockers; QC holds the episode regardless of score",
    ),
    Rule(
        id="compliance.crisis-support-resource",
        text=(
            "Self harm, suicide, a mental health crisis or leaving service is never "
            "covered without a support resource named on screen and in the "
            "description."
        ),
        rule_class=RuleClass.COMPLIANCE,
        source="build_qc_prompt.js hard blockers",
    ),
    Rule(
        id="compliance.no-named-person-negative",
        text="Never name a real identifiable person in a negative light.",
        rule_class=RuleClass.COMPLIANCE,
        source="build_qc_prompt.js hard blockers",
    ),
    Rule(
        id="compliance.no-combat-violence-footage",
        text=(
            "Military b-roll is archival and training footage only. Never a phrase "
            "that would fetch or fabricate realistic combat violence."
        ),
        rule_class=RuleClass.COMPLIANCE,
        source="build_script_prompt.js NCO branch, STRICT clause on broll",
    ),
)


# ---------------------------------------------------------------------------
# Craft. These bend, they declare a scope, and an exception is written down
# only once a real case has landed. Most carry none yet, which the ledger
# reports rather than hides.
# ---------------------------------------------------------------------------

CRAFT: Tuple[Rule, ...] = (
    Rule(
        id="tqo.hook.first-fifteen-seconds",
        text=(
            "The first 10-15 seconds decide whether this video is watched or "
            "skipped. Open on the single most specific, concrete claim, number or "
            "tension in the whole topic. Never a warm-up, never in this video, "
            "never a dictionary definition."
        ),
        rule_class=RuleClass.CRAFT,
        scope=("tqo",),
        confidence=0.95,
        source="build_script_prompt.js TQO branch, THE HOOK IS EVERYTHING",
    ),
    Rule(
        id="tqo.voice.calm-register",
        text=(
            "Calm, precise, anti-hype, proof-driven, quietly confident. Never fear-"
            "monger, never use hype or clickbait. Calm is the weapon: a quiet, "
            "exact, slightly contrarian first line outperforms hype for this "
            "audience."
        ),
        rule_class=RuleClass.CRAFT,
        scope=("tqo",),
        confidence=0.95,
        source="build_script_prompt.js TQO branch, Voice",
    ),
    Rule(
        id="tqo.length.1200-2000",
        text=(
            "A long-form spoken narration of 1200-2000 words, target 1600, hard "
            "floor 1200. Depth, not padding."
        ),
        rule_class=RuleClass.CRAFT,
        scope=("tqo", "nco"),
        confidence=0.9,
        bends=(
            Bend(
                condition="script below the floor",
                instead=(
                    "The lane expands rather than refuses: Script: Needs Expansion "
                    "sends it to Expand Script, and Script: Still Short sends it to "
                    "Expand Script 2. The floor is enforced by retry, not by a hard "
                    "stop, so do not treat 1200 as a reason to pad."
                ),
                evidence=(
                    "nodes Script: Needs Expansion?, Expand Script (Cerebras), "
                    "Script: Still Short?, Expand Script 2 (Cerebras) in TQO FINAL V5, "
                    "read 2026-09-17"
                ),
            ),
        ),
        source="build_script_prompt.js both branches, item 2",
    ),
    Rule(
        id="tqo.broll.cutaways-not-people",
        text=(
            "8 to 12 short visual search phrases, 2-4 words each, one per major "
            "section, in order. These are cutaways over a presenter. Name the thing "
            "being illustrated: a concrete object, screen, document or place, never "
            "a person standing in for him. No generic office workers, no anonymous "
            "professionals at desks, no handshakes."
        ),
        rule_class=RuleClass.CRAFT,
        scope=("tqo",),
        confidence=0.9,
        source="build_script_prompt.js TQO branch, item 4",
    ),
    Rule(
        id="tqo.close.one-quiet-cta",
        text=(
            "The last 5 seconds carry ONE quiet call: a question worth answering in "
            "the comments, and nothing after it. Never a like or subscribe ask, "
            "and never a pointer to an audit, a download or a link. The brand "
            "does not beg. Ruled by Tee 2026-09-23, when the free audit pointer "
            "was dropped."
        ),
        rule_class=RuleClass.CRAFT,
        scope=("tqo",),
        confidence=0.9,
        source="build_script_prompt.js TQO branch, CLOSE beat",
    ),
    Rule(
        id="tqo.format.pick-one",
        text=(
            "Pick the ONE best-fit proven format and shape the whole script around "
            "it: LISTICLE, NEGATIVE or STOP, TUTORIAL, CONTRARIAN or REFRAME, "
            "RECEIPT or STORY."
        ),
        rule_class=RuleClass.CRAFT,
        scope=("tqo", "nco"),
        confidence=0.85,
        source="build_script_prompt.js both branches",
    ),
    Rule(
        id="tqo.keyword.primary",
        text=(
            "Choose a PRIMARY KEYWORD of 2-4 words that this viewer would actually "
            "type into YouTube search. Weave it into the title and the first "
            "sentence of the description. Never keyword-stuff."
        ),
        rule_class=RuleClass.CRAFT,
        scope=("tqo", "nco"),
        confidence=0.85,
        source="build_script_prompt.js both branches",
    ),
    Rule(
        id="tqo.frame.outcomes-not-topics",
        text=(
            "Frame outcomes, not topics. Every section connects to what the viewer "
            "gains or avoids, the transformation rather than the subject."
        ),
        rule_class=RuleClass.CRAFT,
        scope=("tqo",),
        confidence=0.85,
        source="build_script_prompt.js TQO branch",
    ),
    Rule(
        id="nco.voice.seasoned-nco",
        text=(
            "A seasoned NCO talking to their people. Direct, practical, respectful "
            "of service. No ego, no theory for theory's sake, no fear-mongering, no "
            "hype. Concrete examples over abstract principles, always."
        ),
        rule_class=RuleClass.CRAFT,
        scope=("nco",),
        confidence=0.95,
        source="build_script_prompt.js NCO branch, Voice",
    ),
    Rule(
        id="nco.pillars.pick-one",
        text=(
            "Pick the one pillar this topic belongs to and stay in it: Military "
            "Foundation, Transition Blueprint, Financial Freedom, Physical and "
            "Mental Edge, Life After Service."
        ),
        rule_class=RuleClass.CRAFT,
        scope=("nco",),
        confidence=0.9,
        source="build_script_prompt.js NCO branch, THE FIVE PILLARS",
    ),
    Rule(
        id="nco.benefits.verify-do-not-guess",
        text=(
            "Be precise about VA, TSP and GI Bill facts. If unsure, say verify with "
            "your transition counselor rather than guessing."
        ),
        rule_class=RuleClass.CRAFT,
        scope=("nco",),
        confidence=1.0,
        source="build_script_prompt.js NCO branch, pillar 3",
        bends=(
            Bend(
                condition="mental health adjacent",
                instead=(
                    "Stay compassionate and point to professional support where it "
                    "belongs, rather than sending the viewer to a transition "
                    "counselor for something clinical."
                ),
                evidence="build_script_prompt.js NCO branch, pillar 4, read 2026-09-17",
            ),
        ),
    ),
    Rule(
        id="nco.never-pain-as-coping",
        text=(
            "Never present discomfort or pain as a coping technique."
        ),
        rule_class=RuleClass.CRAFT,
        scope=("nco",),
        confidence=1.0,
        source="build_script_prompt.js NCO branch, pillar 4",
    ),
)


def ledger() -> RuleLedger:
    """The whole canon, both shows, compliance and craft together."""
    return RuleLedger(rules=COMPLIANCE + CRAFT)


def mirror_text() -> str:
    """The shipped node source, read from the mirror beside this repository."""
    return MIRROR.read_text(encoding="utf-8")
