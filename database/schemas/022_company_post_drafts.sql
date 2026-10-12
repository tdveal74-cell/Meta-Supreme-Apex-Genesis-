-- 022: the Marketing approval queue's storage, one row per drafted post.
--
-- Tee ruled on 2026-10-12 that the Marketing agent drafts and queues and never
-- schedules or publishes. This table holds the queue. A row is a draft, an
-- approval record, or a rejection record. Nothing here sends anything anywhere.
--
-- owner_id is the account that owns the draft. It is not a foreign key, for the
-- same reason provider_usage.user_id is not: the record outlives the account.
-- The rules (disclosure present, no em or en dashes, a named human decider)
-- are enforced in services/company/marketing.py; the CHECK constraints below
-- hold the two that must survive a caller that skips it.
--
-- Re-runnable.

CREATE TABLE IF NOT EXISTS company_post_drafts (
    owner_id VARCHAR(64) NOT NULL,
    draft_id VARCHAR(64) NOT NULL,
    show VARCHAR(120) NOT NULL,
    episode_ref VARCHAR(200) NOT NULL,
    platform VARCHAR(80) NOT NULL,
    text TEXT NOT NULL,
    ai_disclosure TEXT NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'drafted',
    decided_by VARCHAR(320),
    decision_note TEXT,
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (owner_id, draft_id),
    CONSTRAINT company_post_drafts_status_chk
        CHECK (status IN ('drafted', 'approved', 'rejected')),
    CONSTRAINT company_post_drafts_disclosure_chk
        CHECK (length(btrim(ai_disclosure)) > 0),
    CONSTRAINT company_post_drafts_decider_chk
        CHECK ((status = 'drafted') = (decided_by IS NULL))
);

CREATE INDEX IF NOT EXISTS company_post_drafts_owner_created_idx
    ON company_post_drafts (owner_id, created_at DESC);
