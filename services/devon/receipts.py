"""
The DEVON RECEIPT, parsed, validated and rendered.

Sources on Drive, both read 2026-08-22:
  DEVON Cross-Platform Capture Protocol (1jVAQ6KwhFXoONg3cLYFDfi0zhLMjWAfi)
      defines the v1 block, the one pasted across ChatGPT and Grok.
  SYS_SPEC_llm-standing-instructions_v3 (1A88Nkf5BpCZysmHP7XYMXBtaEh4Eqj9M)
      defines the standing format, which added files_opened and unverified.

WHY TWO FORMATS EXIST AND WHY BOTH ARE SUPPORTED
The v1 block is already published inside platform instruction fields and iOS
Shortcuts. Changing it would break something not visible from here. The standing
format is the newer one and carries the two fields that matter most. Rather than
force a migration this module reads either and renders either, so a v1 poster
keeps working while new work emits the standing format.

WHAT THE RECEIPT IS FOR
No API reads chat threads on any platform. Nothing can silently watch three
vendors and file everything. What is possible is self reporting capture: every
thread ends by emitting one compact standard block, and because the block is
standard one destination receives all of them. The cost is roughly ten seconds
per thread. The payoff is that no thread starts from zero.

THE TWO LOAD BEARING FIELDS
`files_opened` and `unverified`. Between them they would have caught the
fabricated architecture board of 2026-08-20 before it propagated into a later
spec. A receipt missing either is not a receipt, and this module refuses it.

Two further rules taken verbatim from the protocol. `DECIDED` holds only what
was actually settled, never topics merely discussed. `OPEN` includes what
failed, because a log recording only successes lies by omission and the next
thread inherits the lie.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date as date_cls
from enum import Enum
from typing import Dict, List, Optional, Tuple

from services.devon.areas import AreaError, canonical_labels, get_area

SOURCES = {
    "v1_block": {
        "drive_id": "1jVAQ6KwhFXoONg3cLYFDfi0zhLMjWAfi",
        "title": "DEVON Cross-Platform Capture Protocol",
    },
    "standing": {
        "drive_id": "1A88Nkf5BpCZysmHP7XYMXBtaEh4Eqj9M",
        "title": "SYS_SPEC_llm-standing-instructions_v3_2026-08-21",
    },
}

PLATFORMS: Tuple[str, ...] = ("Claude", "ChatGPT", "Grok", "Gemini")

V1_OPEN = "=== DEVON RECEIPT v1 ==="
V1_CLOSE = "=== END RECEIPT ==="
STANDING_HEADER = "DEVON RECEIPT"

V1_WORD_LIMIT = 250

# Titles that describe the container rather than the content. The protocol names
# "discussion about the vault" as the example of what a title must not be.
_VAGUE_TITLE = re.compile(
    r"^\s*(a\s+)?(discussion|conversation|chat|thread|session|talk|notes?)\b"
    r"|^\s*(about|regarding|re:)\b",
    re.IGNORECASE,
)

_NONE_TOKENS = {"none", "n/a", "na", "nil", "-", "nothing"}


class ReceiptFormat(str, Enum):
    V1_BLOCK = "v1-block"
    STANDING = "standing"


class ReceiptError(ValueError):
    """Raised when text offered as a receipt cannot be read as one."""


@dataclass
class Receipt:
    """One thread receipt. A superset of both formats.

    Fields absent from a given format stay empty rather than being invented.
    `source_format` records which shape it arrived in, so a round trip does not
    silently upgrade a v1 poster into claiming fields it never supplied.
    """

    date: str = ""
    platform: str = ""
    areas: List[str] = field(default_factory=list)
    title: str = ""
    summary: str = ""
    decided: List[str] = field(default_factory=list)
    built: List[str] = field(default_factory=list)
    open_threads: List[str] = field(default_factory=list)
    next_action: str = ""
    canon: List[str] = field(default_factory=list)
    verify: List[str] = field(default_factory=list)
    files_opened: List[str] = field(default_factory=list)
    unverified: List[str] = field(default_factory=list)
    source_format: Optional[ReceiptFormat] = None
    raw: str = ""

    @property
    def produced_a_decision(self) -> bool:
        """A session producing a decision and no receipt is treated as unlogged."""
        return bool([d for d in self.decided if d.strip().lower() not in _NONE_TOKENS])

    @property
    def changes_canon(self) -> bool:
        """True when the receipt touches a standing rule, which routes further."""
        return bool([c for c in self.canon if c.strip().lower() not in _NONE_TOKENS])


@dataclass(frozen=True)
class ReceiptViolation:
    field_name: str
    severity: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.field_name}: {self.message}"


SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"


def _split_lines(value: str) -> List[str]:
    """One item per line, blanks dropped, NONE preserved as a single token.

    NONE is kept rather than emptied because an explicit NONE is an answer and
    an empty field is an omission. The validator treats them differently.
    """
    if value is None:
        return []
    items = [line.strip(" \t-•*") for line in value.splitlines()]
    items = [i for i in items if i]
    if len(items) == 1 and items[0].lower() in _NONE_TOKENS:
        return [items[0]]
    return items


def _split_areas(value: str) -> List[str]:
    if not value:
        return []
    parts = re.split(r"[,/|]| and ", value)
    return [p.strip() for p in parts if p.strip()]


def _parse_fields(body: str, keys: Tuple[str, ...]) -> Dict[str, str]:
    """Read `KEY: value` lines, allowing a value to run across following lines.

    Written as an explicit scanner rather than a regex per field so that a
    multi line SUMMARY does not swallow the next key, which is the failure mode
    that makes naive receipt parsers drop DECIDED.
    """
    normalized = {k.lower(): k for k in keys}
    found: Dict[str, List[str]] = {}
    current: Optional[str] = None
    for line in body.splitlines():
        match = re.match(r"^\s*([A-Za-z_ ]{2,20})\s*:\s*(.*)$", line)
        key = match.group(1).strip().lower().replace(" ", "_") if match else None
        if key and key in normalized:
            current = normalized[key]
            found.setdefault(current, [])
            remainder = match.group(2).strip()
            if remainder:
                found[current].append(remainder)
        elif current is not None:
            stripped = line.strip()
            if stripped:
                found[current].append(stripped)
    return {k: "\n".join(v).strip() for k, v in found.items()}


V1_KEYS = (
    "DATE",
    "PLATFORM",
    "AREA",
    "TITLE",
    "SUMMARY",
    "DECIDED",
    "BUILT",
    "OPEN",
    "NEXT",
    "CANON",
    "VERIFY",
)

STANDING_KEYS = (
    "platform",
    "date",
    "area",
    "files_opened",
    "summary",
    "decisions",
    "open_threads",
    "artifacts",
    "unverified",
)


def detect_format(text: str) -> Optional[ReceiptFormat]:
    """Identify which receipt shape the text carries, or None."""
    if not text:
        return None
    if V1_OPEN in text:
        return ReceiptFormat.V1_BLOCK
    stripped = text.strip()
    if stripped.upper().startswith(STANDING_HEADER):
        return ReceiptFormat.STANDING
    if re.search(r"^\s*files_opened\s*:", text, re.IGNORECASE | re.MULTILINE):
        return ReceiptFormat.STANDING
    return None


def parse_receipt(text: str) -> Receipt:
    """Read either receipt format into the unified model.

    Raises ReceiptError when the text is not a receipt at all. Field level
    problems are not raised here, they are reported by `validate`, because a
    malformed receipt still needs to be readable in order to be corrected.
    """
    fmt = detect_format(text)
    if fmt is None:
        raise ReceiptError(
            "No DEVON receipt found. Expected a block opening with "
            f"'{V1_OPEN}' or a '{STANDING_HEADER}' header."
        )

    if fmt is ReceiptFormat.V1_BLOCK:
        start = text.index(V1_OPEN) + len(V1_OPEN)
        end = text.index(V1_CLOSE) if V1_CLOSE in text else len(text)
        body = text[start:end]
        fields = _parse_fields(body, V1_KEYS)
        return Receipt(
            date=fields.get("DATE", "").strip(),
            platform=fields.get("PLATFORM", "").strip(),
            areas=_split_areas(fields.get("AREA", "")),
            title=fields.get("TITLE", "").strip(),
            summary=fields.get("SUMMARY", "").strip(),
            decided=_split_lines(fields.get("DECIDED", "")),
            built=_split_lines(fields.get("BUILT", "")),
            open_threads=_split_lines(fields.get("OPEN", "")),
            next_action=fields.get("NEXT", "").strip(),
            canon=_split_lines(fields.get("CANON", "")),
            verify=_split_lines(fields.get("VERIFY", "")),
            source_format=fmt,
            raw=text,
        )

    body = text[text.upper().index(STANDING_HEADER) + len(STANDING_HEADER):] \
        if STANDING_HEADER in text.upper() else text
    fields = _parse_fields(body, STANDING_KEYS)
    return Receipt(
        date=fields.get("date", "").strip(),
        platform=fields.get("platform", "").strip().strip("[]"),
        areas=_split_areas(fields.get("area", "").strip("[]")),
        summary=fields.get("summary", "").strip(),
        decided=_split_lines(fields.get("decisions", "")),
        built=_split_lines(fields.get("artifacts", "")),
        open_threads=_split_lines(fields.get("open_threads", "")),
        files_opened=_split_lines(fields.get("files_opened", "")),
        unverified=_split_lines(fields.get("unverified", "")),
        source_format=fmt,
        raw=text,
    )


def validate(receipt: Receipt, today: Optional[date_cls] = None) -> List[ReceiptViolation]:
    """Check a receipt against the rules that keep it honest."""
    today = today or date_cls.today()
    problems: List[ReceiptViolation] = []

    if not receipt.date:
        problems.append(ReceiptViolation("date", SEVERITY_ERROR, "missing"))
    else:
        try:
            parsed = date_cls.fromisoformat(receipt.date[:10])
            if parsed > today:
                problems.append(
                    ReceiptViolation(
                        "date", SEVERITY_ERROR, f"{receipt.date} is in the future"
                    )
                )
        except ValueError:
            problems.append(
                ReceiptViolation("date", SEVERITY_ERROR, f"'{receipt.date}' is not ISO")
            )

    if not receipt.platform:
        problems.append(ReceiptViolation("platform", SEVERITY_ERROR, "missing"))
    elif receipt.platform not in PLATFORMS:
        problems.append(
            ReceiptViolation(
                "platform",
                SEVERITY_ERROR,
                f"'{receipt.platform}' is not one of {', '.join(PLATFORMS)}",
            )
        )

    if not receipt.areas:
        problems.append(
            ReceiptViolation(
                "area",
                SEVERITY_ERROR,
                "missing. An untagged receipt drops into a void nobody queries.",
            )
        )
    for token in receipt.areas:
        if get_area(token) is None:
            problems.append(
                ReceiptViolation(
                    "area",
                    SEVERITY_ERROR,
                    f"'{token}' is not one of the nine. Valid: "
                    f"{', '.join(canonical_labels())}. The moment one platform invents "
                    "an Area the index fractures and the brain stops being one brain.",
                )
            )

    if not receipt.summary:
        problems.append(ReceiptViolation("summary", SEVERITY_ERROR, "missing"))

    if receipt.source_format is ReceiptFormat.V1_BLOCK:
        if not receipt.title:
            problems.append(ReceiptViolation("title", SEVERITY_ERROR, "missing"))
        elif _VAGUE_TITLE.search(receipt.title):
            problems.append(
                ReceiptViolation(
                    "title",
                    SEVERITY_WARNING,
                    f"'{receipt.title}' names the container, not the content. "
                    "A title must be specific.",
                )
            )
        if not receipt.next_action:
            problems.append(
                ReceiptViolation("next", SEVERITY_WARNING, "no single next action stated")
            )
        words = len(receipt.raw.split())
        if words > V1_WORD_LIMIT:
            problems.append(
                ReceiptViolation(
                    "length",
                    SEVERITY_WARNING,
                    f"{words} words, over the {V1_WORD_LIMIT} word guide. "
                    "A receipt is a receipt, not a transcript.",
                )
            )

    if receipt.source_format is ReceiptFormat.STANDING:
        if not receipt.files_opened:
            problems.append(
                ReceiptViolation(
                    "files_opened",
                    SEVERITY_ERROR,
                    "missing and load bearing. State the DEVON files actually read "
                    "this session, or NONE. Not read means not read, and a "
                    "memory sourced claim is not covered by labelling it unverified.",
                )
            )
        if not receipt.unverified:
            problems.append(
                ReceiptViolation(
                    "unverified",
                    SEVERITY_ERROR,
                    "missing and load bearing. Everything asserted without "
                    "measurement goes here, or NONE.",
                )
            )

    if not receipt.open_threads:
        problems.append(
            ReceiptViolation(
                "open",
                SEVERITY_ERROR,
                "missing. OPEN records what is unresolved and what failed. A log "
                "recording only successes lies by omission.",
            )
        )

    if receipt.verify == [] and receipt.source_format is ReceiptFormat.V1_BLOCK:
        problems.append(
            ReceiptViolation(
                "verify",
                SEVERITY_WARNING,
                "empty. VERIFY is not optional, and a receipt with nothing "
                "unverified after a research heavy thread is hiding something. "
                "State NONE deliberately if nothing needs checking.",
            )
        )

    return problems


def is_valid(receipt: Receipt, today: Optional[date_cls] = None) -> bool:
    """True when no error severity problem is present."""
    return not any(p.severity == SEVERITY_ERROR for p in validate(receipt, today))


def require_valid(receipt: Receipt, today: Optional[date_cls] = None) -> Receipt:
    """Return the receipt or raise loudly listing every error.

    The capture parser rejects an unknown Area loudly rather than silently
    dropping the row, which is what this enforces on the write path.
    """
    problems = [p for p in validate(receipt, today) if p.severity == SEVERITY_ERROR]
    if problems:
        raise ReceiptError(
            "Receipt refused:\n" + "\n".join(f"  {p}" for p in problems)
        )
    return receipt


def _render_list(items: List[str]) -> str:
    if not items:
        return "none"
    return "\n".join(items) if len(items) > 1 else items[0]


def render_v1(receipt: Receipt) -> str:
    """Emit the v1 block, the shape ChatGPT and Grok are instructed to produce."""
    areas = ", ".join(receipt.areas) if receipt.areas else ""
    return "\n".join(
        [
            V1_OPEN,
            f"DATE: {receipt.date}",
            f"PLATFORM: {receipt.platform}",
            f"AREA: {areas}",
            f"TITLE: {receipt.title}",
            f"SUMMARY: {receipt.summary}",
            f"DECIDED: {_render_list(receipt.decided)}",
            f"BUILT: {_render_list(receipt.built)}",
            f"OPEN: {_render_list(receipt.open_threads)}",
            f"NEXT: {receipt.next_action or 'none'}",
            f"CANON: {_render_list(receipt.canon)}",
            f"VERIFY: {_render_list(receipt.verify)}",
            V1_CLOSE,
        ]
    )


def render_standing(receipt: Receipt) -> str:
    """Emit the standing format, which carries files_opened and unverified."""
    areas = " | ".join(receipt.areas) if receipt.areas else ""
    return "\n".join(
        [
            STANDING_HEADER,
            f"platform: {receipt.platform}",
            f"date: {receipt.date}",
            f"area: {areas}",
            f"files_opened: {_render_list(receipt.files_opened)}",
            f"summary: {receipt.summary}",
            f"decisions: {_render_list(receipt.decided)}",
            f"open threads: {_render_list(receipt.open_threads)}",
            f"artifacts: {_render_list(receipt.built)}",
            f"unverified: {_render_list(receipt.unverified)}",
        ]
    )


def normalize_areas(receipt: Receipt) -> Receipt:
    """Rewrite the Area tokens to canonical labels, refusing unknown ones.

    Run this before filing so that a receipt tagged TSWS and one tagged Podcast
    land on the same row value, which is the drift that split the index between
    the filename vocabulary and the prose vocabulary.
    """
    normalized: List[str] = []
    for token in receipt.areas:
        area = get_area(token)
        if area is None:
            raise AreaError(
                f"'{token}' is not one of the nine DEVON Areas. Refusing to file "
                "a receipt into an untagged void."
            )
        if area.label not in normalized:
            normalized.append(area.label)
    receipt.areas = normalized
    return receipt
