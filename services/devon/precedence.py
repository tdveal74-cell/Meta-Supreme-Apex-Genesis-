"""
DEVON precedence and conflict doctrine, executable.

Source of truth on Drive: SYS_SPEC_precedence-doctrine_v2_2026-08-06
(Drive id 1EaFyPPAXIX5j75oJ06tvvUuq4Qd73jB4), read 2026-08-22.

Two rules, and the second one is the important one:

    1. For versions of the same artifact, the most recent wins.
    2. For contradictions, nothing wins. Flag and let a human rule.

Most systems implement only the first, which is how they quietly destroy things.
The 2026-08-04 cleanup is the proof: the instruction was "keep newest of each
name", and buried in the same line was a note that a 28 July draft was the
evidence record. Blind recency would have deleted the evidence. A 47 byte stub
was also in that list, ready to supersede a real document purely by being newer.

Recency is a good tiebreaker between drafts. Recency is a poor arbiter of truth.

MOST RECENT MEANS CLOSEST TO TODAY, ruled 2026-08-06, not numerically largest.
A file stamped 2027-01-14 is not ahead of one stamped yesterday, a file stamped
2027-01-14 is wrong. Ranking is by absolute distance from today, and a future
dated candidate loses outright to any candidate that is not future dated.

A NOTE ON THE LADDER, recorded honestly rather than smoothed over.
The doctrine's "establishing the date" ladder puts a version marker at step 2,
between the filename date and a date stated inside the document. A version
marker is not a date. It yields an ordering, not a point in time. This module
therefore treats the ladder as a precedence signal ladder and says so, rather
than pretending v3 resolves to a calendar date. Behaviour matches the doctrine's
intent on every well formed input; the divergence is only in what the code calls
the thing. Flagged here so a later reader does not think the code drifted.

THE LINE
Automation may decide which draft is current. Only Tee decides which claim is
true.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_cls
from enum import Enum
from typing import List, Optional, Sequence, Tuple

from services.devon.naming import parse_filename

SOURCE = {
    "drive_id": "1EaFyPPAXIX5j75oJ06tvvUuq4Qd73jB4",
    "title": "SYS_SPEC_precedence-doctrine_v2_2026-08-06",
    "ruled": "2026-08-06",
    "read": "2026-08-22",
}

# Where refused resolutions are recorded, per the doctrine.
CONFLICTS_TABLE = {"table_id": "tblbenoy1QF9KAftn", "base_id": "app28z7XnKzjfTXwc"}

# A candidate under about a quarter the size of what it would replace is refused,
# unless the loser is itself trivially small, where the ratio carries no meaning.
SIZE_RATIO_FLOOR = 0.25
TRIVIALLY_SMALL_BYTES = 256


class Signal(str, Enum):
    """How a candidate's precedence was established, in ladder order."""

    FILENAME_DATE = "filename date"
    VERSION_MARKER = "version marker in filename"
    DOCUMENT_DATE = "date stated inside the document"
    MODIFIED_TIME = "file modified time"
    CREATED_TIME = "file created time"
    NONE = "no signal"


class Outcome(str, Enum):
    """What the resolver concluded."""

    SUPERSEDE = "supersede"
    CONFLICT = "conflict"
    REFUSED = "refused"


@dataclass
class Candidate:
    """One file competing to be the current version of an artifact."""

    name: str
    drive_id: Optional[str] = None
    size_bytes: Optional[int] = None
    document_date: Optional[str] = None
    modified_time: Optional[str] = None
    created_time: Optional[str] = None
    parent_path: str = ""
    is_canon: bool = False

    # Filled by the resolver.
    established_date: Optional[date_cls] = None
    signal: Signal = Signal.NONE
    version: Optional[int] = None
    protected: bool = False
    future_dated: bool = False
    notes: List[str] = field(default_factory=list)

    @property
    def in_archive(self) -> bool:
        """Archive is supposed to be old. Being old is its job."""
        path = self.parent_path.lower()
        return "4. archive" in path or path.startswith("archive")


