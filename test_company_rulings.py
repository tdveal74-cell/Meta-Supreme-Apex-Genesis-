"""Tee's rulings of 2026-10-14 and the visible character counter. Pure, no database.

Ruled: a one to one sales email needs no AI disclosure (tested in
test_company_sales.py); the dash rule covers decision notes, acceptance checks,
reference artifacts and measured references but not URLs or quoted text; the
hyphen look-alikes U+2010 and U+2011 stay allowed. The counter fix is not a
ruling: measured the same day, ten braille blanks, ten Hangul fillers and twelve
bare combining marks all counted as visible and cleared the 10 character floors.
"""

from __future__ import annotations

import pytest

from services.company import marketing, product, research, sales, support
from services.company.marketing import QueueRefusal, _visible_len

DASHES = ["—", "–", "―", "‒", "－", "︱", "﹘"]
BLANKS = ["\u2800", "\u3164", "\u115f", "\u1160", "\uffa0", "\u0301", "\u200b", "\u00a0", "\u2028",
          "\ufffc", "\U0001d159", "\u2065", "\ufff0", "\ufff8", "\U000e0002", "\U000e0080", "\ue000", "\U000f0000"]


@pytest.mark.parametrize("text,expected", [
    ("", 0),
    ("   ", 0),
    ("⠀" * 12, 0),
    ("ㅤ" * 12, 0),
    ("ᅟᅠﾠ", 0),
    ("́" * 12, 0),
    ("​" * 5, 0),
    ("é", 1),
    ("café", 4),
    ("café", 4),
    ("a b c", 3),
    ("Made with AI", 10),
    ("⠀" * 9 + "Made with AI", 10),
    ("x" * 10, 10),
    ("\ufffc" * 12, 0),
    ("\U0001d159" * 12, 0),
    ("\u2065\ufff0\ufff8\U000e0002\U000e0080", 0),
    ("\ue000" * 12, 0),
    ("\U0001f600" * 12, 12),
    ("\u2705" * 12, 12),
    ("\u4e2d\u6587" * 6, 12),
    ("\U0001f9d1\u200d\U0001f4bb", 2),
])
def test_the_counter_counts_what_a_reader_can_see(text, expected):
    assert _visible_len(text) == expected


@pytest.mark.parametrize("blank", BLANKS)
def test_ten_blank_looking_characters_do_not_clear_a_ten_character_floor(blank):
    junk = blank * 12
    with pytest.raises(QueueRefusal):
        marketing.create_draft(draft_id="d", show="TQO", episode_ref="ep-1", platform="youtube_community",
                               text="A real post about the episode.", ai_disclosure=junk)
    with pytest.raises(QueueRefusal):
        support.create_comment_draft(
            draft_id="d", video_id="dQw4w9WgXcQ", comment_id="Ugx1", commenter_name="Jo",
            comment_text="q?", reply_text="Yes, it works.", reply_basis=junk,
            ai_disclosure="Drafted with AI, posted by Tee.")
    with pytest.raises(QueueRefusal):
        research.create_finding(
            draft_id="f", claim=junk, evidence_kind="measured", evidence_ref="pytest run, 41 passed",
            evidence_excerpt=None, recommendation="Do the thing well.")
    with pytest.raises(QueueRefusal):
        product.create_proposal(
            draft_id="p", title="Weekly digest", problem="Revenue is hidden in Stripe.",
            proposal="Read the month total into the scoreboard.", acceptance_check=junk,
            reference_artifact="services/company/scoreboard.py", size="small")


def test_a_disclosure_that_is_one_character_short_is_still_refused_and_the_right_length_passes():
    base = dict(draft_id="d", show="TQO", episode_ref="ep-1", platform="youtube_community",
                text="A real post about the episode.")
    with pytest.raises(QueueRefusal, match="visible characters"):
        marketing.create_draft(**base, ai_disclosure="Made wit AI")
    assert marketing.create_draft(**base, ai_disclosure="Made with AI").ai_disclosure == "Made with AI"


# ---- the dash rule on decision notes, in every queue

def _drafts():
    return {
        "marketing": (marketing.create_draft(
            draft_id="d", show="TQO", episode_ref="ep-1", platform="youtube_community",
            text="A real post about the episode.", ai_disclosure="Made with AI"), marketing),
        "sales": (sales.create_lead_draft(
            draft_id="l", source="email", contact_name="Jordan Lee", contact_email="jordan@example.com",
            inbound_excerpt="Do you coach?", qualification="qualified",
            qualification_reason="Asked about career strategy.", reply_text="Thanks for writing."), sales),
        "support": (support.create_comment_draft(
            draft_id="c", video_id="dQw4w9WgXcQ", comment_id="Ugx1", commenter_name="Jo",
            comment_text="q?", reply_text="Yes, it works.", reply_basis="Episode script, section two.",
            ai_disclosure="Drafted with AI, posted by Tee."), support),
        "research": (research.create_finding(
            draft_id="f", claim="Career strategy searches rose in 2026.", evidence_kind="source",
            evidence_ref="https://example.com/report", evidence_excerpt=None,
            recommendation="Lead the next episode with it."), research),
        "product": (product.create_proposal(
            draft_id="p", title="Weekly digest", problem="Revenue is hidden in Stripe.",
            proposal="Read the month total into the scoreboard.",
            acceptance_check="The scoreboard equals the Stripe total.",
            reference_artifact="services/company/scoreboard.py", size="small"), product),
    }


