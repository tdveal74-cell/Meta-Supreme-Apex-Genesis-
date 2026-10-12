-- 024: the Support approval queue's storage, one row per YouTube comment and drafted reply.
--
-- Tee ruled on 2026-10-12: audience questions arrive as YouTube comments, the
-- Support agent drafts the reply, and nothing is posted without Tee. A row is a
-- draft, an approval record or a rejection record. Nothing here posts anything.
--
-- owner_id is the account that owns the draft. It is not a foreign key, for the
-- same reason company_post_drafts.owner_id is not. The rules live in
-- services/company/support.py; the CHECK constraints hold the ones that must
-- survive a caller that skips it. One comment is queued once per owner, so a
-- repeated intake pass cannot stack drafts for the same comment.
--
-- Re-runnable.

CREATE TABLE IF NOT EXISTS company_comment_drafts (
    owner_id VARCHAR(64) NOT NULL,
    draft_id VARCHAR(64) NOT NULL,
    video_id VARCHAR(11) NOT NULL,
    comment_id VARCHAR(129) NOT NULL,
    commenter_name VARCHAR(200) NOT NULL,
    comment_text TEXT NOT NULL,
    reply_text TEXT NOT NULL,
    reply_basis TEXT NOT NULL,
    ai_disclosure TEXT NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'drafted',
    decided_by VARCHAR(320),
    decision_note TEXT,
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (owner_id, draft_id),
    CONSTRAINT company_comment_drafts_comment_uq UNIQUE (owner_id, comment_id),
    CONSTRAINT company_comment_drafts_status_chk
        CHECK (status IN ('drafted', 'approved', 'rejected')),
    CONSTRAINT company_comment_drafts_video_chk
        CHECK (video_id ~ '^[A-Za-z0-9_-]{11}$'),
    CONSTRAINT company_comment_drafts_comment_id_chk
        CHECK (comment_id ~ '^[A-Za-z0-9_-]{1,64}(\.[A-Za-z0-9_-]{1,64})?$'),
    CONSTRAINT company_comment_drafts_basis_chk
        CHECK (length(btrim(reply_basis)) > 0),
    CONSTRAINT company_comment_drafts_disclosure_chk
        CHECK (length(btrim(ai_disclosure)) > 0),
    CONSTRAINT company_comment_drafts_decider_chk
        CHECK ((status = 'drafted') = (decided_by IS NULL))
);

CREATE INDEX IF NOT EXISTS company_comment_drafts_owner_created_idx
    ON company_comment_drafts (owner_id, created_at DESC);
