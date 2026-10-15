"""The Support knowledge base rules. Pure, no database.

Ruled by Tee 2026-10-15: replies take their facts from approved articles he
writes, and a reply with no article id is refused.
"""

from __future__ import annotations

import pytest

from services.company import marketing, support
from services.company.knowledge import (
    approve,
    check_article_id,
    create_article,
    reject,
    require_citable,
)
from services.company.marketing import DraftStatus, QueueRefusal

GOOD = dict(article_id="checklist-guide", title="The episode checklist",
            body="Steps one to three need no code. Step four is optional.")
DASHES = ["—", "–", "―", "‒", "－", "〜", "\U00010ead"]


def test_a_clean_article_is_a_draft():
    a = create_article(**GOOD)
    assert a.status is DraftStatus.DRAFTED and a.decided_by is None
    assert a.title == "The episode checklist"


@pytest.mark.parametrize("bad", [
    "", "a", "Checklist", "check list", "check_list", "-lead", "x" * 64, "café",
    "ok\n", "ok\r", "a/b", "../x", " ok", "ok ",
])
def test_article_ids_are_lowercase_slugs_only(bad):
    with pytest.raises(QueueRefusal, match="slug"):
        check_article_id(bad)


@pytest.mark.parametrize("good", ["ab", "checklist-guide", "a1", "x" * 63, "2026-q4-faq"])
def test_good_article_ids_pass(good):
    assert check_article_id(good) == good


@pytest.mark.parametrize("dash", DASHES)
@pytest.mark.parametrize("field", ["title", "body"])
def test_a_dash_in_the_title_or_body_is_refused(dash, field):
    with pytest.raises(QueueRefusal, match="dash"):
        create_article(**{**GOOD, field: f"before {dash} after the rest of it"})


@pytest.mark.parametrize("patch,needle", [
    ({"title": ""}, "empty"),
    ({"title": "   "}, "empty"),
    ({"title": "x" * 201}, "longer"),
    ({"title": "​" * 5}, "visible"),
    ({"body": "short"}, "visible characters"),
    ({"body": "⠀" * 40}, "visible characters"),
    ({"body": "a\x00b" + "c" * 30}, "NUL"),
    ({"body": ""}, "empty"),
])
def test_bad_titles_and_bodies_are_refused_with_a_reason(patch, needle):
    with pytest.raises(QueueRefusal, match=needle):
        create_article(**{**GOOD, **patch})


def test_hyphens_and_a_minus_sign_are_allowed():
    a = create_article(**{**GOOD, "body": "A well‐known five step list, 5 − 2 left, non‑stop."})
    assert a.status is DraftStatus.DRAFTED


def test_approval_needs_a_named_human_and_happens_once():
    a = create_article(**GOOD)
    for who in ("", "   ", "claude", "Agent", "DEVON", "system"):
        with pytest.raises(QueueRefusal):
            approve(a, who)
    done = approve(a, "tee@example.com", "Checked against the episode.")
    assert done.status is DraftStatus.APPROVED and done.decided_by == "tee@example.com"
    with pytest.raises(QueueRefusal, match="already approved"):
        reject(done, "tee@example.com")
    assert reject(a, "tee@example.com").status is DraftStatus.REJECTED


@pytest.mark.parametrize("dash", DASHES)
def test_a_dash_in_a_decision_note_is_refused(dash):
    with pytest.raises(QueueRefusal, match="dash"):
        approve(create_article(**GOOD), "tee@example.com", f"fine {dash} go")


def test_only_an_approved_article_is_citable():
    a = create_article(**GOOD)
    with pytest.raises(QueueRefusal, match="does not exist"):
        require_citable(None, "nope-nope")
    with pytest.raises(QueueRefusal, match="drafted"):
        require_citable(a, a.article_id)
    with pytest.raises(QueueRefusal, match="rejected"):
        require_citable(reject(a, "tee@example.com"), a.article_id)
    approved = approve(a, "tee@example.com")
    assert require_citable(approved, a.article_id) is approved


def test_a_support_draft_must_name_an_article_slug():
    base = dict(draft_id="d", video_id="dQw4w9WgXcQ", comment_id="Ugx1", commenter_name="Jo",
                comment_text="q?", reply_text="Yes, it works.", reply_basis="Episode script, section two.",
                ai_disclosure="Drafted with AI, posted by Tee.")
    with pytest.raises(TypeError):
        support.create_comment_draft(**base)
    for bad in ("", "Not A Slug", "ok\n"):
        with pytest.raises(QueueRefusal, match="slug"):
            support.create_comment_draft(**base, article_id=bad)
    assert support.create_comment_draft(**base, article_id="checklist-guide").article_id == "checklist-guide"


def test_the_shared_dash_list_is_what_the_article_rules_use():
    assert "\U00010ead" in marketing.BANNED_DASHES