@pytest.mark.parametrize("queue", ["marketing", "sales", "support", "research", "product"])
@pytest.mark.parametrize("dash", DASHES)
def test_a_dash_in_a_decision_note_is_refused_in_every_queue(queue, dash):
    draft, mod = _drafts()[queue]
    for fn in (mod.approve, mod.reject):
        with pytest.raises(QueueRefusal, match="dash"):
            fn(draft, "Tee", f"looks fine {dash} ship it")


@pytest.mark.parametrize("queue", ["marketing", "sales", "support", "research", "product"])
def test_notes_with_a_minus_sign_hyphens_or_no_note_are_still_accepted(queue):
    draft, mod = _drafts()[queue]
    assert mod.reject(draft, "Tee", "2026-10-14 − a minus sign, a-b, and a‐b").decision_note
    assert mod.reject(draft, "Tee").decision_note is None


# ---- the dash rule on checks, reference artifacts and measured references

PROD = dict(draft_id="p", title="Weekly digest", problem="Revenue is hidden in Stripe.",
            proposal="Read the month total into the scoreboard.",
            acceptance_check="The scoreboard equals the Stripe total.",
            reference_artifact="services/company/scoreboard.py", size="small")


@pytest.mark.parametrize("dash", DASHES)
def test_a_dash_in_an_acceptance_check_or_a_prose_reference_is_refused(dash):
    with pytest.raises(QueueRefusal, match="acceptance_check"):
        product.create_proposal(**{**PROD, "acceptance_check": f"it works {dash} measured against the total"})
    with pytest.raises(QueueRefusal, match="reference_artifact"):
        product.create_proposal(**{**PROD, "reference_artifact": f"the scoreboard file {dash} extended"})


def test_a_bare_url_reference_is_left_verbatim_even_with_a_dash_in_it():
    url = "https://example.com/docs/a–b/page"
    assert product.create_proposal(**{**PROD, "reference_artifact": url}).reference_artifact == url


def test_a_url_with_prose_around_it_is_prose():
    with pytest.raises(QueueRefusal, match="reference_artifact"):
        product.create_proposal(**{**PROD, "reference_artifact": "https://example.com/x — the docs page"})


FIND = dict(draft_id="f", claim="Career strategy searches rose in 2026.", evidence_excerpt=None,
            recommendation="Lead the next episode with it.")


@pytest.mark.parametrize("kind", ["measured", "unverified"])
@pytest.mark.parametrize("dash", DASHES)
def test_a_dash_in_a_measured_or_unverified_reference_is_refused(kind, dash):
    with pytest.raises(QueueRefusal, match="evidence_ref"):
        research.create_finding(**FIND, evidence_kind=kind, evidence_ref=f"pytest run {dash} 41 passed")


def test_a_source_url_is_left_verbatim_and_a_quoted_excerpt_still_may_carry_dashes():
    f = research.create_finding(
        **{**FIND, "evidence_excerpt": "Up — sharply – in 2026."},
        evidence_kind="source", evidence_ref="https://example.com/a–b/report")
    assert "–" in f.evidence_ref and "—" in f.evidence_excerpt


# ---- the hyphen look-alikes stay allowed

@pytest.mark.parametrize("hyphen", ["‐", "‑"])
def test_hyphen_lookalikes_are_not_refused(hyphen):
    text = f"A well{hyphen}known result for the episode."
    assert marketing.create_draft(draft_id="d", show="TQO", episode_ref="ep-1", platform="youtube_community",
                                  text=text, ai_disclosure="Made with AI").text == text
    assert sales.create_lead_draft(
        draft_id="l", source="email", contact_name="Jordan Lee", contact_email="jordan@example.com",
        inbound_excerpt="Do you coach?", qualification="qualified",
        qualification_reason="Asked about career strategy.", reply_text=text).reply_text == text


def test_a_reference_that_is_only_dashes_after_https_is_prose_not_a_url():
    for ref in ("https://" + "\u2014" * 8, "https://\u2013.\u2013", "https://localhost\u2014notes"):
        with pytest.raises(QueueRefusal, match="reference_artifact"):
            product.create_proposal(**{**PROD, "reference_artifact": ref})


@pytest.mark.parametrize("url", [
    "https://example.com", "https://example.com:8443/a\u2013b?x=\u2014#f", "https://docs.example.co.uk/a/b",
])
def test_a_real_host_url_is_left_verbatim(url):
    assert product.create_proposal(**{**PROD, "reference_artifact": url}).reference_artifact == url
