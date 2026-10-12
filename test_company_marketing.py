"""Marketing approval queue rules. Pure, no database.

Ruled by Tee 2026-10-12: draft and queue only. These pin the refusals and that
the module cannot reach a platform.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from services.company.marketing import (
    DraftStatus,
    QueueRefusal,
    approve,
    create_draft,
    reject,
)

ROOT = pathlib.Path(__file__).resolve().parent
GOOD = dict(draft_id="d1", show="TQO", episode_ref="ep-12", platform="youtube_community",
            text="New episode: three steps to audit your role for AI risk.",
            ai_disclosure="Made with AI voice and avatar.")


def test_a_clean_draft_enters_the_queue_as_drafted():
    d = create_draft(**GOOD)
    assert d.status is DraftStatus.DRAFTED and d.decided_by is None


@pytest.mark.parametrize("disclosure", ["", "   "])
def test_no_disclosure_is_refused(disclosure):
    with pytest.raises(QueueRefusal, match="AI disclosure"):
        create_draft(**{**GOOD, "ai_disclosure": disclosure})


@pytest.mark.parametrize("field", ["text", "ai_disclosure"])
@pytest.mark.parametrize("dash", ["—", "–"])
def test_dashes_are_refused_in_text_and_disclosure(field, dash):
    with pytest.raises(QueueRefusal, match="dash"):
        create_draft(**{**GOOD, field: f"before {dash} after"})


def test_empty_identity_fields_are_refused():
    for f in ("draft_id", "show", "episode_ref", "platform", "text"):
        with pytest.raises(QueueRefusal):
            create_draft(**{**GOOD, f: " "})


def test_approval_needs_a_named_human():
    d = create_draft(**GOOD)
    with pytest.raises(QueueRefusal, match="named decider"):
        approve(d, "")
    for bot in ("Claude", "agent", "AUTO", "marketing"):
        with pytest.raises(QueueRefusal, match="automated"):
            approve(d, bot)


def test_approval_records_the_human_and_does_not_mutate_the_draft():
    d = create_draft(**GOOD)
    a = approve(d, "Tee", "ok")
    assert a.status is DraftStatus.APPROVED and a.decided_by == "Tee"
    assert d.status is DraftStatus.DRAFTED


def test_a_decided_draft_cannot_be_decided_again():
    d = create_draft(**GOOD)
    r = reject(d, "Tee")
    with pytest.raises(QueueRefusal, match="already rejected"):
        approve(r, "Tee")
    with pytest.raises(QueueRefusal, match="already approved"):
        reject(approve(d, "Tee"), "Tee")


def test_the_module_cannot_reach_a_platform():
    tree = ast.parse((ROOT / "services" / "company" / "marketing.py").read_text())
    banned = {"socket", "subprocess", "httpx", "requests", "urllib", "aiohttp", "http"}
    for node in ast.walk(tree):
        mods = []
        if isinstance(node, ast.Import):
            mods = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods = [node.module.split(".")[0]]
        assert not banned & set(mods)


def test_a_nul_byte_is_refused_in_every_text_field():
    for field in ("text", "ai_disclosure", "show", "episode_ref", "platform", "draft_id"):
        with pytest.raises(QueueRefusal, match="NUL"):
            create_draft(**{**GOOD, field: "a\x00b"})


@pytest.mark.parametrize("ch", ["\u2012", "\u2015", "\u2e3a", "\u2e3b", "\ufe31", "\ufe32", "\ufe58", "\ufe63", "\uff0d"])
def test_dash_lookalikes_are_refused_in_text_and_disclosure(ch):
    for field in ("text", "ai_disclosure"):
        with pytest.raises(QueueRefusal, match="dash"):
            create_draft(**{**GOOD, field: f"before {ch} after the rest"})


def test_the_minus_sign_is_still_allowed_so_arithmetic_works():
    d = create_draft(**{**GOOD, "text": "Cut 5 \u2212 2 steps from the checklist."})
    assert d.status is DraftStatus.DRAFTED


@pytest.mark.parametrize("junk", [".", "AI", "\u200b", "\u200b\u200b\u200b\u200b\u200b\u200b\u200b\u200b\u200b\u200b\u200b", "a\u200bb\u200bc\u200b", "         x         "])
def test_a_disclosure_with_under_ten_visible_characters_is_refused(junk):
    with pytest.raises(QueueRefusal, match="visible characters"):
        create_draft(**{**GOOD, "ai_disclosure": junk})


def test_the_ten_visible_character_boundary_is_exact():
    ten = "Made with AI"  # 10 visible characters, the space does not count
    nine = "Made wit AI"  # 9
    assert create_draft(**{**GOOD, "ai_disclosure": ten}).ai_disclosure == ten
    with pytest.raises(QueueRefusal, match="visible characters"):
        create_draft(**{**GOOD, "ai_disclosure": nine})