@dataclass
class Ruling:
    """The resolver's answer, always carrying its reasoning."""

    outcome: Outcome
    winner: Optional[Candidate] = None
    losers: List[Candidate] = field(default_factory=list)
    signal: Signal = Signal.NONE
    reasons: List[str] = field(default_factory=list)
    refusal_codes: List[str] = field(default_factory=list)

    @property
    def auto_resolvable(self) -> bool:
        return self.outcome is Outcome.SUPERSEDE

    def conflict_row(self) -> dict:
        """The Airtable Conflicts payload for anything refused.

        The doctrine is explicit that the reason must be concrete. "Newer file is
        47 bytes against 11,204 bytes" is useful. "Possible issue" is not.
        """
        return {
            "table_id": CONFLICTS_TABLE["table_id"],
            "base_id": CONFLICTS_TABLE["base_id"],
            "status": "Open",
            "candidates": [
                {"name": c.name, "drive_id": c.drive_id, "size_bytes": c.size_bytes}
                for c in ([self.winner] if self.winner else []) + self.losers
            ],
            "evidence": list(self.reasons),
            "refusal_codes": list(self.refusal_codes),
        }


def _parse_iso(value: Optional[str]) -> Optional[date_cls]:
    if not value:
        return None
    head = value.strip()[:10]
    try:
        return date_cls.fromisoformat(head)
    except ValueError:
        return None


def establish_precedence(candidate: Candidate, today: date_cls) -> Candidate:
    """Walk the ladder and stop at the first signal that yields a real date.

    A future dated signal is not a date. Log it and step down, never use it.
    This is also the anti gaming rule: dating a file forward so it sorts to the
    top does not work, and the attempt shows up in the conflicts table.
    """
    parsed = parse_filename(candidate.name)
    candidate.version = parsed.version
    candidate.protected = parsed.is_protected or candidate.in_archive

    ladder: Sequence[Tuple[Signal, Optional[date_cls]]] = (
        (Signal.FILENAME_DATE, _parse_iso(parsed.date)),
        (Signal.DOCUMENT_DATE, _parse_iso(candidate.document_date)),
        (Signal.MODIFIED_TIME, _parse_iso(candidate.modified_time)),
        (Signal.CREATED_TIME, _parse_iso(candidate.created_time)),
    )

    for signal, value in ladder:
        if value is None:
            continue
        if value > today:
            candidate.future_dated = True
            candidate.notes.append(f"Future dated: {signal.value} reads {value.isoformat()}")
            continue
        candidate.established_date = value
        candidate.signal = signal
        return candidate

    if candidate.version is not None:
        # Version marker orders without dating. Recorded as the signal so the
        # caller knows the confidence is different from a real date.
        candidate.signal = Signal.VERSION_MARKER
        candidate.notes.append("Ordered by version marker, no usable date found")
        return candidate

    candidate.signal = Signal.NONE
    candidate.notes.append("Ambiguous date: no signal yielded a usable date")
    return candidate


def _distance(candidate: Candidate, today: date_cls) -> int:
    if candidate.established_date is None:
        return 10**9
    return abs((today - candidate.established_date).days)


