"""The lesson registry: the only place a learning lesson can come from.

Ruled by Tee on 2026-10-08, Phase 0 of the grouping build specified in
docs/devon/SYS_SPEC_learning-lane-grouping_v1_2026-10-07.md. A completed job
on its own can never become a lesson: the Build 12 gate needs two
independent sources, and a lesson is a reusable rule, not a description of
one job. So a lesson exists only when Tee declares it here, with the claim
in his own words, and the feeder may then group human verified jobs declared
for it.

WHAT AN ENTRY IS

lesson_key   a slug, the lesson's name everywhere downstream
claim        40 to 600 characters, one reusable operational rule. Tee writes
             it, or adopts a session's draft verbatim, and nothing downstream
             may change it. The 600 cap keeps it far under the conflict
             search's 2000 character limit.
area         one of the nine Areas, by its canonical label
scope        project, system or global, as in the reference gate
min_sources  2 to 5. The bar never drops below two.
status       active or retired. Only an active lesson can be grouped.
evidence_ids optional ULIDs of past jobs Tee lists himself as showing it
declared_on  the date he declared it
ruling_ref   where he ruled it

A claim reaches this module only through a pull request whose merge Tee
authorizes, and reaches the n8n table only on his ruling. None is declared
yet, so LESSONS is empty and the lane forms no group.

WHAT IS NOT HERE

The seed script, the data table and its id, the --check step in
registry-check.yml and the vault.py entries for the two new tables. They
arrive in Phase 3, when the tables are created; until then REGISTRY_TABLES is
empty on purpose, because an id written before the table exists would be a
record of something that is not there. Nothing in this module performs a network call or an effect, and
it imports the standard library and the Area canon only, because the daily
registry check will run it with no packages installed once Phase 3 wires
that step.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from services.devon.areas import canonical_labels

SPEC = "docs/devon/SYS_SPEC_learning-lane-grouping_v1_2026-10-07.md"

CLAIM_MIN = 40
CLAIM_MAX = 600
MIN_SOURCES_FLOOR = 2
MIN_SOURCES_CEILING = 5
SCOPES: Tuple[str, ...] = ("project", "system", "global")
STATUSES: Tuple[str, ...] = ("active", "retired")

KEY_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
KEY_MAX = 60
ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

# Shapes that mean a secret was pasted where a lesson belongs: the credential
# formats this estate actually holds, by their own prefixes. The gate scans a
# POST with the same shapes (n8n/devon/learning-gate/candidate_former.js), and
# test_devon_lesson_registry.py pins the two lists equal.
#
# The spec also named a generic rule, any hex or base64 run of 32 characters
# or more. It was measured on 2026-10-08 and left out: it refuses a Drive id
# such as 1DlobTD8LWKFfZzYNgaIr_7yRO-Rtj5RB and a 40 character commit hash,
# both ordinary in job summaries, and on the single job path a false
# REJECT_SECRET would sit in the feed log for good while protecting nothing,
# because that path writes nothing either way.
#
# The token shape opens on a lookbehind rather than a word boundary. With
# the boundary, text made of "eyJ-" repeated gave the engine a fresh start
# at every hyphen and the scan went quadratic: 100 KB held the gate's
# preflight for seven seconds, measured 2026-10-08. The lookbehind allows one
# start per run, and a token after a space, a colon or the start of the text
# still matches.
#
# Three shapes refuse some ordinary prose, measured by the same critic, and
# are kept on purpose: "x-devon-key: accepted", "bearer authentication"
# followed by a long word, and a receipt's TOKEN line, which is a capture
# token by shape and an identifier by design. On the single job path a false
# REJECT_SECRET changes a feed log label and nothing else, because that path
# writes nothing either way, and a lesson carries no free text at all.
#
# No sample secret lives in this file: the deployed copy is scanned for
# secret shapes by test_deploy_soul.py.
SECRET_SHAPES: Tuple[Tuple[str, str], ...] = (
    ("a Pinecone key", r"pcsk_[A-Za-z0-9_-]{20,}"),
    ("a console token", r"dst_[0-9a-f]{32,}"),
    ("a capture token", r"dcp_[A-Za-z0-9_]{16,}"),
    ("an Anthropic key", r"\bsk-ant-[A-Za-z0-9_-]{20,}"),
    ("an OpenAI style key", r"\bsk-[A-Za-z0-9_-]{20,}"),
    ("a Cerebras key", r"\bcsk-[A-Za-z0-9]{20,}"),
    ("an AWS access key id", r"\bAKIA[0-9A-Z]{16}\b"),
    ("a private key block", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("a Slack token", r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    ("a GitHub token", r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    ("a Google API key", r"\bAIza[0-9A-Za-z_-]{30,}"),
    ("an Airtable token", r"\bpat[A-Za-z0-9]{14}\.[0-9a-f]{40,}"),
    ("a JSON web token", r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\."),
    ("a bearer credential", r"\b[Bb][Ee][Aa][Rr][Ee][Rr]\s+[A-Za-z0-9._~+/=-]{16,}"),
    ("an x-devon-key value", r"[Xx]-[Dd][Ee][Vv][Oo][Nn]-[Kk][Ee][Yy]\s*[:=]\s*\S{8,}"),
)
# Compiled ASCII, so \b and \d read as they do in the gate's JavaScript,
# which runs without the u flag. Without it, "café" followed by a key prefix
# is a boundary in the gate and not here.
_SECRET_RES = tuple((label, re.compile(pattern, re.ASCII)) for label, pattern in SECRET_SHAPES)


def likely_secret(text: str) -> Optional[str]:
    """The label of the first secret shape the text carries, or None."""
    for label, pattern in _SECRET_RES:
        if pattern.search(text or ""):
            return label
    return None


def norm_id(value: object) -> str:
    """ULIDs are case insensitive: trimmed and upper cased, or empty."""
    return value.strip().upper() if isinstance(value, str) else ""


@dataclass(frozen=True)
class Lesson:
    lesson_key: str
    claim: str
    area: str
    scope: str
    min_sources: int
    status: str
    declared_on: str
    ruling_ref: str
    evidence_ids: Tuple[str, ...] = ()

    @property
    def claim_sha(self) -> str:
        """Rewording the claim changes this, which is what unblocks a key."""
        return hashlib.sha256(self.claim.encode("utf-8")).hexdigest()

    def row(self) -> Dict[str, object]:
        """One flat record for the devon_lesson_registry data table."""
        return {
            "lesson_key": self.lesson_key,
            "claim": self.claim,
            "claim_sha": self.claim_sha,
            "area": self.area,
            "scope": self.scope,
            "min_sources": self.min_sources,
            "status": self.status,
            "evidence_ids": json.dumps([norm_id(i) for i in self.evidence_ids]),
            "declared_on": self.declared_on,
            "ruling_ref": self.ruling_ref,
        }


# Tee declares each lesson. None is declared yet.
LESSONS: Tuple[Lesson, ...] = ()

# Filled in Phase 3 when the data table is created and read back.
REGISTRY_TABLES: Dict[str, str] = {}


def _is_date(value: object) -> bool:
    """A real calendar date written YYYY-MM-DD in ASCII digits, nothing else."""
    if not isinstance(value, str) or not DATE_RE.fullmatch(value):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def problems(entry: Lesson) -> List[str]:
    """Every reason one entry may not be seeded. Empty means it may."""
    out: List[str] = []
    key = entry.lesson_key
    if not isinstance(key, str) or not KEY_RE.fullmatch(key) or len(key) > KEY_MAX:
        out.append(f"{key!r}: lesson_key must be a lower case slug of up to {KEY_MAX} characters")
    claim = entry.claim if isinstance(entry.claim, str) else ""
    if claim != claim.strip():
        out.append(f"{key}: claim carries leading or trailing whitespace")
    if not CLAIM_MIN <= len(claim) <= CLAIM_MAX:
        out.append(f"{key}: claim is {len(claim)} characters, outside {CLAIM_MIN} to {CLAIM_MAX}")
    if claim.splitlines() != ([claim] if claim else []):
        out.append(f"{key}: claim must be one line")
    found = likely_secret(claim)
    if found:
        out.append(f"{key}: claim carries something shaped like {found}")
    if entry.area not in canonical_labels():
        out.append(f"{key}: area {entry.area!r} is not one of {canonical_labels()}")
    if entry.scope not in SCOPES:
        out.append(f"{key}: scope {entry.scope!r} is not one of {list(SCOPES)}")
    if not isinstance(entry.min_sources, int) or isinstance(entry.min_sources, bool) or not (
        MIN_SOURCES_FLOOR <= entry.min_sources <= MIN_SOURCES_CEILING
    ):
        out.append(f"{key}: min_sources must be an integer from {MIN_SOURCES_FLOOR} to {MIN_SOURCES_CEILING}")
    if entry.status not in STATUSES:
        out.append(f"{key}: status {entry.status!r} is not one of {list(STATUSES)}")
    if not _is_date(entry.declared_on):
        out.append(f"{key}: declared_on must be a YYYY-MM-DD date")
    if not isinstance(entry.ruling_ref, str) or not entry.ruling_ref.strip():
        out.append(f"{key}: ruling_ref must name where Tee ruled it")
    ids = [norm_id(i) for i in entry.evidence_ids]
    for raw, nid in zip(entry.evidence_ids, ids, strict=True):
        if not ULID_RE.fullmatch(nid):
            out.append(f"{key}: evidence id {raw!r} is not a ULID")
    if len(set(ids)) != len(ids):
        out.append(f"{key}: evidence_ids repeats a job once letter case is ignored")
    return out


def registry_problems(entries: Sequence[Lesson] = LESSONS) -> List[str]:
    """Every reason the registry as a whole may not be seeded."""
    out: List[str] = []
    seen: Dict[str, int] = {}
    for entry in entries:
        out.extend(problems(entry))
        seen[entry.lesson_key] = seen.get(entry.lesson_key, 0) + 1
    out.extend(f"{key}: declared {count} times" for key, count in sorted(seen.items()) if count > 1)
    return out


def registry_rows(entries: Sequence[Lesson] = LESSONS) -> Tuple[Dict[str, object], ...]:
    return tuple(entry.row() for entry in entries)


# A numeric expression is read whole, joined by the marks that change what
# it says: "120-30%" is one expression and must appear as such, so the two
# numbers of "120 [dash] 30% above my last one" cannot be stitched into one
# that was never written. It is then looked for with digit boundaries, so
# 20 is not found inside 2026, nor 0.5 inside 0.55.
_NUMBER = re.compile(r"[0-9](?:[0-9.,%-]*[0-9])?%?")
# Double quotes in any of the usual forms, open and close matched by class
# rather than by kind, and single quotes only where they cannot be an
# apostrophe, so "Tee's" and "don't" are not read as quotations.
_QUOTED = re.compile(
    "[\"\u201c\u201d\u201e\u00ab]([^\"\u201c\u201d\u201e\u00ab\u00bb\n]+)[\"\u201c\u201d\u00bb]"
    "|(?<![A-Za-z0-9])['\u2018]([^'\u2018\u2019\n]+)['\u2019](?![A-Za-z0-9])"
)
_DOUBLE_MARKS = "\"\u201c\u201d\u201e\u00ab\u00bb"


def _holds_number(corpus: str, number: str) -> bool:
    pattern = r"(?<![0-9])(?<![0-9][.,])" + re.escape(number) + r"(?![0-9])(?![.,][0-9])"
    return re.search(pattern, corpus) is not None


def draft_claim_problems(claim: str, evidence_texts: Iterable[str]) -> List[str]:
    """Checks a claim a SESSION drafted, before it is put to Tee.

    Every numeric expression written in digits, read whole, and every quoted
    fragment must appear verbatim in the ledger text of the jobs the draft
    names: their intent_summary, their receipt summary or their verification
    evidence. That refuses the failure CLAUDE.md tabulates, where a dash
    rewrite turned "120 [dash] 30% above my last one" into "120-30%", a
    number nobody wrote. Numbers spelled in words, fractions written as one
    character and superscripts are not read. An opening double quote with no
    close is refused rather than skipped. Tee's own wording is his and is
    never run through this.
    """
    corpus = "\n".join(t for t in evidence_texts if isinstance(t, str))
    text = claim or ""
    out: List[str] = []
    for match in _NUMBER.finditer(text):
        if not _holds_number(corpus, match.group(0)):
            out.append(f"the number {match.group(0)!r} appears in no named job's ledger text")
    for match in _QUOTED.finditer(text):
        fragment = match.group(1) or match.group(2)
        if fragment not in corpus:
            out.append(f"the quoted words {fragment!r} appear in no named job's ledger text")
    if any(mark in _QUOTED.sub("", text) for mark in _DOUBLE_MARKS):
        out.append("the draft opens a quotation it never closes")
    return out
