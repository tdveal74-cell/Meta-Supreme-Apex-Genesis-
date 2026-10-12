"""Product proposals queue rules. Pure, no database."""

from __future__ import annotations

import ast
import pathlib

import pytest

from services.company.marketing import DraftStatus, QueueRefusal
from services.company.product import approve, create_proposal, reject, title_key

ROOT = pathlib.Path(__file__).resolve().parent
GOOD = dict(
    draft_id="p1",
    title="Weekly revenue digest",
    problem="Revenue is not visible anywhere except inside Stripe.",
    proposal="Read the month total into the scoreboard and send one line a week.",
    acceptance_check="The scoreboard revenue equals the Stripe dashboard total to the cent.",
    reference_artifact="services/company/scoreboard.py",
    size="small",
)


def test_a_clean_proposal_is_queued_as_drafted():
    p = create_proposal(**GOOD)
    assert p.status is DraftStatus.DRAFTED and p.decided_by is None
    assert p.title_key == title_key(GOOD["title"])


@pytest.mark.parametrize("field,value,match", [
    ("title", "abc", "visible characters"),
    ("title", "x" * 201, "longer than"),
    ("title", "Bad title here", "control or invisible"),
    ("title", "Bad\ntitle here", "control or invisible"),
    ("problem", "short", "visible characters"),
    ("proposal", "short", "visible characters"),
    ("acceptance_check", "short", "visible characters"),
    ("acceptance_check", "   ", "empty"),
    ("reference_artifact", "short", "visible characters"),
    ("reference_artifact", "​" * 20, "visible characters"),
    ("size", "huge", "size"),
    ("size", "", "size"),
])
def test_bad_fields_are_refused_with_a_named_reason(field, value, match):
    with pytest.raises(QueueRefusal, match=match):
        create_proposal(**{**GOOD, field: value})


@pytest.mark.parametrize("ch", ["—", "–", "―", "－", "︱", "︲"])
def test_dashes_and_lookalikes_are_refused_in_the_prose_fields(ch):
    for field in ("title", "problem", "proposal"):
        with pytest.raises(QueueRefusal, match="dash"):
            create_proposal(**{**GOOD, field: f"before {ch} after the rest"})


@pytest.mark.parametrize("field", ["draft_id", "title", "problem", "proposal",
                                   "acceptance_check", "reference_artifact"])
def test_a_nul_byte_is_refused_everywhere(field):
    with pytest.raises(QueueRefusal, match="NUL"):
        create_proposal(**{**GOOD, field: "a\x00b valid text here"})


def test_the_title_key_ignores_case_and_spacing_but_not_wording():
    assert title_key("A  Title here") == title_key("a title here")
    assert title_key("a title here") != title_key("a title there")


def test_a_large_proposal_cannot_be_approved_without_a_note():
    p = create_proposal(**{**GOOD, "size": "large"})
    for note in (None, "", "ok", "​" * 20):
        with pytest.raises(QueueRefusal, match="large"):
            approve(p, "Tee", note)
    assert approve(p, "Tee", "Taking this on knowingly, two weeks.").status is DraftStatus.APPROVED


def test_a_large_proposal_can_be_rejected_without_a_note():
    assert reject(create_proposal(**{**GOOD, "size": "large"}), "Tee").status is DraftStatus.REJECTED


@pytest.mark.parametrize("size", ["small", "medium"])
def test_smaller_proposals_need_no_note_to_approve(size):
    assert approve(create_proposal(**{**GOOD, "size": size}), "Tee").status is DraftStatus.APPROVED


def test_approval_needs_a_named_human():
    p = create_proposal(**GOOD)
    with pytest.raises(QueueRefusal, match="named decider"):
        approve(p, " ")
    for bot in ("Claude", "agent", "SYSTEM", "devon"):
        with pytest.raises(QueueRefusal, match="automated"):
            approve(p, bot)


def test_a_decided_proposal_cannot_be_decided_again():
    p = create_proposal(**GOOD)
    with pytest.raises(QueueRefusal, match="already rejected"):
        approve(reject(p, "Tee"), "Tee")
    with pytest.raises(QueueRefusal, match="already approved"):
        reject(approve(p, "Tee"), "Tee")


def test_the_module_cannot_reach_the_network_or_run_anything():
    tree = ast.parse((ROOT / "services" / "company" / "product.py").read_text())
    banned = {"socket", "subprocess", "httpx", "requests", "urllib", "aiohttp", "http",
              "smtplib", "imaplib", "os", "shutil", "git"}
    for node in ast.walk(tree):
        mods = []
        if isinstance(node, ast.Import):
            mods = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods = [node.module.split(".")[0]]
        assert not banned & set(mods)
