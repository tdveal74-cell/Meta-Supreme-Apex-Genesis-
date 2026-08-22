"""
The eight DEVON filing laws, executable.

Source on Drive: SYS_SPEC_filing-laws-for-llms_v3_2026-08-22
(Drive id 1YxrdXHqlT5kkdzWey5qO_21KbVDQd9ID), read 2026-08-22.

    Read the newest file first. Write to the tree, never the root. Prove it with
    a read-back you validated. Never rule for Tee.

Every law is here because something broke without it, and each carries the
failure it prevents. The laws were written as prose and then broken by threads
that had read them, twice inside the document whose job was preventing exactly
that. Prose does not enforce. A function that refuses does.

This module holds no credentials and performs no network calls. It answers
questions about whether a write is permitted and whether a read actually read
something. The caller performs the effect.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_cls
from enum import Enum
from typing import Any, List, Mapping, Optional, Sequence, Tuple

from services.devon.naming import parse_filename

SOURCE = {
    "drive_id": "1YxrdXHqlT5kkdzWey5qO_21KbVDQd9ID",
    "title": "SYS_SPEC_filing-laws-for-llms_v3_2026-08-22",
    "read": "2026-08-22",
}

DRIVE_ROOT = "root"
VAULT_ROOT_ID = "18_ZF2pYi7BgW6KStvAHNMmcCZHVQFGMo"


@dataclass(frozen=True)
class FilingLaw:
    number: int
    title: str
    rule: str
    failure_prevented: str


LAWS: Tuple[FilingLaw, ...] = (
    FilingLaw(
        1,
        "Root holds the vault and nothing else.",
        "The only permitted item at Drive root is Devon 2nd Brain. Never write a "
        "new file to root. Never leave a file at root for now.",
        "160 items accumulated at root across two months, including a plaintext "
        "private SSH key.",
    ),
    FilingLaw(
        2,
        "Read the newest sibling before writing a new version.",
        "Before consolidating, superseding, or writing v-anything: list the folder, "
        "sort by date, read the newest one in full. It may already be the merge.",
        "Five documents forked in two days. The naming convention forked at 08:41 "
        "and 08:42, sixty seconds apart, in the document whose job is preventing forks.",
    ),
    FilingLaw(
        3,
        "A success response is a claim. A validated read-back is a receipt.",
        "Every move, rename, create or delete is confirmed by reading state back, "
        "and the read is validated before it is compared against.",
        "On 2026-08-22 a payload location assumption produced an empty read three "
        "times. One guard threw 'not v4' at a document that plainly was v4. The "
        "guard fired correctly for the wrong reason, and a guard right by accident "
        "will eventually be wrong by accident.",
    ),
    FilingLaw(
        4,
        "Exact duplicates die on sight. Distinct versions are Tee's ruling.",
        "Identical title and identical byte size and older timestamp: trash it. "
        "Anything else, including a 25 byte difference, is a distinct version. "
        "A model does not decide which draft of Tee's work survives.",
        "A keep-latest pass would have kept the largest decision log and deleted an "
        "addendum holding four rulings that existed nowhere else.",
    ),
    FilingLaw(
        5,
        "Filenames that carry warnings are canon. Obey them before any rule.",
        "Files carry instructions in their titles. These outrank any general "
        "heuristic including keep latest. Read every filename in a folder before "
        "acting on any file in it.",
        "A literal keep-latest pass would have deleted the only copy of four rulings.",
    ),
    FilingLaw(
        6,
        "Retire by moving and renaming, not by deleting.",
        "Superseded material goes to 05_RETIRED or 4. Archive with its status in "
        "the filename. The word CANONICAL never remains in the title of a document "
        "whose central claim was withdrawn. Deletion is final.",
        "A file trashed on 2026-08-22 did not surface in the user's trash view and "
        "returned entity-not-found. The connector cannot restore from trash.",
    ),
    FilingLaw(
        7,
        "Sweep to a dated holding folder. Never route in bulk blind.",
        "When a large pile needs clearing and its contents are not understood, move "
        "it whole into '0. Inbox / ROOT SWEEP YYYY-MM-DD' and stop. Nothing in a "
        "holding folder is canon until a human routes it.",
        "A holding folder that survives its own session becomes the mess it was "
        "built to fix.",
    ),
    FilingLaw(
        8,
        "Correct in place where the lane supports it. Batch and bump once where it does not.",
        "Corrections do not deserve a version. Substance does. In-place writing runs "
        "through the n8n lane. The Claude Drive connector cannot rewrite a file, so a "
        "thread without the lane batches corrections and bumps once.",
        "Six master directory versions in a single day, produced one correction at a "
        "time by a thread that could only create.",
    ),
)


def get_law(number: int) -> FilingLaw:
    for law in LAWS:
        if law.number == number:
            return law
    raise KeyError(f"No filing law numbered {number}")


class Verdict(str, Enum):
    ALLOW = "allow"
    REFUSE = "refuse"
    NEEDS_RULING = "needs-ruling"


@dataclass
class LawResult:
    """The answer from one law, always naming the law that produced it."""

    law: int
    verdict: Verdict
    message: str

    @property
    def allowed(self) -> bool:
        return self.verdict is Verdict.ALLOW


# ---------------------------------------------------------------------------
# Law 1
# ---------------------------------------------------------------------------


def law1_check_destination(parent_id: str) -> LawResult:
    """Refuse any write whose destination is Drive root."""
    if not parent_id or parent_id.strip().lower() == DRIVE_ROOT:
        return LawResult(
            1,
            Verdict.REFUSE,
            "Destination is Drive root. Root holds only Devon 2nd Brain "
            f"({VAULT_ROOT_ID}). Every file lives in a folder. A file at root has "
            "no Area, no owner and no retention rule, and it will still be there "
            "in six months.",
        )
    return LawResult(1, Verdict.ALLOW, f"Destination {parent_id} is inside the tree.")


# ---------------------------------------------------------------------------
# Law 2
# ---------------------------------------------------------------------------


@dataclass
class SiblingRead:
    """Evidence that the folder was listed and the newest sibling was read."""

    folder_listed: bool = False
    siblings_seen: Sequence[str] = field(default_factory=tuple)
    newest_sibling: Optional[str] = None
    newest_sibling_read: bool = False


def law2_require_sibling_read(
    writing_new_version: bool,
    evidence: Optional[SiblingRead] = None,
) -> LawResult:
    """Gate a new version behind proof the folder was listed and the newest read.

    Applies only when writing a new version of something. A first file in a new
    folder has no sibling to read, and gating that would be theatre.
    """
    if not writing_new_version:
        return LawResult(2, Verdict.ALLOW, "Not a new version, no sibling read required.")
    if evidence is None or not evidence.folder_listed:
        return LawResult(
            2,
            Verdict.REFUSE,
            "Folder was not listed. Before writing v-anything, list the folder. "
            "Five documents forked in two days because nobody did this.",
        )
    if evidence.newest_sibling and not evidence.newest_sibling_read:
        return LawResult(
            2,
            Verdict.REFUSE,
            f"Newest sibling '{evidence.newest_sibling}' was found but not read. "
            "It may already be the merge you are about to write again.",
        )
    return LawResult(2, Verdict.ALLOW, "Folder listed and newest sibling read.")


# ---------------------------------------------------------------------------
# Law 3
# ---------------------------------------------------------------------------

# A fetched body may arrive under any of these. Never assume one.
PAYLOAD_KEYS: Tuple[str, ...] = (
    "body",
    "data",
    "text",
    "content",
    "part",
    "fileContent",
    "file_content",
    "result",
    "value",
    "message",
)

MIN_PAYLOAD_LENGTH = 1


@dataclass
class ReadBack:
    """The result of validating a read before trusting it."""

    ok: bool
    value: Optional[str] = None
    location: Optional[str] = None
    reason: str = ""

    def require(self) -> str:
        """Return the payload or raise. Fail loudly on an empty read."""
        if not self.ok or self.value is None:
            raise ValueError(
                f"Read-back failed: {self.reason}. A read that returns nothing is "
                "not a read. Do not let it flow into a comparison, because every "
                "content check silently passes against an empty string."
            )
        return self.value


def law3_validate_readback(
    payload: Any,
    min_length: int = MIN_PAYLOAD_LENGTH,
    _path: str = "",
    _depth: int = 0,
) -> ReadBack:
    """Find the actual content in a tool response and prove it is not empty.

    Searches the documented payload keys first, then any other string, then
    recurses. Returns where it found the value so the caller can record the
    location rather than assume it next time.
    """
    if _depth > 6:
        return ReadBack(False, reason="payload nesting deeper than 6 levels")

    if isinstance(payload, str):
        if len(payload.strip()) >= min_length:
            return ReadBack(True, payload, _path or "<root>", "string payload")
        return ReadBack(False, reason=f"string at {_path or '<root>'} is empty")

    if isinstance(payload, Mapping):
        for key in PAYLOAD_KEYS:
            if key in payload:
                found = law3_validate_readback(
                    payload[key], min_length, f"{_path}.{key}" if _path else key, _depth + 1
                )
                if found.ok:
                    return found
        for key, value in payload.items():
            if key in PAYLOAD_KEYS:
                continue
            found = law3_validate_readback(
                value, min_length, f"{_path}.{key}" if _path else str(key), _depth + 1
            )
            if found.ok:
                return found
        return ReadBack(
            False,
            reason=f"no non-empty payload found in mapping at {_path or '<root>'} "
            f"(keys tried: {', '.join(PAYLOAD_KEYS)})",
        )

    if isinstance(payload, (list, tuple)):
        for index, item in enumerate(payload):
            found = law3_validate_readback(item, min_length, f"{_path}[{index}]", _depth + 1)
            if found.ok:
                return found
        return ReadBack(False, reason=f"no non-empty payload in sequence at {_path or '<root>'}")

    if payload is None:
        return ReadBack(False, reason=f"payload at {_path or '<root>'} is None")

    return ReadBack(False, reason=f"payload at {_path or '<root>'} is {type(payload).__name__}")


# ---------------------------------------------------------------------------
# Law 4
# ---------------------------------------------------------------------------


class DuplicateClass(str, Enum):
    EXACT_DUPLICATE = "exact-duplicate"
    DISTINCT_VERSION = "distinct-version"
    UNRELATED = "unrelated"


@dataclass
class FileFacts:
    name: str
    size_bytes: Optional[int] = None
    modified_time: Optional[str] = None
    drive_id: Optional[str] = None


def law4_classify(a: FileFacts, b: FileFacts) -> Tuple[DuplicateClass, LawResult]:
    """Decide whether two files are the same file twice or two real versions.

    Only identical title AND identical byte size AND an older timestamp permits
    an automatic trash. Everything else is Tee's ruling. Where a file carries an
    explicit version number, the version label governs, not the timestamp.
    """
    if a.name != b.name:
        return DuplicateClass.UNRELATED, LawResult(
            4, Verdict.ALLOW, "Different titles, not a duplicate pair."
        )

    version_a = parse_filename(a.name).version
    version_b = parse_filename(b.name).version
    if version_a is not None and version_b is not None and version_a != version_b:
        return DuplicateClass.DISTINCT_VERSION, LawResult(
            4,
            Verdict.NEEDS_RULING,
            f"Version labels differ (v{version_a} against v{version_b}). The version "
            "label governs, not the modified timestamp.",
        )

    if a.size_bytes is None or b.size_bytes is None:
        return DuplicateClass.DISTINCT_VERSION, LawResult(
            4,
            Verdict.NEEDS_RULING,
            "Byte size unknown for at least one candidate, so an exact duplicate "
            "cannot be proven. Measure before ruling.",
        )

    if a.size_bytes == b.size_bytes:
        older = None
        if a.modified_time and b.modified_time:
            older = a.name if a.modified_time < b.modified_time else b.name
        return DuplicateClass.EXACT_DUPLICATE, LawResult(
            4,
            Verdict.ALLOW,
            f"Identical title and identical size ({a.size_bytes} bytes). "
            + (f"Trash the older: {older}." if older else "Timestamps unknown, trash neither yet."),
        )

    return DuplicateClass.DISTINCT_VERSION, LawResult(
        4,
        Verdict.NEEDS_RULING,
        f"Sizes differ ({a.size_bytes} against {b.size_bytes} bytes). A 25 byte "
        "difference is still a distinct version. Preserve both, place them, and "
        "put it on a ruling card.",
    )


# ---------------------------------------------------------------------------
# Law 5
# ---------------------------------------------------------------------------


def law5_filename_warnings(names: Sequence[str]) -> List[Tuple[str, Tuple[str, ...]]]:
    """Surface every warning marker in a folder before anything acts on it.

    Read every filename in a folder before acting on any file in it. The return
    is deliberately a list rather than a boolean, because the caller must see
    which files carry which warning.
    """
    flagged: List[Tuple[str, Tuple[str, ...]]] = []
    for name in names:
        parsed = parse_filename(name)
        warnings = parsed.warnings_in_name
        if parsed.is_protected:
            warnings = warnings + ("PROTECTED",)
        if warnings:
            flagged.append((name, warnings))
    return flagged


# ---------------------------------------------------------------------------
# Law 6
# ---------------------------------------------------------------------------

RETIREMENT_DESTINATIONS = ("05_RETIRED", "4. Archive")


@dataclass
class Retirement:
    """The move and rename that retires a file. Never a deletion."""

    original_name: str
    new_name: str
    destination: str
    note: str


def law6_retire(
    name: str,
    destination: str = "4. Archive",
    reason: str = "superseded",
) -> Retirement:
    """Produce the rename and move that retires a file.

    Refuses to leave the word CANONICAL in the title of a document whose central
    claim was withdrawn.
    """
    from services.devon.naming import SUPERSEDED_PREFIX

    new_name = name
    if "CANONICAL" in new_name.upper():
        new_name = new_name.replace("CANONICAL", "WITHDRAWN").replace(
            "canonical", "withdrawn"
        )
    if not new_name.upper().startswith(SUPERSEDED_PREFIX):
        new_name = f"{SUPERSEDED_PREFIX}_{new_name}"

    return Retirement(
        original_name=name,
        new_name=new_name,
        destination=destination,
        note=(
            f"Retired as {reason}. Moved and renamed, never deleted. Deletion is "
            "final: the connector cannot restore from trash."
        ),
    )


def law6_refuse_deletion(name: str) -> LawResult:
    """Deletion is never the retirement mechanism."""
    return LawResult(
        6,
        Verdict.REFUSE,
        f"Refusing to delete '{name}'. Retire by moving and renaming. Treat every "
        "deletion as permanent at the moment you make it.",
    )


# ---------------------------------------------------------------------------
# Law 7
# ---------------------------------------------------------------------------


def law7_sweep_folder(on_date: Optional[date_cls] = None) -> str:
    """Name the dated holding folder a blind sweep must land in."""
    stamp = (on_date or date_cls.today()).isoformat()
    return f"0. Inbox / ROOT SWEEP {stamp}"


def law7_check_holding_folder(created_on: date_cls, today: Optional[date_cls] = None) -> LawResult:
    """A holding folder that survives its own session becomes the mess it fixed."""
    today = today or date_cls.today()
    if created_on < today:
        return LawResult(
            7,
            Verdict.REFUSE,
            f"Holding folder created {created_on.isoformat()} has outlived its "
            "session. Empty it and trash it. Nothing in a holding folder is canon "
            "until a human routes it.",
        )
    return LawResult(7, Verdict.ALLOW, "Holding folder created this session.")


# ---------------------------------------------------------------------------
# Law 8
# ---------------------------------------------------------------------------


class ChangeKind(str, Enum):
    CORRECTION = "correction"
    SUBSTANCE = "substance"


def law8_version_decision(
    change: ChangeKind,
    lane_supports_in_place: bool,
    pending_corrections: int = 0,
) -> LawResult:
    """Decide whether a change costs a version bump.

    In-place writing runs through the n8n lane, a PATCH to the Drive upload
    endpoint with the file id unchanged. The Claude Drive connector cannot do it:
    it can trash, rename, move and create, but it cannot rewrite. A thread
    without the lane must not bump per correction.
    """
    if change is ChangeKind.SUBSTANCE:
        return LawResult(8, Verdict.ALLOW, "Substance changed. Bump the integer once.")
    if lane_supports_in_place:
        return LawResult(
            8,
            Verdict.ALLOW,
            "Correction with the in-place lane available. Fix at the same file id, "
            "no bump.",
        )
    return LawResult(
        8,
        Verdict.REFUSE,
        f"Correction without the in-place lane. Do not bump. Batch this with the "
        f"{pending_corrections} other pending correction(s) and bump once. Bumping "
        "per correction is what produced six directory versions in a single day.",
    )


# ---------------------------------------------------------------------------
# Aggregate write check
# ---------------------------------------------------------------------------


@dataclass
class WriteRequest:
    """Everything a write to the vault must declare before it happens."""

    filename: str
    parent_id: str
    writing_new_version: bool = False
    sibling_evidence: Optional[SiblingRead] = None
    change: ChangeKind = ChangeKind.SUBSTANCE
    lane_supports_in_place: bool = False
    folder_contents: Sequence[str] = field(default_factory=tuple)


@dataclass
class WriteCheck:
    allowed: bool
    results: List[LawResult] = field(default_factory=list)
    naming_violations: List[str] = field(default_factory=list)
    folder_warnings: List[Tuple[str, Tuple[str, ...]]] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"Write {'permitted' if self.allowed else 'refused'}."]
        for result in self.results:
            if not result.allowed:
                lines.append(f"  Law {result.law}: {result.message}")
        for violation in self.naming_violations:
            lines.append(f"  Naming: {violation}")
        for name, warnings in self.folder_warnings:
            lines.append(f"  Warning in folder: {name} carries {', '.join(warnings)}")
        return "\n".join(lines)


def check_write(request: WriteRequest) -> WriteCheck:
    """Run every applicable law against a proposed write.

    This is the gate. It answers a question and performs no effect, so calling
    it is always safe and never partially applies anything.
    """
    results = [
        law1_check_destination(request.parent_id),
        law2_require_sibling_read(request.writing_new_version, request.sibling_evidence),
        law8_version_decision(request.change, request.lane_supports_in_place),
    ]

    parsed = parse_filename(request.filename)
    naming_violations = [str(v) for v in parsed.violations if v.severity == "error"]
    folder_warnings = law5_filename_warnings(request.folder_contents)

    allowed = all(r.allowed for r in results) and not naming_violations
    return WriteCheck(
        allowed=allowed,
        results=results,
        naming_violations=naming_violations,
        folder_warnings=folder_warnings,
    )
