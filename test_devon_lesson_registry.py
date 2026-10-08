"""The lesson registry refuses anything that is not a lesson Tee declared.

Ruled by Tee 2026-10-08, Phase 0 of
docs/devon/SYS_SPEC_learning-lane-grouping_v1_2026-10-07.md. Nothing here
touches a network: the module is pure data and validation, and the seed
script and the data table arrive in Phase 3.

Sample secrets in this file are assembled at run time from fragments, so no
complete secret shape is ever written down in the repository.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re

import pytest

from services.devon import lesson_registry as reg
from services.devon.areas import canonical_labels

ROOT = pathlib.Path(__file__).resolve().parent
GATE_PREFLIGHT = ROOT / "n8n" / "devon" / "learning-gate" / "candidate_former.js"
FORM_JOB = ROOT / "n8n" / "devon" / "intake-former" / "form_job.js"

REAL_ID = "01M2KT8WM4RPZ90BCTZPVXH6HK"


def lesson(**changes) -> reg.Lesson:
    base = dict(
        lesson_key="read-receipts-before-trust",
        claim="Read the executor's own receipt back before reporting a job as done; a green status is not a result.",
        area="Systems",
        scope="system",
        min_sources=2,
        status="active",
        declared_on="2026-10-08",
        ruling_ref="test fixture, not a ruling",
        evidence_ids=(REAL_ID,),
    )
    base.update(changes)
    return reg.Lesson(**base)


def test_no_lesson_is_declared_yet_and_no_table_is_named():
    assert reg.LESSONS == ()
    assert reg.registry_problems() == []
    assert reg.registry_rows() == ()
    assert reg.REGISTRY_TABLES == {}


def test_a_well_formed_entry_has_no_problems():
    assert reg.problems(lesson()) == []


@pytest.mark.parametrize(
    "changes, expected",
    [
        ({"lesson_key": "Read Receipts"}, "lower case slug"),
        ({"lesson_key": "x" * 61}, "lower case slug"),
        ({"claim": "too short"}, "outside 40 to 600"),
        ({"claim": "x" * 601}, "outside 40 to 600"),
        ({"claim": "A claim that runs on and on.\nThen breaks onto a second line here."}, "one line"),
        ({"claim": " A claim that is long enough to pass the length rule easily. "}, "whitespace"),
        ({"area": "systems"}, "is not one of"),
        ({"area": "SYS"}, "is not one of"),
        ({"scope": "Systems"}, "scope"),
        ({"min_sources": 1}, "min_sources"),
        ({"min_sources": 6}, "min_sources"),
        ({"min_sources": True}, "min_sources"),
        ({"status": "draft"}, "status"),
        ({"declared_on": "8 Oct 2026"}, "declared_on"),
        ({"ruling_ref": "  "}, "ruling_ref"),
        ({"evidence_ids": ("SMOKETEST0FEEDER0000000000",)}, "is not a ULID"),
        ({"evidence_ids": (REAL_ID, REAL_ID.lower())}, "repeats a job"),
    ],
)
def test_each_bad_field_is_named(changes, expected):
    found = reg.problems(lesson(**changes))
    assert any(expected in p for p in found), found


def test_a_key_declared_twice_is_refused():
    found = reg.registry_problems([lesson(), lesson()])
    assert any("declared 2 times" in p for p in found)


def test_the_area_vocabulary_is_the_canon_and_matches_the_intake():
    """The registry takes the Area canon, and the intake must agree with it."""
    text = FORM_JOB.read_text()
    js = re.search(r"const AREAS = \[([^\]]*)\]", text)
    assert js, "form_job.js no longer declares AREAS"
    intake = re.findall(r"'([^']+)'", js.group(1))
    assert intake == canonical_labels()


def test_the_row_is_flat_and_carries_a_sha_of_the_exact_claim():
    entry = lesson(evidence_ids=(" " + REAL_ID.lower(),))
    row = entry.row()
    assert set(row) == {
        "lesson_key", "claim", "claim_sha", "area", "scope", "min_sources",
        "status", "evidence_ids", "declared_on", "ruling_ref",
    }
    assert row["claim_sha"] == hashlib.sha256(entry.claim.encode("utf-8")).hexdigest()
    assert json.loads(row["evidence_ids"]) == [REAL_ID]
    reworded = lesson(claim=entry.claim + " Always.")
    assert reworded.claim_sha != entry.claim_sha


# ---- secrets -------------------------------------------------------------

def _samples():
    """Secret shaped strings, assembled so none is written whole in the repo."""
    tail = "Ab3" * 12
    return {
        "a Pinecone key": "pc" + "sk_" + tail,
        "a console token": "ds" + "t_" + "0123456789abcdef" * 3,
        "a capture token": "dc" + "p_" + "claude_" + "f1" * 10,
        "an Anthropic key": "s" + "k-" + "ant-" + "api03-" + tail,
        "an OpenAI style key": "s" + "k-" + "proj" + tail,
        "a Cerebras key": "cs" + "k-" + tail,
        "an AWS access key id": "AK" + "IA" + "ABCDEFGHIJKLMNOP",
        "a private key block": "-----BEG" + "IN RSA PRIVATE KEY-----",
        "a Slack token": "xo" + "xb-" + "1234567890-abcdef",
        "a GitHub token": "gh" + "p_" + tail,
        "a Google API key": "AI" + "za" + tail,
        "an Airtable token": "pa" + "t" + "Ab3Cd4Ef5Gh6Ij" + "." + "0123456789abcdef" * 4,
        "a JSON web token": "ey" + "JhbGciOiJIUzI1NiJ9" + "." + "ey" + "JzdWIiOiJ0ZWUifQ" + "." + "sig",
        "a bearer credential": "Authorization: Bear" + "er " + "abcDEF123456ghiJKL789",
        "an x-devon-key value": "x-devon-" + "key: " + "s3cr3tV4lue",
    }


def test_every_shape_has_a_sample():
    assert sorted(_samples()) == sorted(label for label, _ in reg.SECRET_SHAPES)


@pytest.mark.parametrize("label", sorted(_samples()))
def test_each_secret_shape_is_caught(label):
    text = "Before this step " + _samples()[label] + " was pasted."
    assert reg.likely_secret(text) is not None, label
    entry = lesson(claim="A claim that carries a secret: " + _samples()[label] + " here.")
    assert any("shaped like" in p for p in reg.problems(entry))


@pytest.mark.parametrize(
    "text",
    [
        "Read the risk-free task-list before the disk-check runs on the VPS.",
        "File it under Drive folder 1DlobTD8LWKFfZzYNgaIr_7yRO-Rtj5RB in _Devon Core.",
        "The job " + REAL_ID + " wrote row recoe6wzzAdkKpEnj in tbl4ziFRbl5mnUcKc.",
        "https://airtable.com/app28z7XnKzjfTXwc/tbl4ziFRbl5mnUcKc/recoe6wzzAdkKpEnj",
        "Never paste a Bearer token or the x-devon-key header into a lesson.",
        "Completed job experience: VPS cutover verification. Area: Systems. Executor: n8n.",
        "Merged as ea6bcf8cb9e12acf9ef7344d711fcce0c5bd2ca3 after the gate went live as 17f51ee2.",
        "Ran under credential AgSGuaA2pnZsrZcJ and the Pinecone key credential YL4Q4rZ4yFssfQVy.",
    ],
)
def test_ordinary_lane_text_is_not_mistaken_for_a_secret(text):
    assert reg.likely_secret(text) is None, text


def test_the_gate_scans_with_exactly_these_shapes():
    """The gate's preflight carries the same shapes, in the same order.

    n8n cannot import this module, so the list is duplicated on purpose, the
    same way the folder and table maps are. If the two disagree, a claim the
    registry refuses could still be scanned clean at the gate, or the other
    way round.
    """
    if not GATE_PREFLIGHT.exists():
        pytest.skip("the gate preflight is not in the repo yet")
    text = GATE_PREFLIGHT.read_text()
    block = re.search(r"const SECRET_SHAPES = \[(.*?)\n\];", text, re.S)
    if block is None:
        pytest.skip("this version of the gate carries no secret scan")
    js = re.findall(r'\["([^"]+)", String\.raw`([^`]+)`\]', block.group(1))
    assert js == list(reg.SECRET_SHAPES)


# ---- a session's draft claim --------------------------------------------

EVIDENCE = [
    "VPS cutover verification: one real job driven end to end on the VPS",
    "Tee verified the output end to end and approved card REQ-20260916-J1ApUy at 2026-09-16T02:02:49.955Z.",
    "verify_card REQ-20260916-J1ApUy approved by Tee",
]


def test_a_draft_with_a_number_the_jobs_never_held_is_refused():
    claim = "Driving one job end to end on the VPS took 120-30% longer than on Cloud."
    found = reg.draft_claim_problems(claim, EVIDENCE)
    assert any("'120'" in p for p in found)
    assert any("'30'" in p for p in found)


def test_a_draft_quoting_words_the_jobs_never_held_is_refused():
    claim = 'A job is only done when Tee says "ship it" on the verify card.'
    found = reg.draft_claim_problems(claim, EVIDENCE)
    assert any("ship it" in p for p in found)


def test_a_draft_built_from_the_jobs_own_words_passes():
    claim = 'A job is "driven end to end" only when its verify card is approved, as on 2026-09-16.'
    assert reg.draft_claim_problems(claim, EVIDENCE) == []


def test_the_module_imports_nothing_outside_the_standard_library_and_the_canon():
    tree = (ROOT / "services" / "devon" / "lesson_registry.py").read_text()
    imports = set(re.findall(r"^(?:from|import) ([a-zA-Z_.]+)", tree, re.M))
    assert imports <= {"__future__", "hashlib", "json", "re", "dataclasses", "typing", "services.devon.areas"}, imports
