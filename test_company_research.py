"""Research findings queue rules. Pure, no database."""

from __future__ import annotations

import ast
import pathlib
import unicodedata

import pytest

from services.company.marketing import DraftStatus, QueueRefusal
from services.company.research import approve, claim_key, create_finding, reject

ROOT = pathlib.Path(__file__).resolve().parent
GOOD = dict(
    draft_id="f1",
    claim="Mid-career PMs search for AI career strategy more than for AI tools.",
    evidence_kind="source",
    evidence_ref="https://example.com/report?year=2026#section-3",
    evidence_excerpt="Searches for career strategy rose 40% year over year.",
    recommendation="Lead the next TQO episode with the career strategy angle.",
)


def test_a_clean_finding_is_queued_as_drafted():
    f = create_finding(**GOOD)
    assert f.status is DraftStatus.DRAFTED and f.decided_by is None
    assert f.claim_key == claim_key(GOOD["claim"])


def test_the_excerpt_may_contain_dashes_because_it_is_quoted_source_text():
    f = create_finding(**{**GOOD, "evidence_excerpt": "Up — sharply – in 2026."})
    assert "—" in f.evidence_excerpt


def test_the_excerpt_is_optional():
    assert create_finding(**{**GOOD, "evidence_excerpt": None}).evidence_excerpt is None
    assert create_finding(**{**GOOD, "evidence_excerpt": ""}).evidence_excerpt is None


@pytest.mark.parametrize("field,value,match", [
    ("claim", "short", "visible characters"),
    ("claim", "\u200b" * 20, "claim contains"),
    ("evidence_kind", "rumour", "evidence_kind"),
    ("evidence_kind", "", "evidence_kind"),
    ("evidence_ref", "short", "visible characters"),
    ("evidence_ref", "   ", "empty"),
    ("evidence_ref", "x" * 2001, "longer than"),
    ("recommendation", "short", "visible characters"),
    ("recommendation", "", "empty"),
])
def test_bad_fields_are_refused_with_a_named_reason(field, value, match):
    with pytest.raises(QueueRefusal, match=match):
        create_finding(**{**GOOD, field: value})


@pytest.mark.parametrize("ref", [
    "http://example.com/report",
    "ftp://example.com/report",
    "example.com/report/page",
    "https://example",
    "https://exa mple.com/page",
    "https://example.com/pa ge",
    "https://example.com/pa\nge",
    "https://example.com/page\r\nBcc: x",
    "https://example.com/<x>",
    "https://example.com/​page",
    "https://-example.com/page",
    "javascript:alert(1)//https://example.com",
])
def test_a_source_finding_needs_a_plain_https_url(ref):
    with pytest.raises(QueueRefusal, match="https URL"):
        create_finding(**{**GOOD, "evidence_ref": ref})


def test_surrounding_whitespace_is_stripped_before_the_url_is_stored():
    f = create_finding(**{**GOOD, "evidence_ref": "  https://example.com/page\n"})
    assert f.evidence_ref == "https://example.com/page"


@pytest.mark.parametrize("kind,ref", [
    ("measured", "pytest test_company_research.py, 41 passed, run 2026-10-12"),
    ("unverified", "Would need the channel analytics export to settle this."),
])
def test_measured_and_unverified_findings_take_free_text_references(kind, ref):
    assert create_finding(**{**GOOD, "evidence_kind": kind, "evidence_ref": ref}).evidence_kind == kind


@pytest.mark.parametrize("ch", ["—", "–", "―", "－", "︱", "︲"])
def test_dashes_and_lookalikes_are_refused_in_the_claim_and_recommendation(ch):
    for field in ("claim", "recommendation"):
        with pytest.raises(QueueRefusal, match="dash"):
            create_finding(**{**GOOD, field: f"before {ch} after the rest"})


