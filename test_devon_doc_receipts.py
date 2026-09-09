"""Every DEVON receipt in docs/devon parses and files.

The receipt convention was decorative. `services/devon/receipts.py` could read
both shapes, `test_devon_receipts.py` proved it on hand written samples, and
nothing ever handed it a receipt out of the estate's own documents. Measured on
2026-09-09 before this file existed: eighteen documents under `docs/devon`
carry a receipt, one of them validated, and seventeen had AREA holding the
entire rest of the block because the parser absorbed every field name it did
not know. So an area read `ruff clean` or `api 1196 passed`, and
`normalize_areas` would have refused to file any of them.

This closes the loop the other way round from `test_devon_integrity.py`, which
reads the same files for banned dashes and never looks at a receipt.

What is checked here is what has to be true for a receipt to be filed at all:
it parses, and its AREA resolves to one of the nine. The full thread capture
validation in `receipts.validate` is deliberately not applied, because it
requires PLATFORM, SUMMARY, OPEN and FILES_OPENED, which belong to a thread
receipt posted to the capture webhook and not to a dated SYS_OPS status
document. Holding status docs to the thread shape would mean rewriting the
dated record to satisfy a test, which is the opposite of what the record is for.

Cheap on purpose: no database, no network.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

import pytest

from services.devon.areas import get_area
from services.devon.receipts import V1_OPEN, parse_receipt

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs" / "devon"

#: A real receipt block opens with a markdown heading, optionally numbered, or
#: with the v1 fence. A bare mention of the words in a table row or a sentence
#: is prose about receipts, not a receipt, and there are four of those.
_HEADING = re.compile(r"^#{1,6}\s*(?:\d+\.\s*)?DEVON RECEIPT\s*$", re.MULTILINE)


def _receipt_blocks() -> Dict[str, str]:
    """Each document that carries a receipt, mapped to the block itself."""
    found: Dict[str, str] = {}
    for path in sorted(DOCS.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if V1_OPEN in text:
            found[path.name] = text[text.index(V1_OPEN):]
            continue
        heading = _HEADING.search(text)
        if heading:
            # Slice from the words themselves, not from the end of the heading
            # line: detect_format identifies the standing shape by the text
            # starting with the header, so "## " in front of it, or the block
            # starting after it, both read as no receipt at all.
            found[path.name] = text[text.index("DEVON RECEIPT", heading.start()):]
    return found


BLOCKS = _receipt_blocks()


def test_the_estate_actually_carries_receipts() -> None:
    """A detector that quietly matches nothing would pass every test below."""
    assert len(BLOCKS) >= 13, (
        f"only {len(BLOCKS)} receipt blocks found under {DOCS.relative_to(ROOT)}; "
        "the detector is matching less than the estate carries, so the checks "
        "below would pass by finding nothing"
    )


def test_prose_about_receipts_is_not_mistaken_for_one() -> None:
    """Four documents discuss receipts in a table row or an instruction.

    They must not be held to the shape, and a detector that swept on the bare
    string would have failed all four.
    """
    prose = [
        "DEVON.md",
        "SYS_OPS_continuity_v1_2026-08-22.md",
        "SYS_OPS_devon-airtable-row-writer_v1_2026-09-06.md",
        "SYS_OPS_qa-checklist_v1_2026-08-22.md",
    ]
    for name in prose:
        path = DOCS / name
        if not path.is_file():
            continue
        assert "DEVON RECEIPT" in path.read_text(encoding="utf-8"), (
            f"{name} no longer mentions a receipt, so this guard is checking nothing. "
            "Drop it from the list rather than leaving it inert."
        )
        assert name not in BLOCKS, (
            f"{name} mentions receipts in prose and carries no receipt block, but the "
            "detector matched it. Tighten the detector rather than the document."
        )


@pytest.mark.parametrize("name", sorted(BLOCKS))
def test_each_receipt_parses(name: str) -> None:
    receipt = parse_receipt(BLOCKS[name])
    assert receipt.source_format is not None, f"{name}: no receipt format detected"


@pytest.mark.parametrize("name", sorted(BLOCKS))
def test_each_receipt_files_under_one_of_the_nine_areas(name: str) -> None:
    """An AREA that does not resolve cannot be filed; normalize_areas refuses it."""
    receipt = parse_receipt(BLOCKS[name])
    assert receipt.areas, (
        f"{name}: the receipt states no AREA, so DEVON cannot file it. Add an "
        "AREA line naming one of the nine."
    )
    unknown = [token for token in receipt.areas if get_area(token) is None]
    assert not unknown, (
        f"{name}: AREA carries {unknown!r}, which is not one of the nine DEVON areas. "
        "If the value looks like the rest of the receipt rather than an area, the "
        "parser absorbed a field it does not know; see _parse_fields in "
        "services/devon/receipts.py."
    )


@pytest.mark.parametrize("name", sorted(BLOCKS))
def test_each_receipt_carries_the_capture_token(name: str) -> None:
    """The standing convention: every receipt block carries the capture token.

    Ruled on 2026-09-02 that these are identifiers rather than credentials, so
    the token in the block is deliberate and its absence is the defect.
    """
    assert re.search(r"^TOKEN:\s*\S+", BLOCKS[name], re.MULTILINE), (
        f"{name}: the receipt block states no TOKEN line."
    )


def test_no_receipt_area_swallowed_the_rest_of_the_block() -> None:
    """The specific corruption this file was written after.

    An absorbed field shows up as an area carrying a newline or another field
    name. Checked across every block at once so the failure names all of them.
    """
    swallowed: List[str] = []
    for name, block in sorted(BLOCKS.items()):
        for token in parse_receipt(block).areas:
            if "\n" in token or re.search(r"\b(TYPE|ARTIFACT|BUILT|STATUS|DATE)\b", token):
                swallowed.append(f"{name}: {token[:60]!r}")
    assert not swallowed, (
        "these receipts have an AREA that ran past its own line, which means the "
        "parser absorbed a field name it does not know: " + "; ".join(swallowed)
    )
