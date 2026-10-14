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


@pytest.mark.parametrize("addr", [
    "<a@b.co>", "a@b.co>", "a@b.", "a@.b", "a@b..co", "a@b,c.co",
    "a\x01@b.co", "a@b.co\u200b", "\u200ba@b.co", "a@b.co,c@d.co", "a@b.co;c@d.co",
    'a"b@c.co', "a@b.c", "a@-b.co", "a@b-.co", "a@b.co\r\nBcc: x@y.co", "a@" + "b" * 250 + ".co",
])
def test_the_email_shape_refuses_what_a_mail_header_could_not_carry(addr):
    with pytest.raises(QueueRefusal, match="email"):
        create_lead_draft(**{**GOOD, "contact_email": addr})


@pytest.mark.parametrize("addr", ["jordan@example.com", "j.lee+tag@sub.example.co.uk", "o'brien@example.org",
                                  "\u00e9mile@example.fr"])
def test_ordinary_addresses_still_pass(addr):
    assert create_lead_draft(**{**GOOD, "contact_email": addr}).contact_email == addr


@pytest.mark.parametrize("name", ["Bob\r\nBcc: evil@x.co", "Bob\nX", "Bo\u200bb", "Bob\x01", "Bob\u202eevil"])
def test_a_contact_name_with_control_or_invisible_characters_is_refused(name):
    with pytest.raises(QueueRefusal, match="contact_name"):
        create_lead_draft(**{**GOOD, "contact_name": name})


def test_a_plain_name_with_a_hyphen_or_accent_passes():
    assert create_lead_draft(**{**GOOD, "contact_name": "Anne-Marie O\u2019Neil"}).contact_name


@pytest.mark.parametrize("ch", ["\ufe31", "\ufe32"])
def test_the_vertical_em_and_en_dashes_are_refused(ch):
    with pytest.raises(QueueRefusal, match="dash"):
        create_lead_draft(**{**GOOD, "reply_text": f"before {ch} after the rest"})


@pytest.mark.parametrize("value", [None, "", "   ", "\n\t "])
def test_a_one_to_one_email_needs_no_disclosure(value):
    """Ruled by Tee 2026-10-14, against the recommendation to keep requiring it."""
    d = create_lead_draft(**{**GOOD, "ai_disclosure": value})
    assert d.ai_disclosure is None and d.status is DraftStatus.DRAFTED


def test_the_disclosure_may_be_left_out_entirely():
    kwargs = {k: v for k, v in GOOD.items() if k != "ai_disclosure"}
    assert create_lead_draft(**kwargs).ai_disclosure is None


@pytest.mark.parametrize("value", ["AI", ".", "\u200b" * 20, "\u2800" * 12, "\u3164" * 12])
def test_a_disclosure_that_is_given_must_still_be_real(value):
    with pytest.raises(QueueRefusal, match="ai_disclosure"):
        create_lead_draft(**{**GOOD, "ai_disclosure": value})


def test_a_given_disclosure_is_kept_as_written():
    d = create_lead_draft(**{**GOOD, "ai_disclosure": "Drafted with AI, sent by Tee."})
    assert d.ai_disclosure == "Drafted with AI, sent by Tee."
