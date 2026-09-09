"""The DEVON receipt shape on the status docs, enforced rather than described.

Ruled by Tee 2026-09-09, on a card. The estate carried seven different receipt
key sets across the twelve status docs that had a receipt at all, and forty
more docs with none, while `services/devon/receipts.py` parses a third format
that no status doc uses. Nothing checked any of it, so the drift compounded
silently for weeks.

The canon is the shape six of those twelve already used, the one
`SYS_OPS_os29-platform-policy-sensor_v2_2026-09-08` carries.

The exemption list below is the migration backlog, and it may only shrink. A
new doc cannot dodge the rule by carrying an old date in its filename, because
the exemption is by exact filename, not by date. When a legacy doc is migrated,
`test_a_migrated_legacy_doc_leaves_the_exemption_list` fails until its name is
removed, so the backlog cannot quietly stop shrinking either.
"""

from __future__ import annotations

import pathlib
import re

import pytest

DOCS = pathlib.Path(__file__).parent / "docs" / "devon"

#: Every key a status doc's receipt must carry. Extra keys are allowed: a doc
#: with more to say says it, but these nine are the floor so a receipt can
#: always be read the same way.
CANON_KEYS = (
    "AREA",
    "TYPE",
    "ARTIFACT",
    "DATE",
    "DECISIONS",
    "FINDINGS",
    "OPEN",
    "STATUS",
    "TOKEN",
)

#: The capture token every receipt carries, so a receipt cannot be filed
#: without the line that routes it.
CAPTURE_TOKEN = "dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f"

RECEIPT_HEADING = "## DEVON RECEIPT"

#: The migration backlog, by exact filename. Ruled as a grandfather list
#: rather than a retroactive migration: enforcing the canon on all fifty two
#: docs would have failed forty of them on the first run, and rewriting a
#: dated record to satisfy a rule made later is its own dishonesty. Shrink it
#: by migrating a doc and deleting its line, never grow it.
GRANDFATHERED = frozenset(
    {
        "SYS_OPS_alert-lane-blackout-and-estate-map_v1_2026-09-05.md",
        "SYS_OPS_austin-marchese-automation-framework-incorporation_v1_2026-09-07.md",
        "SYS_OPS_build15-presence-authority-close_v1_2026-08-26.md",
        "SYS_OPS_chatgpt-complementary-operating-layer_v1_2026-08-26.md",
        "SYS_OPS_continuity_v1_2026-08-22.md",
        "SYS_OPS_devon-agent-effect-receipts-design_v1_2026-08-24.md",
        "SYS_OPS_devon-agent-effect-receipts-handover_v1_2026-08-24.md",
        "SYS_OPS_devon-agent-effect-receipts-runtime-handover_v1_2026-08-24.md",
        "SYS_OPS_devon-agent-effect-receipts-wiring-handover_v1_2026-08-24.md",
        "SYS_OPS_devon-agent-runtime-durable-operator-handover_v1_2026-08-24.md",
        "SYS_OPS_devon-agent-runtime-handover_v1_2026-08-24.md",
        "SYS_OPS_devon-agent-task-execution-leases-handover_v1_2026-08-24.md",
        "SYS_OPS_devon-airtable-row-writer_v1_2026-09-06.md",
        "SYS_OPS_devon-autonomy-driver_v1_2026-09-05.md",
        "SYS_OPS_devon-browser-terminal-cwd-hotfix-handover_v1_2026-08-24.md",
        "SYS_OPS_devon-browser-terminal-git-root-hotfix-handover_v1_2026-08-24.md",
        "SYS_OPS_devon-browser-terminal-handover_v1_2026-08-24.md",
        "SYS_OPS_devon-browser-terminal-main-branch-hotfix-handover_v1_2026-08-24.md",
        "SYS_OPS_devon-browser-terminal-remote-main-hotfix-handover_v1_2026-08-24.md",
        "SYS_OPS_devon-browser-terminal-sdk-hotfix-handover_v1_2026-08-24.md",
        "SYS_OPS_devon-draft-parser_v1_2026-09-06.md",
        "SYS_OPS_devon-durable-shared-approval-authority-handover_v1_2026-08-24.md",
        "SYS_OPS_devon-editforge-execution_v1_2026-08-26.md",
        "SYS_OPS_devon-editforge-live-provider_v1_2026-08-27.md",
        "SYS_OPS_devon-editforge-local-operation_v1_2026-08-30.md",
        "SYS_OPS_devon-effect-receipts-hardening_v1_2026-08-24.md",
        "SYS_OPS_devon-github-capability-adapter-handover_v1_2026-08-24.md",
        "SYS_OPS_devon-hermes-agent-audit_v1_2026-09-02.md",
        "SYS_OPS_devon-hermes-expansion-handover_v1_2026-08-24.md",
        "SYS_OPS_devon-hermes-stack-status_v1_2026-08-24.md",
        "SYS_OPS_devon-hermes-stack-status_v2_2026-08-25.md",
        "SYS_OPS_devon-hermes-surface-sentinel_v1_2026-09-09.md",
        "SYS_OPS_devon-improvements-handoff_v1_2026-08-26.md",
        "SYS_OPS_devon-learning-capture-and-execution-burn_v1_2026-09-06.md",
        "SYS_OPS_devon-operational-report_v1_2026-09-06.md",
        "SYS_OPS_devon-operator-terminal-handover_v1_2026-08-24.md",
        "SYS_OPS_devon-unified-command-center-handover_v1_2026-08-26.md",
        "SYS_OPS_devon-unified-command-center-handover_v2_2026-08-26.md",
        "SYS_OPS_found-by-using-it_v1_2026-08-27.md",
        "SYS_OPS_n8n-cloud-to-vps-cutover_v2_2026-09-06.md",
        "SYS_OPS_n8n-cloud-to-vps-migration_v1_2026-08-31.md",
        "SYS_OPS_presence-hardening-and-recovery_v1_2026-08-27.md",
        "SYS_OPS_qa-checklist_v1_2026-08-22.md",
        "SYS_OPS_reconciler-score-and-grill-lane_v1_2026-09-07.md",
        "SYS_OPS_seven-improvements-close_v1_2026-08-26.md",
    }
)

