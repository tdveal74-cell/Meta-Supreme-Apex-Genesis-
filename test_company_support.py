"""Support approval queue rules. Pure, no database.

Ruled by Tee 2026-10-12: audience questions arrive as YouTube comments, the
agent drafts the reply, nothing is posted without him. These pin the refusals
and that the module cannot reach the network.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from services.company.marketing import DraftStatus, QueueRefusal
from services.company.support import approve, create_comment_draft, reject

ROOT = pathlib.Path(__file__).resolve().parent
GOOD = dict(
    draft_id="c1",
    video_id="dQw4w9WgXcQ",
    comment_id="UgxABC123_-xyz",
    commenter_name="Jordan Lee",
    comment_text="Does the checklist work for a non-technical manager?",
    reply_text="Yes. Steps one to three need no code. Step four is optional.",
    reply_basis="Episode script, checklist section, steps one to four.",
    ai_disclosure="Drafted with AI, posted by Tee.",
)


def test_a_clean_comment_draft_is_queued_as_drafted():
    d = create_comment_draft(**GOOD)
    assert d.status is DraftStatus.DRAFTED and d.decided_by is None


def test_the_viewers_comment_may_contain_dashes_because_it_is_their_own_words():
    d = create_comment_draft(**{**GOOD, "comment_text": "Wait — is this real – or not?"})
    assert "—" in d.comment_text


@pytest.mark.parametrize("field,value,match", [
    ("video_id", "short", "video_id"),
    ("video_id", "dQw4w9WgXcQ1", "video_id"),
    ("video_id", "dQw4w9 WgXc", "video_id"),
    ("video_id", "dQw4w9/WgXc", "video_id"),
    ("video_id", "", "video_id"),
    ("comment_id", "", "comment_id"),
    ("comment_id", "a b", "comment_id"),
    ("comment_id", "a.b.c", "comment_id"),
    ("comment_id", "a\nb", "comment_id"),
    ("comment_id", "a" * 65, "comment_id"),
    ("comment_text", "   ", "empty"),
    ("reply_basis", "short", "visible characters"),
    ("reply_basis", "​" * 20, "visible characters"),
    ("ai_disclosure", "AI", "visible characters"),
    ("ai_disclosure", "", "empty"),
])
def test_bad_fields_are_refused_with_a_named_reason(field, value, match):
    with pytest.raises(QueueRefusal, match=match):
        create_comment_draft(**{**GOOD, field: value})


@pytest.mark.parametrize("field,value", [
    ("video_id", "dQw4w9WgXcQ\n"),
    ("comment_id", "UgxABC123_-xyz\n"),
    ("comment_id", "UgxABC123.9xYz\n"),
    ("comment_id", ("a" * 64) + "." + ("b" * 64) + "\n"),
])
def test_a_trailing_newline_is_not_part_of_an_id(field, value):
    with pytest.raises(QueueRefusal, match=field):
        create_comment_draft(**{**GOOD, field: value})


@pytest.mark.parametrize("value", ["\u200b\u200b", "\u200b", "\u2060 \ufeff"])
def test_a_reply_with_no_visible_character_is_refused(value):
    with pytest.raises(QueueRefusal, match="no visible"):
        create_comment_draft(**{**GOOD, "reply_text": value})


def test_a_commenter_name_longer_than_the_column_is_a_refusal_not_a_database_error():
    with pytest.raises(QueueRefusal, match="longer than"):
        create_comment_draft(**{**GOOD, "commenter_name": "x" * 201})
    assert create_comment_draft(**{**GOOD, "commenter_name": "x" * 200})


def test_a_reply_id_is_the_parent_id_a_dot_and_a_suffix():
    assert create_comment_draft(**{**GOOD, "comment_id": "UgxABC123.9xYz_-1"}).comment_id


@pytest.mark.parametrize("ch", ["—", "–", "―", "－", "︱", "︲"])
def test_dashes_and_lookalikes_are_refused_in_the_reply_and_disclosure(ch):
    for field in ("reply_text", "ai_disclosure"):
        with pytest.raises(QueueRefusal, match="dash"):
            create_comment_draft(**{**GOOD, field: f"before {ch} after the rest"})


@pytest.mark.parametrize("field", ["draft_id", "commenter_name", "comment_text",
                                   "reply_text", "reply_basis", "ai_disclosure"])
def test_a_nul_byte_is_refused_everywhere(field):
    with pytest.raises(QueueRefusal, match="NUL"):
        create_comment_draft(**{**GOOD, field: "a\x00b valid text here"})


@pytest.mark.parametrize("name", ["Bob\r\nX", "Bo\u200bb", "Bob\x01", "Bob\u202eevil", "Bob\u2028X", "Bob\u2029X"])
def test_a_commenter_name_with_control_or_invisible_characters_is_refused(name):
    with pytest.raises(QueueRefusal, match="commenter_name"):
        create_comment_draft(**{**GOOD, "commenter_name": name})


def test_approval_needs_a_named_human():
    d = create_comment_draft(**GOOD)
    with pytest.raises(QueueRefusal, match="named decider"):
        approve(d, " ")
    for bot in ("Claude", "agent", "SYSTEM", "marketing"):
        with pytest.raises(QueueRefusal, match="automated"):
            approve(d, bot)


def test_approval_records_the_human_and_does_not_mutate_the_draft():
    d = create_comment_draft(**GOOD)
    a = approve(d, "Tee", "post it")
    assert a.status is DraftStatus.APPROVED and a.decided_by == "Tee"
    assert d.status is DraftStatus.DRAFTED


def test_a_decided_draft_cannot_be_decided_again():
    d = create_comment_draft(**GOOD)
    with pytest.raises(QueueRefusal, match="already rejected"):
        approve(reject(d, "Tee"), "Tee")
    with pytest.raises(QueueRefusal, match="already approved"):
        reject(approve(d, "Tee"), "Tee")


def test_the_module_cannot_reach_the_network():
    tree = ast.parse((ROOT / "services" / "company" / "support.py").read_text())
    banned = {"socket", "subprocess", "httpx", "requests", "urllib", "aiohttp", "http", "smtplib", "imaplib"}
    for node in ast.walk(tree):
        mods = []
        if isinstance(node, ast.Import):
            mods = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods = [node.module.split(".")[0]]
        assert not banned & set(mods)