def resolve(
    candidates: Sequence[Candidate],
    today: Optional[date_cls] = None,
    disagrees_on_load_bearing: bool = False,
) -> Ruling:
    """Rank candidates for the same artifact and decide, or refuse.

    `disagrees_on_load_bearing` is supplied by the caller after reading the
    documents. No parser detects a contradiction about a name, a number, or a
    ruling, and pretending otherwise would let a real conflict auto resolve.
    """
    today = today or date_cls.today()
    if not candidates:
        return Ruling(outcome=Outcome.REFUSED, reasons=["no candidates"], refusal_codes=["empty"])

    resolved = [establish_precedence(c, today) for c in candidates]

    if len(resolved) == 1:
        only = resolved[0]
        return Ruling(
            outcome=Outcome.SUPERSEDE,
            winner=only,
            losers=[],
            signal=only.signal,
            reasons=["single candidate, nothing to resolve"],
        )

    refusal_codes: List[str] = []
    reasons: List[str] = []

    if any(c.is_canon for c in resolved):
        refusal_codes.append("canon")
        reasons.append(
            "A candidate is canon. Canon collisions route to studio-canon-intake "
            "and are never resolved unilaterally."
        )

    ambiguous = [c for c in resolved if c.established_date is None]
    if ambiguous:
        refusal_codes.append("ambiguous-date")
        reasons.append(
            "Precedence cannot be computed for: "
            + ", ".join(c.name for c in ambiguous)
            + ". Do not fall back to alphabetical, file size, or read order."
        )

    future = [c for c in resolved if c.future_dated]
    if future:
        refusal_codes.append("future-dated")
        reasons.append("Future dated candidates: " + ", ".join(c.name for c in future))

    ranked = sorted(resolved, key=lambda c: (_distance(c, today), -(c.version or 0), c.name))
    winner = ranked[0]
    losers = ranked[1:]

    protected_losers = [c for c in losers if c.protected]
    if protected_losers:
        refusal_codes.append("protected-superseded")
        reasons.append(
            "Protected or archived candidate would be superseded: "
            + ", ".join(c.name for c in protected_losers)
            + ". Protected files are the record of what was true at a moment. Keep both."
        )

    if winner.size_bytes is not None:
        for loser in losers:
            if loser.size_bytes is None or loser.size_bytes <= TRIVIALLY_SMALL_BYTES:
                continue
            if winner.size_bytes < loser.size_bytes * SIZE_RATIO_FLOOR:
                refusal_codes.append("winner-drastically-smaller")
                reasons.append(
                    f"Winner is {winner.size_bytes} bytes against {loser.size_bytes} bytes. "
                    "A stub, a failed write, or a truncated export looks exactly like a "
                    "legitimate new version to a date comparison."
                )
                break

    if disagrees_on_load_bearing:
        refusal_codes.append("load-bearing-disagreement")
        reasons.append(
            "The candidates disagree on something load bearing: a name, a number, "
            "a ruling, or a decision. Recency does not settle a contradiction."
        )

    if refusal_codes:
        outcome = Outcome.CONFLICT if "load-bearing-disagreement" in refusal_codes else Outcome.REFUSED
        return Ruling(
            outcome=outcome,
            winner=winner,
            losers=losers,
            signal=winner.signal,
            reasons=reasons,
            refusal_codes=refusal_codes,
        )

    reasons.append(
        f"Newest by {winner.signal.value}: {winner.name}"
        + (f" ({winner.established_date.isoformat()})" if winner.established_date else "")
    )
    return Ruling(
        outcome=Outcome.SUPERSEDE,
        winner=winner,
        losers=losers,
        signal=winner.signal,
        reasons=reasons,
    )


def live_tree(trees: dict[str, Sequence[Candidate]], today: Optional[date_cls] = None) -> Optional[str]:
    """Pick the live folder tree among competing trees, ruled 2026-08-05.

    Judge by recency of content, not by which tree looks better organised, has
    more files, or was created first. Whichever tree holds the file closest to
    today is where work is actually happening. Future dated files are ignored
    entirely, so one file misdated 2027 cannot make a dead tree look alive.

    Tree recency is a tiebreaker applied after version marker and file date. A
    genuinely newer file in a stale tree still beats an older file in the live
    tree.
    """
    today = today or date_cls.today()
    best_name: Optional[str] = None
    best_distance = 10**9
    for name, members in trees.items():
        for candidate in members:
            resolved = establish_precedence(candidate, today)
            if resolved.established_date is None or resolved.protected:
                continue
            distance = _distance(resolved, today)
            if distance < best_distance:
                best_distance = distance
                best_name = name
    return best_name