FILENAME_DATE = re.compile(r"_(\d{4}-\d{2}-\d{2})\.md$")


def _status_docs() -> list[pathlib.Path]:
    return sorted(DOCS.glob("SYS_OPS_*.md"))


def _receipt_block(text: str) -> str:
    if RECEIPT_HEADING not in text:
        return ""
    return text[text.index(RECEIPT_HEADING) :]


def _keys(block: str) -> set[str]:
    return {
        match.group(1).strip()
        for match in re.finditer(r"^([A-Z][A-Z_ ]*):", block, re.MULTILINE)
    }


BOUND = [p for p in _status_docs() if p.name not in GRANDFATHERED]


def test_the_exemption_list_names_only_docs_that_exist():
    """A stale name in the list would silently exempt a future doc that
    happened to reuse it."""
    present = {p.name for p in _status_docs()}
    missing = sorted(GRANDFATHERED - present)
    assert not missing, f"exempted docs that no longer exist: {missing}"


def test_at_least_one_doc_is_actually_bound_by_this_rule():
    """A guard that binds nothing passes forever and proves nothing."""
    assert BOUND, "every status doc is exempt, so this file checks nothing"


@pytest.mark.parametrize("path", BOUND, ids=lambda p: p.name)
def test_a_status_doc_carries_a_receipt_in_the_canon_shape(path):
    text = path.read_text(encoding="utf-8")
    block = _receipt_block(text)
    assert block, f"{path.name} carries no '{RECEIPT_HEADING}' block"
    missing = [key for key in CANON_KEYS if key not in _keys(block)]
    assert not missing, f"{path.name} receipt is missing {missing}"


@pytest.mark.parametrize("path", BOUND, ids=lambda p: p.name)
def test_a_receipt_carries_the_capture_token(path):
    block = _receipt_block(path.read_text(encoding="utf-8"))
    assert f"TOKEN: {CAPTURE_TOKEN}" in block, (
        f"{path.name} receipt does not carry the capture token line verbatim"
    )


@pytest.mark.parametrize("path", BOUND, ids=lambda p: p.name)
def test_the_receipt_date_matches_the_filename(path):
    """A receipt dated differently from the file it closes makes the dated
    record unorderable, which is the one thing the record is for."""
    stamped = FILENAME_DATE.search(path.name)
    assert stamped, f"{path.name} carries no date in its filename"
    block = _receipt_block(path.read_text(encoding="utf-8"))
    dated = re.search(r"^DATE:\s*(\S+)", block, re.MULTILINE)
    assert dated, f"{path.name} receipt carries no DATE line"
    assert dated.group(1)[:10] == stamped.group(1), (
        f"{path.name} is dated {stamped.group(1)} and its receipt says "
        f"{dated.group(1)[:10]}"
    )


@pytest.mark.parametrize(
    "path",
    [p for p in _status_docs() if p.name in GRANDFATHERED],
    ids=lambda p: p.name,
)
def test_a_migrated_legacy_doc_leaves_the_exemption_list(path):
    """The backlog may only shrink. A legacy doc that already satisfies the
    canon must come off the list, so the list keeps meaning what it says."""
    block = _receipt_block(path.read_text(encoding="utf-8"))
    if not block:
        return
    if [key for key in CANON_KEYS if key not in _keys(block)]:
        return
    pytest.fail(
        f"{path.name} now satisfies the canon: remove it from GRANDFATHERED "
        "so the backlog reflects the estate"
    )
