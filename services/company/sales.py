"""The Sales approval queue rules.

Tee ruled on 2026-10-12: leads arrive as email or form replies, the Sales agent
qualifies them and drafts the follow-up, and nothing is sent without Tee. This
module is the rule set for that queue. It holds no store and opens no
connection, so nothing here can send a message.

What it refuses:

  1. A source other than email or form, a contact address that is not shaped
     like one, and a qualification that is not one of the three named.
  2. A qualification with no reason of at least 10 visible characters. A
     verdict nobody can read the grounds for is a guess, and Tee decides on
     the grounds.
  3. A drafted reply with em or en dashes or look-alikes, or a NUL byte. Tee's
     prose rule for anything delivered. The inbound excerpt is the lead's own
     words and is only checked for NUL, because it is not ours to rewrite.
  4. A drafted reply with no AI disclosure of at least 10 visible characters.
     Tee's disclosure rule has no exception path, so this reuses the Marketing
     rule. Whether a one to one email needs the same line is Tee's call to
     loosen; the safe direction is to require it.
  5. An approval with no human named, or one named as an automated actor, and
     a second decision on a draft that already has one.

It never checks that a reply's claims are true. It only checks the grounds
were written down.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace
from enum import Enum
from typing import Optional

from services.company.marketing import (
    AUTOMATED_ACTORS,
    MIN_DISCLOSURE_CHARS,
    DraftStatus,
    QueueRefusal,
    _check_text,
    _visible_len,
)

SOURCES = ("email", "form")
MIN_REASON_CHARS = 10
MAX_EMAIL_CHARS = 254

# The address comes from an untrusted inbound message and may one day feed a To
# header, so it is held to a strict shape: one @, no whitespace, angle brackets,
# commas, semicolons, quotes, control or invisible characters in the local part,
# and a dotted ASCII domain with no empty labels and an alphabetic top level.
_EMAIL_RE = re.compile(
    r"^[^\s@<>,;\"\x00-\x1f\x7f\u200b-\u200f\u2028-\u202f\u2060-\u206f\ufeff]+"
    r"@(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,}$"
)


class Qualification(str, Enum):
    QUALIFIED = "qualified"
    NOT_QUALIFIED = "not_qualified"
    NEEDS_INFO = "needs_info"


@dataclass(frozen=True)
class LeadDraft:
    draft_id: str
    source: str
    contact_name: str
    contact_email: str
    inbound_excerpt: str
    qualification: Qualification
    qualification_reason: str
    reply_text: str
    ai_disclosure: str
    status: DraftStatus = DraftStatus.DRAFTED
    decided_by: Optional[str] = None
    decision_note: Optional[str] = None


def _plain_field(value: str, label: str) -> None:
    if not value or not value.strip():
        raise QueueRefusal(f"{label} is empty")
    if "\x00" in value:
        raise QueueRefusal(f"{label} contains a NUL byte")


def create_lead_draft(
    *,
    draft_id: str,
    source: str,
    contact_name: str,
    contact_email: str,
    inbound_excerpt: str,
    qualification: str,
    qualification_reason: str,
    reply_text: str,
    ai_disclosure: str,
) -> LeadDraft:
    _plain_field(draft_id, "draft_id")
    if source not in SOURCES:
        raise QueueRefusal(f"source must be one of {', '.join(SOURCES)}")
    _plain_field(contact_name, "contact_name")
    if any(unicodedata.category(ch) in ("Cc", "Cf") for ch in contact_name):
        raise QueueRefusal("contact_name contains a control or invisible character")
    _plain_field(contact_email, "contact_email")
    addr = contact_email.strip()
    if len(addr) > MAX_EMAIL_CHARS or not _EMAIL_RE.match(addr):
        raise QueueRefusal("contact_email is not shaped like an email address")
    _plain_field(inbound_excerpt, "inbound_excerpt")
    try:
        qual = Qualification(qualification)
    except ValueError:
        raise QueueRefusal(
            "qualification must be one of "
            + ", ".join(q.value for q in Qualification)
        ) from None
    _plain_field(qualification_reason, "qualification_reason")
    if _visible_len(qualification_reason) < MIN_REASON_CHARS:
        raise QueueRefusal(
            f"qualification_reason needs at least {MIN_REASON_CHARS} visible characters"
        )
    _check_text(reply_text, "reply text")
    _check_text(ai_disclosure, "ai_disclosure")
    if _visible_len(ai_disclosure) < MIN_DISCLOSURE_CHARS:
        raise QueueRefusal(
            f"ai_disclosure needs at least {MIN_DISCLOSURE_CHARS} visible characters"
        )
    return LeadDraft(
        draft_id=draft_id, source=source, contact_name=contact_name.strip(),
        contact_email=addr, inbound_excerpt=inbound_excerpt, qualification=qual,
        qualification_reason=qualification_reason, reply_text=reply_text,
        ai_disclosure=ai_disclosure,
    )


def _decide(draft: LeadDraft, status: DraftStatus, decided_by: str, note: Optional[str]) -> LeadDraft:
    if draft.status is not DraftStatus.DRAFTED:
        raise QueueRefusal(f"draft already {draft.status.value}")
    who = (decided_by or "").strip()
    if not who:
        raise QueueRefusal("a human decision needs a named decider")
    if who.lower() in AUTOMATED_ACTORS:
        raise QueueRefusal(f"{who!r} is an automated actor, not a human decider")
    return replace(draft, status=status, decided_by=who, decision_note=note)


def approve(draft: LeadDraft, decided_by: str, note: Optional[str] = None) -> LeadDraft:
    """Records approval. It does not send anything."""
    return _decide(draft, DraftStatus.APPROVED, decided_by, note)


def reject(draft: LeadDraft, decided_by: str, note: Optional[str] = None) -> LeadDraft:
    return _decide(draft, DraftStatus.REJECTED, decided_by, note)
