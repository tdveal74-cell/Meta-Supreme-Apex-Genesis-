"""The lesson registry refuses anything that is not a lesson Tee declared.

Ruled by Tee 2026-10-08, Phase 0 of
docs/devon/SYS_SPEC_learning-lane-grouping_v1_2026-10-07.md. Nothing here
touches a network: the module is pure data and validation, and the seed
script and the data table arrive in Phase 3.

Sample secrets in this file are assembled at run time from fragments, so no
complete secret shape is ever written down in the repository.
"""

from __future__ import annotations

import ast
import hashlib
import json
import pathlib
import re
import time

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
        ({"lesson_key": "read-receipts-before-trust\n"}, "lower case slug"),
        ({"claim": "too short"}, "outside 40 to 600"),
        ({"claim": "x" * 601}, "outside 40 to 600"),
        ({"claim": "A claim that runs on and on.\nThen breaks onto a second line here."}, "one line"),
        ({"claim": "A claim that runs on and on.\rThen breaks onto a second line here."}, "one line"),
        ({"claim": "A claim that runs on and on.\u2028Then breaks onto a second line here."}, "one line"),
        ({"claim": "A claim that runs on and on.\vThen breaks onto a second line here."}, "one line"),
        ({"claim": " A claim that is long enough to pass the length rule easily. "}, "whitespace"),
        ({"area": "systems"}, "is not one of"),
        ({"area": "SYS"}, "is not one of"),
        ({"scope": "Systems"}, "scope"),
        ({"min_sources": 1}, "min_sources"),
        ({"min_sources": 6}, "min_sources"),
        ({"min_sources": True}, "min_sources"),
        ({"status": "draft"}, "status"),
        ({"declared_on": "8 Oct 2026"}, "declared_on"),
        ({"declared_on": "2026-10-08\n"}, "declared_on"),
        ({"declared_on": "2026-13-45"}, "declared_on"),
        ({"declared_on": "\u0662\u0660\u0662\u0666-10-08"}, "declared_on"),
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


@pytest.mark.parametrize(
    "label, sample",
    [
        ("a private key block", "-----BEG" + "IN PRIVATE KEY-----"),
        ("a private key block", "-----BEG" + "IN OPENSSH PRIVATE KEY-----"),
        ("a GitHub token", "gh" + "o_" + "Ab3" * 12),
        ("a GitHub token", "gh" + "s_" + "Ab3" * 12),
        ("a Slack token", "xo" + "xp-" + "1234567890-abcdef"),
        ("an x-devon-key value", "x-devon-" + "key=" + "s3cr3tV4lue"),
        ("an OpenAI style key", "caf\u00e9" + "s" + "k-" + "proj" + "Ab3" * 12),
    ],
)
def test_the_other_forms_of_each_shape_are_caught_by_their_own_label(label, sample):
    assert reg.likely_secret("Before this step " + sample + " was pasted.") == label


def test_every_shape_has_a_sample():
    assert sorted(_samples()) == sorted(label for label, _ in reg.SECRET_SHAPES)


@pytest.mark.parametrize("label", sorted(_samples()))
def test_each_secret_shape_is_caught(label):
    text = "Before this step " + _samples()[label] + " was pasted."
    assert reg.likely_secret(text) == label
    entry = lesson(claim="A claim that carries a secret: " + _samples()[label] + " here.")
    assert any("shaped like" in p for p in reg.problems(entry))


