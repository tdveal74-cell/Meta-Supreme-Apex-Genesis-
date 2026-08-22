"""
DEVON naming convention, executable.

Source of truth on Drive: SYS_SPEC_naming-convention_v4_2026-08-22
(Drive id 1r5-7JCqMDEHcYWj97AxZuWuzb7wdSYCL), read 2026-08-22.

    AREA_TYPE_slug_vN_YYYY-MM-DD[_MARKER].ext

Segments split on underscore. Words inside the slug split on hyphen. That one
distinction is what makes a name machine splittable and still readable.

WHY THIS IS CODE AND NOT A DOCUMENT
The convention forked twice inside a single day, at 08:41 and 08:42 on
2026-08-22, written by two threads that had both read the law telling them to
list the folder first. The violation record in v4 says work on 21 and 22 August
produced v2.1 through v2.5 and v1.1 while a v1 convention banning decimals sat
unread in the same folder. A rule nobody opens is not enforced. A parser that
refuses a bad name is.

Version numbers are plain integers, ruled by Tee on 2026-08-22, reversing the
point releases v3 permitted. Existing decimal filenames stay, because renaming
them would break Drive ids already recorded in the master directory. So this
module parses decimals, reports them as grandfathered, and refuses to build a
new one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date as date_cls
from typing import List, Optional, Tuple

SOURCE = {
    "drive_id": "1r5-7JCqMDEHcYWj97AxZuWuzb7wdSYCL",
    "title": "SYS_SPEC_naming-convention_v4_2026-08-22",
    "ruled": "2026-08-22",
    "read": "2026-08-22",
}

# The nine Area codes. Kept in sync with services.devon.areas by test, not by
# import, so that a drift between the two fails a test rather than passing
# silently through a shared constant.
AREA_CODES: Tuple[str, ...] = (
    "TQO",
    "TSWS",
    "NCO",
    "ACX",
    "SYS",
    "HEALTH",
    "MONEY",
    "FAMILY",
    "LEARNING",
)

# Two prefixes permitted outside the Area set.
NON_AREA_PREFIXES: Tuple[str, ...] = ("ARCHIVE", "RETIRED")

# Short forms recorded as already in use and valid.
SHORT_FORMS: dict[str, str] = {
    "FAM": "FAMILY",
    "MON": "MONEY",
    "LRN": "LEARNING",
    "RES": "RESOURCES",
    "INBOX": "INBOX",
}

TYPE_CODES: Tuple[str, ...] = (
    "CANON",
    "SCRIPT",
    "BRAND",
    "OPS",
    "SKILL",
    "SOURCE",
    "PROOF",
    "LOG",
    "SPEC",
    "INDEX",
    "DATA",
    "BUILD",
    "DOC",
)

# A file carrying any protective marker is never auto superseded, never swept,
# never overwritten. Renaming is deliberately the whole mechanism, because a
# rename works in Drive, on the phone, and in a script with no database to keep
# in sync.
PROTECTIVE_MARKERS: Tuple[str, ...] = (
    "KEEP",
    "EVIDENCE",
    "LOCKED",
    "ORIGINAL",
    "DO-NOT-DELETE",
)

# Warning markers outrank general heuristics including keep latest. This is
# Filing Law 5, and exists because a literal keep latest pass would have deleted
# a decision addendum holding four rulings that existed nowhere else.
WARNING_MARKERS: Tuple[str, ...] = (
    "SUPERSEDED",
    "RETIRED",
    "PARTIAL",
    "do-not-build-against",
    "ruling-owed",
    "unreviewed",
    "untriaged",
)

# Superseded material takes a prefix, not a suffix and not an infix, ruled
# 2026-08-22. A prefix sorts every retired file to one place in a listing.
SUPERSEDED_PREFIX = "SUPERSEDED"

MAX_NAME_LENGTH = 80

# Banned as bare names outside a code repo. The 2026-08-05 scan found 471 files
# fighting over 97 names, five of them called SKILL.md.
GENERIC_NAMES: Tuple[str, ...] = (
    "skill.md",
    "readme.md",
    "untitled.md",
    "untitled",
    "notes.md",
    "document.md",
    "new.md",
    "copy.md",
)

_GENERIC_STEM_PATTERN = re.compile(r"^(file|img|image|doc|document|untitled|new)[_\-]?\d*$", re.I)

# Status words banned in a name unless they warn.
BANNED_STATUS_WORDS: Tuple[str, ...] = ("final", "new", "real", "copy", "latest", "current")

_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_VERSION = re.compile(r"^v(\d+)(?:\.(\d+))?$", re.I)
_EM_DASH_CHARS = ("—", "–")  # wordlist-exempt: cited prohibition, this is the detector

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"


class NamingError(ValueError):
    """Raised when a name cannot be built to the convention."""


@dataclass(frozen=True)
class Violation:
    """One convention breach, with the rule that caught it."""

    rule: str
    severity: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.rule}: {self.message}"


@dataclass
class ParsedName:
    """The result of reading a filename against the convention.

    Parsing never raises. A name that cannot be parsed is reported, because the
    vault is full of names written before the convention existed and a crash on
    read would make the validator unusable on the files that need it most.
    """

    raw: str
    prefix_marker: Optional[str] = None
    area: Optional[str] = None
    type_code: Optional[str] = None
    slug: Optional[str] = None
    version: Optional[int] = None
    version_raw: Optional[str] = None
    version_is_decimal: bool = False
    date: Optional[str] = None
    markers: Tuple[str, ...] = ()
    extension: Optional[str] = None
    violations: List[Violation] = field(default_factory=list)

    @property
    def conforms(self) -> bool:
        """True when no error severity violation was found."""
        return not any(v.severity == SEVERITY_ERROR for v in self.violations)

    @property
    def is_protected(self) -> bool:
        """True when any protective marker is present. Never auto supersede these."""
        present = {m.upper() for m in self.markers}
        return any(m.upper() in present for m in PROTECTIVE_MARKERS)

    @property
    def is_superseded(self) -> bool:
        """True when the name carries the superseded or retired warning."""
        tokens = {m.upper() for m in self.markers}
        if self.prefix_marker:
            tokens.add(self.prefix_marker.upper())
        return "SUPERSEDED" in tokens or "RETIRED" in tokens

    @property
    def warnings_in_name(self) -> Tuple[str, ...]:
        """Warning markers found, which outrank any general heuristic."""
        found = []
        pool = list(self.markers)
        if self.prefix_marker:
            pool.append(self.prefix_marker)
        for token in pool:
            for marker in WARNING_MARKERS:
                if token.upper() == marker.upper():
                    found.append(marker)
        return tuple(found)


def _split_extension(name: str) -> Tuple[str, Optional[str]]:
    if "." not in name:
        return name, None
    stem, _, ext = name.rpartition(".")
    if not stem:
        return name, None
    return stem, ext


def _is_marker(token: str) -> bool:
    upper = token.upper()
    if any(upper == m.upper() for m in PROTECTIVE_MARKERS):
        return True
    return any(upper == m.upper() for m in WARNING_MARKERS)


def parse_filename(name: str) -> ParsedName:
    """Read a filename against the convention. Never raises.

    Handles the shapes actually present in the vault: the clean pattern, a
    SUPERSEDED_ prefixed name, a trailing marker, legacy decimal versions, and
    the annotated retirement suffix such as `--merged-into-v3` that several real
    files carry after the date segment.
    """
    parsed = ParsedName(raw=name)
    if not name or not name.strip():
        parsed.violations.append(
            Violation("structure", SEVERITY_ERROR, "empty filename")
        )
        return parsed

    for bad in _EM_DASH_CHARS:
        if bad in name:
            parsed.violations.append(
                Violation(
                    "rule-7",
                    SEVERITY_ERROR,
                    "no em dashes or en dashes in filenames, studio wide",
                )
            )
            break

    stem, ext = _split_extension(name)
    parsed.extension = ext

    lowered = name.strip().lower()
    if lowered in GENERIC_NAMES or _GENERIC_STEM_PATTERN.match(stem.strip()):
        parsed.violations.append(
            Violation(
                "rule-1",
                SEVERITY_ERROR,
                f"'{name}' is a bare generic name. Inside a packaged skill the file "
                "must be SKILL.md; the vault copy gets a real name.",
            )
        )

    if len(name) > MAX_NAME_LENGTH:
        parsed.violations.append(
            Violation(
                "rule-3",
                SEVERITY_WARNING,
                f"{len(name)} characters. Over roughly {MAX_NAME_LENGTH} a filename is "
                "documentation and belongs in frontmatter.",
            )
        )

    segments = [s for s in stem.split("_") if s != ""]
    if not segments:
        parsed.violations.append(Violation("structure", SEVERITY_ERROR, "no segments"))
        return parsed

    # A leading warning marker is a prefix, per the 2026-08-22 ruling.
    if segments and segments[0].upper() in {m.upper() for m in WARNING_MARKERS}:
        parsed.prefix_marker = segments[0]
        segments = segments[1:]

    # Trailing markers.
    trailing: List[str] = []
    while segments and _is_marker(segments[-1]):
        trailing.insert(0, segments.pop())
    parsed.markers = tuple(trailing)

    if len(segments) < 2:
        parsed.violations.append(
            Violation(
                "structure",
                SEVERITY_ERROR,
                "expected AREA_TYPE_slug_vN_YYYY-MM-DD, found fewer than two segments",
            )
        )
        if segments:
            parsed.area = segments[0]
        return parsed

    parsed.area = segments[0]
    parsed.type_code = segments[1]
    rest = segments[2:]

    # Date is the last segment that starts with an ISO date, allowing an
    # annotation suffix such as 2026-08-21--by-v4.
    date_index: Optional[int] = None
    for index in range(len(rest) - 1, -1, -1):
        head = rest[index][:10]
        if _ISO_DATE.match(head):
            date_index = index
            parsed.date = head
            if len(rest[index]) > 10:
                parsed.markers = parsed.markers + (rest[index][10:].lstrip("-"),)
            break

    version_index: Optional[int] = None
    for index in range(len(rest) - 1, -1, -1):
        match = _VERSION.match(rest[index])
        if match:
            version_index = index
            parsed.version_raw = rest[index]
            parsed.version = int(match.group(1))
            parsed.version_is_decimal = match.group(2) is not None
            break

    slug_end = min([i for i in (date_index, version_index) if i is not None], default=len(rest))
    slug_parts = rest[:slug_end]
    parsed.slug = "_".join(slug_parts) if slug_parts else None

    _validate_parsed(parsed)
    return parsed


def _validate_parsed(parsed: ParsedName) -> None:
    """Apply the convention's rules to an already split name."""
    area = (parsed.area or "").upper()
    known_area = (
        area in AREA_CODES
        or area in NON_AREA_PREFIXES
        or area in SHORT_FORMS
    )
    if not known_area:
        parsed.violations.append(
            Violation(
                "area-code",
                SEVERITY_ERROR,
                f"'{parsed.area}' is not one of the nine Area codes "
                f"({', '.join(AREA_CODES)}), nor ARCHIVE or RETIRED, nor a known short form.",
            )
        )

    type_code = (parsed.type_code or "").upper()
    if type_code and type_code not in TYPE_CODES:
        parsed.violations.append(
            Violation(
                "type-code",
                SEVERITY_ERROR,
                f"'{parsed.type_code}' is not one of the thirteen type codes. "
                "If something fits none of them it is DOC. If the same kind of thing "
                "lands on DOC three times, add a code rather than inventing one.",
            )
        )

    if not parsed.slug:
        parsed.violations.append(
            Violation("structure", SEVERITY_ERROR, "no slug segment found")
        )

    if parsed.version is None:
        parsed.violations.append(
            Violation("version", SEVERITY_WARNING, "no version segment, expected vN")
        )
    elif parsed.version_is_decimal:
        parsed.violations.append(
            Violation(
                "version",
                SEVERITY_WARNING,
                f"'{parsed.version_raw}' is a point release. Ruled 2026-08-22: plain "
                "integers only. Existing decimal filenames are grandfathered and must "
                "not be renamed, because the master directory records their ids.",
            )
        )

    if parsed.date is None:
        parsed.violations.append(
            Violation(
                "rule-2",
                SEVERITY_ERROR,
                "no ISO date segment. Dates are ISO or they are not dates, and "
                "anything else sorts wrong.",
            )
        )
    else:
        try:
            date_cls.fromisoformat(parsed.date)
        except ValueError:
            parsed.violations.append(
                Violation("rule-2", SEVERITY_ERROR, f"'{parsed.date}' is not a real date")
            )

    slug_words = (parsed.slug or "").lower().replace("_", "-").split("-")
    for banned in BANNED_STATUS_WORDS:
        if banned in slug_words:
            parsed.violations.append(
                Violation(
                    "rule-5",
                    SEVERITY_WARNING,
                    f"'{banned}' in the slug. Status belongs in a name only when it "
                    "warns. Never final, new, v2_real, copy.",
                )
            )


