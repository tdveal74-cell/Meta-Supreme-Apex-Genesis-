-- 023: the Sales approval queue's storage, one row per qualified lead and drafted reply.
--
-- Tee ruled on 2026-10-12: leads arrive as email or form replies, the Sales
-- agent qualifies them and drafts the follow-up, and nothing is sent without
-- Tee. A row is a draft, an approval record or a rejection record. Nothing here
-- sends anything.
--
-- owner_id is the account that owns the draft. It is not a foreign key, for the
-- same reason company_post_drafts.owner_id is not. The rules live in
-- services/company/sales.py; the CHECK constraints hold the ones that must
-- survive a caller that skips it. The row holds a lead's contact details, which
-- are personal data: keep reads scoped to the owner, as the service does.
--
-- Re-runnable.

CREATE TABLE IF NOT EXISTS company_lead_drafts (
    owner_id VARCHAR(64) NOT NULL,
    draft_id VARCHAR(64) NOT NULL,
    source VARCHAR(16) NOT NULL,
    contact_name VARCHAR(200) NOT NULL,
    contact_email VARCHAR(320) NOT NULL,
    inbound_excerpt TEXT NOT NULL,
    qualification VARCHAR(16) NOT NULL,
    qualification_reason TEXT NOT NULL,
    reply_text TEXT NOT NULL,
    ai_disclosure TEXT NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'drafted',
    decided_by VARCHAR(320),
    decision_note TEXT,
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (owner_id, draft_id),
    CONSTRAINT company_lead_drafts_source_chk CHECK (source IN ('email', 'form')),
    CONSTRAINT company_lead_drafts_qualification_chk
        CHECK (qualification IN ('qualified', 'not_qualified', 'needs_info')),
    CONSTRAINT company_lead_drafts_status_chk
        CHECK (status IN ('drafted', 'approved', 'rejected')),
    CONSTRAINT company_lead_drafts_disclosure_chk
        CHECK (length(btrim(ai_disclosure)) > 0),
    CONSTRAINT company_lead_drafts_decider_chk
        CHECK ((status = 'drafted') = (decided_by IS NULL))
);

CREATE INDEX IF NOT EXISTS company_lead_drafts_owner_created_idx
    ON company_lead_drafts (owner_id, created_at DESC);