@pytest.mark.parametrize(
    "text",
    [
        "Read the risk-free task-list before the disk-check runs on the VPS.",
        "Filed under task-receipts-are-read-before-every-trust-decision as the slug.",
        "Ticket sk-1042 was closed after the review.",
        "The header eyJhbGciOiJIUzI1NiJ9. decodes to alg HS256 and nothing else.",
        "Use bearer tokens, not cookies, for the soul service.",
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
    # The gate file is in the repo from Phase 1, so a missing file or a
    # renamed list is a failure, never a skip, and a shape commented out of
    # the list does not count as carried.
    assert GATE_PREFLIGHT.exists(), "the gate preflight is missing from the repo"
    text = GATE_PREFLIGHT.read_text()
    block = re.search(r"const SECRET_SHAPES = \[(.*?)\n\];", text, re.S)
    assert block is not None, "the gate preflight no longer carries const SECRET_SHAPES"
    live = "\n".join(line for line in block.group(1).splitlines() if not line.lstrip().startswith("//"))
    js = re.findall(r'\["([^"]+)", String\.raw`([^`]+)`\]', live)
    entries = [line for line in live.splitlines() if line.strip().startswith("[")]
    assert len(entries) == len(js), "the gate carries a shape this pin cannot read"
    assert js == list(reg.SECRET_SHAPES)
    assert "SECRET_SHAPES)" in text.replace(" ", ""), "the gate no longer loops over the shapes it declares"


def test_the_token_shape_stays_linear_on_hostile_text():
    """Text made of "eyJ-" repeated went quadratic under a word boundary.

    Measured 2026-10-08: 100 KB held the gate's preflight for seven seconds.
    The old pattern took 3.1 s in Python on half this text; the lookbehind
    allows one start per run, so the same text scans at once.
    """
    started = time.monotonic()
    assert reg.likely_secret("eyJ-" * 50000) is None
    assert time.monotonic() - started < 2.0
    jwt = _samples()["a JSON web token"]
    for text in ("key " + jwt, "X-N8N-API-KEY: " + jwt, jwt, "(" + jwt + ")"):
        assert reg.likely_secret(text) == "a JSON web token", text


# ---- a session's draft claim --------------------------------------------

EVIDENCE = [
    "VPS cutover verification: one real job driven end to end on the VPS",
    "Tee verified the output end to end and approved card REQ-20260916-J1ApUy at 2026-09-16T02:02:49.955Z.",
    "verify_card REQ-20260916-J1ApUy approved by Tee",
]


def test_a_draft_with_a_number_the_jobs_never_held_is_refused():
    claim = "Driving one job end to end on the VPS took 120-30% longer than on Cloud."
    found = reg.draft_claim_problems(claim, EVIDENCE)
    assert any("'120-30%'" in p for p in found)


def test_the_recorded_dash_rewrite_is_refused_with_its_own_source_in_the_evidence():
    """CLAUDE.md's first law table: "120 [dash] 30% above my last one" became "120-30%".

    The source sentence is in the evidence this time, so both numbers are
    there on their own and only the stitched expression is not.
    """
    source = ["Tee said the new rate is 120 \u2014 30% above my last one."]
    found = reg.draft_claim_problems("The rate became 120-30% of the last one.", source)
    assert found == ["the number '120-30%' appears in no named job's ledger text"]
    assert reg.draft_claim_problems("The rate is 120, which is 30% above the last one.", source) == []


@pytest.mark.parametrize(
    "claim, evidence",
    [
        ("Driving it took 20 minutes.", EVIDENCE),
        ("It ran 5 separate checks.", EVIDENCE),
        ("It passed 95% of the time.", EVIDENCE),
        ("It moved 120 rows.", ["It moved 1200 rows."]),
        ("It used 0.5 of the budget.", ["It used 0.55 of the budget."]),
        ("It filled 30% of the table.", ["It filled 30 rows of the table."]),
        ("It took 5 seconds.", ["It took 1.5 seconds."]),
    ],
)
def test_a_number_is_read_whole_and_never_found_inside_another(claim, evidence):
    assert reg.draft_claim_problems(claim, evidence), claim


@pytest.mark.parametrize(
    "claim",
    [
        "Tee said 'ship it' on the card.",
        "Tee said \u2018ship it\u2019 on the card.",
        "Tee said \u201cship it\" on the card.",
        "Tee said \"ship it\u201d on the card.",
        "Tee said \u201cship it\u201d on the card.",
        "Tee said \u00abship it\u00bb on the card.",
        "Tee said \u201eship it\u201c on the card.",
        "Tee said \"Approved By Tee\" on the card.",
    ],
)
def test_every_form_of_quotation_is_checked_verbatim(claim):
    found = reg.draft_claim_problems(claim, EVIDENCE)
    assert any(p.startswith("the quoted words") for p in found), (claim, found)
    assert "the draft opens a quotation it never closes" not in found


def test_an_unclosed_quotation_is_refused_and_an_apostrophe_is_not_a_quotation():
    assert reg.draft_claim_problems('Tee said "ship it and left.', EVIDENCE) == [
        "the draft opens a quotation it never closes"
    ]
    assert reg.draft_claim_problems("Don't call it done until Tee's card reads what's approved.", EVIDENCE) == []


def test_a_draft_quoting_words_the_jobs_never_held_is_refused():
    claim = 'A job is only done when Tee says "ship it" on the verify card.'
    found = reg.draft_claim_problems(claim, EVIDENCE)
    assert any("ship it" in p for p in found)


def test_a_draft_built_from_the_jobs_own_words_passes():
    claim = 'A job is "driven end to end" only when its verify card is approved, as on 2026-09-16.'
    assert reg.draft_claim_problems(claim, EVIDENCE) == []


def test_the_module_imports_nothing_outside_the_standard_library_and_the_canon():
    """Every import node in the tree, at any depth, comma lists included."""
    tree = ast.parse((ROOT / "services" / "devon" / "lesson_registry.py").read_text())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
    allowed = {"__future__", "datetime", "hashlib", "json", "re", "dataclasses", "typing", "services.devon.areas"}
    assert imports <= allowed, imports - allowed
