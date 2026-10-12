"""Sales approval queue rules. Pure, no database.

Ruled by Tee 2026-10-12: leads arrive as email or form replies, the agent
qualifies and drafts, nothing is sent without him. These pin the refusals and
that the module cannot reach a mail system.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from services.company.marketing import DraftStatus, QueueRefusal
from services.company.sales import (
    Qualification,
    approve,
    create_lead_draft,
    reject,
)

ROOT = pathlib.Path(__file__).resolve().parent
GOOD = dict(
    draft_id="l1",
    source="email",
    contact_name="Jordan Lee",
    contact_email="jordan@example.com",
    inbound_excerpt="I am a mid-career PM worried about AI. Do you coach?",
    qualification="qualified",
    qualification_reason="Mid-career professional asking about AI career strategy.",
    reply_text="Thanks for writing. The Quiet Operator covers exactly this.",
    ai_disclosure="Drafted with AI, sent by Tee.",
)


def test_a_clean_lead_draft_is_queued_as_drafted():
    d = create_lead_draft(**GOOD)
    assert d.status is DraftStatus.DRAFTED and d.qualification is Qualification.QUALIFIED
    assert d.decided_by is None


def test_the_inbound_excerpt_may_contain_dashes_because_it_is_the_leads_own_words():
    d = create_lead_draft(**{**GOOD, "inbound_excerpt": "Worried — really – about AI."})
    assert "—" in d.inbound_excerpt


@pytest.mark.parametrize("field,value,match", [
    ("source", "sms", "source"),
    ("source", "", "source"),
    ("qualification", "maybe", "qualification"),
    ("qualification_reason", "short", "visible characters"),
    ("qualification_reason", "​" * 20, "visible characters"),
    ("contact_email", "not-an-email", "email"),
    ("contact_email", "a@b", "email"),
    ("contact_email", "a b@example.com", "email"),
    ("contact_email", "a@@example.com", "email"),
    ("ai_disclosure", "AI", "visible characters"),
    ("ai_disclosure", "", "empty"),
])
def test_bad_fields_are_refused_with_a_named_reason(field, value, match):
    with pytest.raises(QueueRefusal, match=match):
        create_lead_draft(**{**GOOD, field: value})


@pytest.mark.parametrize("ch", ["—", "–", "―", "－"])
def test_dashes_and_lookalikes_are_refused_in_the_reply_and_disclosure(ch):
    for field in ("reply_text", "ai_disclosure"):
        with pytest.raises(QueueRefusal, match="dash"):
            create_lead_draft(**{**GOOD, field: f"before {ch} after the rest"})


@pytest.mark.parametrize("field", ["draft_id", "contact_name", "contact_email", "inbound_excerpt",
                                   "qualification_reason", "reply_text", "ai_disclosure"])
def test_a_nul_byte_is_refused_everywhere(field):
    with pytest.raises(QueueRefusal, match="NUL"):
        create_lead_draft(**{**GOOD, field: "a\x00b valid text here"})


def test_approval_needs_a_named_human():
    d = create_lead_draft(**GOOD)
    with pytest.raises(QueueRefusal, match="named decider"):
        approve(d, " ")
    for bot in ("Claude", "agent", "SYSTEM", "marketing"):
        with pytest.raises(QueueRefusal, match="automated"):
            approve(d, bot)


def test_approval_records_the_human_and_does_not_mutate_the_draft():
    d = create_lead_draft(**GOOD)
    a = approve(d, "Tee", "send it")
    assert a.status is DraftStatus.APPROVED and a.decided_by == "Tee"
    assert d.status is DraftStatus.DRAFTED


def test_a_decided_draft_cannot_be_decided_again():
    d = create_lead_draft(**GOOD)
    with pytest.raises(QueueRefusal, match="already rejected"):
        approve(reject(d, "Tee"), "Tee")
    with pytest.raises(QueueRefusal, match="already approved"):
        reject(approve(d, "Tee"), "Tee")


def test_the_module_cannot_reach_a_mail_system():
    tree = ast.parse((ROOT / "services" / "company" / "sales.py").read_text())
    banned = {"socket", "subprocess", "httpx", "requests", "urllib", "aiohttp", "http", "smtplib", "imaplib"}
    for node in ast.walk(tree):
        mods = []
        if isinstance(node, ast.Import):
            mods = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods = [node.module.split(".")[0]]
        assert not banned & set(mods)
