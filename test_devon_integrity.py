"""
Integrity tests for the DEVON package itself.

These check properties of the source rather than its behaviour: that the studio's
own hard rules hold in the code that claims to enforce them, that every doctrine
module declares where it came from, and that the package cannot reach the network.

The last one is the load bearing test in this file. DEVON parses, plans and
gates; it never performs an effect. A component with no network capability cannot
be argued into using one, and that property has to be checked rather than
asserted, because it is exactly the kind of thing a later edit erodes quietly.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

PACKAGE = pathlib.Path(__file__).parent / "services" / "devon"
SOURCE_FILES = sorted(PACKAGE.glob("*.py"))
DOC_FILES = sorted((pathlib.Path(__file__).parent / "docs" / "devon").glob("*.md"))


def test_the_package_has_the_expected_modules():
    names = {p.stem for p in SOURCE_FILES}
    expected = {
        "__init__",
        "approval",
        "areas",
        "assistant",
        "commands",
        "filing",
        "flagship",
        "naming",
        "persona",
        "precedence",
        "receipts",
        "vault",
    }
    assert expected <= names


# Voice standard v2 carries four exempt categories, one of which is a cited
# prohibition. A line defining the detector for a banned mark has to contain the
# mark. The marker is explicit and greppable so an exemption cannot be claimed
# quietly, which is the soft spot the standard itself names.
EXEMPT_MARKER = "wordlist-exempt"

BANNED_MARKS = ("—", "–")


def _offending_lines(text: str) -> list[str]:
    return [
        line
        for line in text.splitlines()
        if any(mark in line for mark in BANNED_MARKS) and EXEMPT_MARKER not in line
    ]


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: p.name)
def test_no_em_dashes_in_the_source(path):
    """Hard rule 1, studio wide and absolute. Restructure, do not swap punctuation."""
    offenders = _offending_lines(path.read_text(encoding="utf-8"))
    assert not offenders, f"banned dash in {path.name}: {offenders[:3]}"


@pytest.mark.parametrize("path", DOC_FILES, ids=lambda p: p.name)
def test_no_em_dashes_in_the_docs(path):
    offenders = _offending_lines(path.read_text(encoding="utf-8"))
    assert not offenders, f"banned dash in {path.name}: {offenders[:3]}"


def test_exemptions_are_rare_and_explicit():
    """An agent wrapping a hard line in a marker erodes the rule quietly."""
    exempt = []
    for path in SOURCE_FILES:
        for line in path.read_text(encoding="utf-8").splitlines():
            if EXEMPT_MARKER in line:
                exempt.append((path.name, line.strip()))
    assert len(exempt) <= 3, f"too many exemptions claimed: {exempt}"
    for _, line in exempt:
        assert "cited prohibition" in line


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: p.name)
def test_every_module_parses(path):
    ast.parse(path.read_text(encoding="utf-8"))


# The modules compiled from vault doctrine must each say where they came from,
# so a reader can go and check the original rather than trusting the copy.
DOCTRINE_MODULES = {
    "areas": "SOURCE",
    "naming": "SOURCE",
    "precedence": "SOURCE",
    "filing": "SOURCE",
    "flagship": "SOURCE",
    "receipts": "SOURCES",
    "vault": "SOURCES",
    "persona": "SOURCES",
    "commands": "SOURCES",
    "approval": "SOURCE",
}


@pytest.mark.parametrize("module_name,attr", sorted(DOCTRINE_MODULES.items()))
def test_doctrine_modules_declare_their_provenance(module_name, attr):
    import importlib

    module = importlib.import_module(f"services.devon.{module_name}")
    declared = getattr(module, attr, None)
    assert declared, f"{module_name} does not declare {attr}"
    rendered = repr(declared)
    # Either a labelled drive_id, or a bare Drive id, or a named upstream source.
    looks_sourced = (
        "drive_id" in rendered
        or "workflow" in rendered
        or "upstream" in rendered
        or re.search(r"'1[A-Za-z0-9_-]{20,}'", rendered) is not None
    )
    assert looks_sourced, f"{module_name}.{attr} names no checkable source"


# Modules that must never import a network or subprocess capability.
NETWORK_FORBIDDEN = (
    "requests",
    "httpx",
    "urllib",
    "socket",
    "http",
    "subprocess",
    "os.system",
    "ftplib",
    "smtplib",
    "telnetlib",
)


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: p.name)
def test_the_package_cannot_reach_the_network_or_spawn_a_process(path):
    """DEVON plans and gates. The caller executes. Prove the capability is absent."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    for name in imported:
        root = name.split(".")[0]
        assert root not in NETWORK_FORBIDDEN, (
            f"{path.name} imports '{name}'. The DEVON package must not carry a "
            "network or process spawning capability."
        )


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: p.name)
def test_no_eval_or_exec_in_the_package(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in ("eval", "exec", "compile"), (
                f"{path.name} calls {node.func.id}"
            )


def test_the_vault_map_covers_every_area():
    from services.devon import areas, vault

    for label in areas.canonical_labels():
        assert label in vault.AREA_FOLDERS, f"no Drive folder recorded for {label}"


def test_the_vault_declares_its_staleness_risk():
    """Ids were read once and do not update themselves. Say so."""
    from services.devon import vault

    assert vault.READ_ON
    assert "not self updating" in vault.VERIFY_BEFORE_AUTOMATION


def test_the_dead_airtable_base_is_recorded_as_dead():
    from services.devon import vault

    assert vault.AIRTABLE["dead_base"] == "appKIY47KvzBpZQOQ"
    assert vault.AIRTABLE["live_base"] == "app28z7XnKzjfTXwc"
    assert vault.AIRTABLE["live_base"] != vault.AIRTABLE["dead_base"]


def test_the_ten_hard_rules_are_carried():
    from services.devon import persona

    assert len(persona.HARD_RULES) == 10
    assert [r.number for r in persona.HARD_RULES] == list(range(1, 11))


def test_the_persona_boundary_is_load_bearing_and_present():
    from services.devon import persona

    assert "Never caricature" in persona.BOUNDARY
    assert "Never caricature" in persona.system_prompt()


def test_the_system_prompt_states_when_nothing_was_read():
    from services.devon import persona

    prompt = persona.system_prompt()
    assert "not read" in prompt


def test_punctuation_check_catches_the_banned_marks():
    from services.devon import persona

    assert persona.check_punctuation("a clean sentence") == []
    assert persona.check_punctuation("a — dash")
    assert persona.check_punctuation("a ; semicolon")


def test_the_word_list_objection_is_logged_once_and_explained():
    """Hard rule 5: when overruled, log the objection once and execute at full quality."""
    from services.devon import persona

    assert "objection logged once" in persona.WORD_LIST_NOTE.lower()


def test_only_claude_may_write_canon():
    from services.devon import vault

    assert vault.PERMISSIONS["Claude"].may_write_canon
    for platform in ("ChatGPT", "Grok", "Gemini"):
        assert not vault.PERMISSIONS[platform].may_write_canon


def test_other_platforms_are_confined_to_the_capture_inbox():
    from services.devon import vault

    core = vault.FOLDERS["_Devon Core"]
    for platform in ("ChatGPT", "Grok", "Gemini"):
        allowed, reason = vault.may_write(platform, core)
        assert not allowed
        assert "one writer" in reason


def test_an_unknown_platform_writes_nowhere():
    from services.devon import vault

    allowed, reason = vault.may_write("SomeNewBot", vault.CAPTURE_INBOX["id"])
    assert not allowed
    assert "no recorded write permission" in reason


def test_unrecognised_capture_types_are_parked_not_guessed():
    from services.devon import vault

    destination, recognised = vault.route_capture("xyz")
    assert not recognised
    assert destination == vault.UNROUTED_DESTINATION

    destination, recognised = vault.route_capture("pdf")
    assert recognised
    assert "Documents" in destination


def test_draft_folders_match_the_executor_folder_map() -> None:
    """The Drive Draft Writer carries its own copy of DRAFT_FOLDERS.

    n8n cannot import the vault, so Build 16's Validate and Plan node holds the
    same Area to folder map inline. The repo copy of that node lives under
    ``n8n/devon/drive-draft-writer/``. If the two drift, DEVON writes a draft
    into a folder the vault does not permit for the Area and nothing else
    notices. This pins them together.
    """
    from services.devon import vault

    Path = pathlib.Path
    source = Path(__file__).parent / "n8n" / "devon" / "drive-draft-writer" / "validate_and_plan.js"
    assert source.exists(), f"{source} is missing; the executor source must live in the repo"
    body = source.read_text(encoding="utf-8")

    block = re.search(r"const FOLDERS = \{(.*?)\n\};", body, re.S)
    assert block, "FOLDERS map not found in the executor source"
    pairs = dict(re.findall(r"'([A-Za-z]+)':\s*\{\s*id:\s*'([^']+)'", block.group(1)))

    inbox = re.search(r"const INBOX = \{\s*id:\s*'([^']+)'", body)
    assert inbox, "INBOX fallback not found in the executor source"
    pairs["_unknown"] = inbox.group(1)

    assert pairs == vault.DRAFT_FOLDERS, (
        "the executor's folder map and vault.DRAFT_FOLDERS disagree; "
        "change both or neither"
    )

    # The approval card names the folder in words, from a third copy of the map
    # inside the driver's Decide node. That sentence is the one thing Tee reads
    # about where the document lands, so it is pinned to the folder NAMES the
    # executor actually writes to, not just to the ids.
    names = dict(re.findall(r"'([A-Za-z]+)':\s*\{[^}]*?name:\s*'([^']+)'", block.group(1)))
    decide = Path(__file__).parent / "n8n" / "devon" / "job-driver" / "decide.js"
    assert decide.exists(), f"{decide} is missing; the driver source must live in the repo"
    labels = dict(
        re.findall(
            r"(\w+):\s*'the [^']*?\(([^)]+)\)'",
            re.search(r"const AREA_FOLDER_LABEL = \{(.*?)\};", decide.read_text(encoding="utf-8"), re.S).group(1),
        )
    )
    assert labels, "AREA_FOLDER_LABEL not found in the driver source"
    for area, folder in labels.items():
        assert names.get(area) == folder, (
            f"the approval card tells Tee a {area} draft lands in {folder}, "
            f"but the executor writes it to {names.get(area)}"
        )


def test_airtable_row_tables_match_the_executor_table_map() -> None:
    """The Airtable Row Writer carries its own copy of AIRTABLE_ROW_TABLES.

    n8n cannot import the vault, so Build 17's Validate and Plan node holds the
    same table allowlist inline: the table id, the two stamp fields and the
    writable fields. The repo copy of that node lives under
    ``n8n/devon/airtable-row-writer/``. If the two drift, DEVON writes a row
    into a table or a field the vault does not permit and nothing else
    notices. This pins them together, and pins the base id to AIRTABLE.
    """
    from services.devon import vault

    source = pathlib.Path(__file__).parent / "n8n" / "devon" / "airtable-row-writer" / "validate_and_plan.js"
    assert source.exists(), f"{source} is missing; the executor source must live in the repo"
    body = source.read_text(encoding="utf-8")

    base = re.search(r"const BASE = '([^']+)';", body)
    assert base, "BASE not found in the executor source"
    assert base.group(1) == vault.AIRTABLE["live_base"], "the executor writes to a base the vault does not name as live"

    block = re.search(r"const TABLES = \{(.*?)\n\};", body, re.S)
    assert block, "TABLES map not found in the executor source"
    tables = {}
    for name, entry in re.findall(r"'([^']+)': \{\s*\n(.*?)\n  \}", block.group(1), re.S):
        table_id = re.search(r"id: '([^']+)'", entry)
        key_field = re.search(r"key_field: '([^']+)'", entry)
        job_field = re.search(r"job_field: '([^']+)'", entry)
        rules = re.search(r"rules: \{(.*?)\n    \}", entry, re.S)
        assert table_id and key_field and job_field and rules, f"table {name} is missing id, stamp fields or rules"
        writable = tuple(re.findall(r"'([^']+)': \{ kind:", rules.group(1)))
        tables[name] = {
            "id": table_id.group(1),
            "key_field": key_field.group(1),
            "job_field": job_field.group(1),
            "writable": writable,
        }
    assert tables, "no tables parsed from the executor source"
    assert tables == vault.AIRTABLE_ROW_TABLES, (
        "the executor's table allowlist and vault.AIRTABLE_ROW_TABLES disagree; change both or neither"
    )
    for name, entry in tables.items():
        assert vault.AIRTABLE["tables"].get(name) == entry["id"], (
            f"table {name} is on the row writer's allowlist with id {entry['id']} but AIRTABLE.tables records it differently"
        )
        assert entry["key_field"] not in entry["writable"] and entry["job_field"] not in entry["writable"], (
            f"table {name} lets the job set a stamp field; the executor must own both stamps"
        )


def test_action_router_allowlist_matches_the_vault_state() -> None:
    """Every allowlisted action names a workflow the vault records.

    The router dispatches only to the names in TARGETS. A name that reaches
    production without a vault entry is a capability nobody wrote down.
    """
    from services.devon import vault

    source = pathlib.Path(__file__).parent / "n8n" / "devon" / "action-router" / "authorise_and_resolve_target.js"
    assert source.exists(), f"{source} is missing; the router source must live in the repo"
    body = source.read_text(encoding="utf-8")

    targets = dict(re.findall(r"'([a-z.]+)':\s*\{[^}]*?workflow_id:\s*'([^']+)'", body, re.S))
    assert targets, "no TARGETS entries found in the router source"

    known = {entry["id"] for entry in vault.WORKFLOWS.values()}
    for action, workflow_id in targets.items():
        assert workflow_id in known, f"action {action} dispatches to unregistered workflow {workflow_id}"

    ceilings = dict(
        re.findall(r"'([a-z.]+)':\s*\{[^}]*?max_blast_radius:\s*'([^']+)'", body, re.S)
    )
    router_state = vault.WORKFLOWS["Action Router"]["state"]
    for action in targets:
        assert action in router_state, f"action {action} is live but the vault state does not name it"
        ceiling = ceilings.get(action)
        assert ceiling, f"action {action} has no ceiling in the router source"
        assert ceiling in router_state, (
            f"action {action} dispatches at ceiling {ceiling}, which the vault state does not record"
        )