def validate_filename(name: str) -> List[Violation]:
    """Convenience wrapper returning the violations for a name."""
    return parse_filename(name).violations


def slugify(text: str) -> str:
    """Lowercase hyphen slug. Words inside a slug split on hyphen, never underscore."""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower())
    return cleaned.strip("-")


def build_filename(
    area: str,
    type_code: str,
    slug: str,
    version: int,
    on_date: str,
    marker: Optional[str] = None,
    extension: str = "md",
    superseded: bool = False,
) -> str:
    """Build a conforming filename, or raise.

    Refuses a decimal version outright. The grandfather clause in v4 covers names
    already written; it is not a licence to write another one.

    `on_date` is the date the content was settled, not the date it was saved.
    That segment is the most load bearing one in the whole name, because
    precedence reads it before modified time.
    """
    area_upper = area.strip().upper()
    if (
        area_upper not in AREA_CODES
        and area_upper not in NON_AREA_PREFIXES
        and area_upper not in SHORT_FORMS
    ):
        raise NamingError(
            f"'{area}' is not a valid Area code. Valid: {', '.join(AREA_CODES)}, "
            f"plus {', '.join(NON_AREA_PREFIXES)} and short forms {', '.join(SHORT_FORMS)}."
        )

    type_upper = type_code.strip().upper()
    if type_upper not in TYPE_CODES:
        raise NamingError(
            f"'{type_code}' is not a valid type code. Valid: {', '.join(TYPE_CODES)}."
        )

    if not isinstance(version, int) or isinstance(version, bool):
        raise NamingError(
            "version must be a plain integer. Point releases were reversed by "
            "Tee's ruling on 2026-08-22."
        )
    if version < 1:
        raise NamingError("version must be 1 or greater")

    if not _ISO_DATE.match(on_date):
        raise NamingError(f"'{on_date}' is not an ISO date. Use YYYY-MM-DD.")
    try:
        date_cls.fromisoformat(on_date)
    except ValueError as exc:
        raise NamingError(f"'{on_date}' is not a real date") from exc

    clean_slug = slugify(slug)
    if not clean_slug:
        raise NamingError("slug is empty after cleaning")

    if marker is not None:
        known = {m.upper() for m in PROTECTIVE_MARKERS} | {m.upper() for m in WARNING_MARKERS}
        if marker.upper() not in known:
            raise NamingError(
                f"'{marker}' is not a known marker. Protective: "
                f"{', '.join(PROTECTIVE_MARKERS)}. Warning: {', '.join(WARNING_MARKERS)}."
            )

    parts = [area_upper, type_upper, clean_slug, f"v{version}", on_date]
    if marker:
        parts.append(marker)
    name = "_".join(parts)
    if superseded:
        name = f"{SUPERSEDED_PREFIX}_{name}"
    if extension:
        name = f"{name}.{extension.lstrip('.')}"

    for bad in _EM_DASH_CHARS:
        if bad in name:
            raise NamingError("no em dashes or en dashes in filenames")

    if len(name) > MAX_NAME_LENGTH:
        # A warning rather than a refusal: some legitimate names run long, and
        # refusing to build one would push the caller into an unnamed file.
        pass

    return name


def disambiguate_by_measurement(
    base_name: str,
    size_bytes: int,
    stamp: str,
) -> str:
    """Put the distinguishing measurement in the filename before asking for a ruling.

    Filing Law 4 and the convention both carry this. When several files share a
    name and none can be ruled without opening them, a measured name turns an
    unrulable pile into a one screen decision. Strip the measurement once the
    ruling is made and the survivors are unique again.
    """
    stem, ext = _split_extension(base_name)
    measured = f"{stem}_{size_bytes}bytes_{stamp}"
    return f"{measured}.{ext}" if ext else measured