@pytest.mark.parametrize("field", ["draft_id", "claim", "evidence_ref", "evidence_excerpt", "recommendation"])
def test_a_nul_byte_is_refused_everywhere(field):
    with pytest.raises(QueueRefusal, match="NUL"):
        create_finding(**{**GOOD, field: "a\x00b valid text here"})


def test_the_claim_key_ignores_case_and_spacing_but_not_wording():
    assert claim_key("A  Claim   here") == claim_key("a claim here")
    assert claim_key("a claim here") != claim_key("a claim there")


def test_an_unverified_finding_cannot_be_adopted_without_saying_so():
    f = create_finding(**{**GOOD, "evidence_kind": "unverified", "evidence_ref": "Needs the analytics export."})
    for note in (None, "", "ok", "​" * 20):
        with pytest.raises(QueueRefusal, match="unverified"):
            approve(f, "Tee", note)
    assert approve(f, "Tee", "Adopting as a lead, not a fact.").status is DraftStatus.APPROVED


def test_an_unverified_finding_can_be_dismissed_without_a_note():
    f = create_finding(**{**GOOD, "evidence_kind": "unverified", "evidence_ref": "Needs the analytics export."})
    assert reject(f, "Tee").status is DraftStatus.REJECTED


def test_a_sourced_finding_needs_no_note_to_adopt():
    assert approve(create_finding(**GOOD), "Tee").status is DraftStatus.APPROVED


def test_approval_needs_a_named_human():
    f = create_finding(**GOOD)
    with pytest.raises(QueueRefusal, match="named decider"):
        approve(f, " ")
    for bot in ("Claude", "agent", "SYSTEM", "marketing"):
        with pytest.raises(QueueRefusal, match="automated"):
            approve(f, bot)


def test_a_decided_finding_cannot_be_decided_again():
    f = create_finding(**GOOD)
    with pytest.raises(QueueRefusal, match="already rejected"):
        approve(reject(f, "Tee"), "Tee")
    with pytest.raises(QueueRefusal, match="already approved"):
        reject(approve(f, "Tee"), "Tee")


def test_the_module_cannot_reach_the_network():
    tree = ast.parse((ROOT / "services" / "company" / "research.py").read_text())
    banned = {"socket", "subprocess", "httpx", "requests", "urllib", "aiohttp", "http", "smtplib", "imaplib"}
    for node in ast.walk(tree):
        mods = []
        if isinstance(node, ast.Import):
            mods = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods = [node.module.split(".")[0]]
        assert not banned & set(mods)


def test_the_claim_key_folds_encoding_and_invisible_characters():
    base = "The caf\u00e9 price is 40 dollars"
    for same in (
        unicodedata.normalize("NFD", base),
        "The caf\u00e9 pri\u200bce is 40 dollars",
        "The caf\u00e9 price is 40 dollars\u00a0",
        "\uff34he caf\u00e9 price is 40 dollars",
    ):
        assert claim_key(same) == claim_key(base)
    assert claim_key("The cafe price is 40 dollars") != claim_key(base)


@pytest.mark.parametrize("claim", ["Claim\x07 long enough here", "Claim\nlong enough here",
                                   "Claim\u200b long enough here", "Claim\u2028long enough here"])
def test_a_claim_with_control_or_invisible_characters_is_refused(claim):
    with pytest.raises(QueueRefusal, match="claim contains"):
        create_finding(**{**GOOD, "claim": claim})


def test_claim_and_recommendation_are_stored_stripped():
    f = create_finding(**{**GOOD, "claim": "  A claim that is long enough.  ",
                          "recommendation": "\n  Do the thing, and do it well.  "})
    assert f.claim == "A claim that is long enough." and f.recommendation == "Do the thing, and do it well."


def test_a_nul_in_a_decision_note_is_a_refusal_not_a_database_error():
    f = create_finding(**GOOD)
    for fn in (approve, reject):
        with pytest.raises(QueueRefusal, match="NUL"):
            fn(f, "Tee", "bad\x00note")
