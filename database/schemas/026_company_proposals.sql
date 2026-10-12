-- 026: the Product proposals queue's storage, one row per change proposal.
--
-- Product Development drafts change proposals and a human decides which get
-- built. A row is a proposal, an approval record or a rejection record. Nothing
-- here builds, commits or runs anything.
--
-- owner_id is the account that owns the proposal. It is not a foreign key, for
-- the same reason company_post_drafts.owner_id is not. The rules live in
-- services/company/product.py; the CHECK constraints hold the ones that must
-- survive a caller that skips it. A title is recorded once per owner (title_key
-- is a sha256 of the case and whitespace folded title).
--
-- Re-runnable.

CREATE TABLE IF NOT EXISTS company_proposals (
    owner_id VARCHAR(64) NOT NULL,
    draft_id VARCHAR(64) NOT NULL,
    title_key VARCHAR(64) NOT NULL,
    title VARCHAR(200) NOT NULL,
    problem TEXT NOT NULL,
    proposal TEXT NOT NULL,
    acceptance_check TEXT NOT NULL,
    reference_artifact TEXT NOT NULL,
    size VARCHAR(8) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'drafted',
    decided_by VARCHAR(320),
    decision_note TEXT,
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (owner_id, draft_id),
    CONSTRAINT company_proposals_title_uq UNIQUE (owner_id, title_key),
    CONSTRAINT company_proposals_title_key_chk CHECK (title_key ~ '^[0-9a-f]{64}$'),
    CONSTRAINT company_proposals_size_chk CHECK (size IN ('small', 'medium', 'large')),
    CONSTRAINT company_proposals_status_chk
        CHECK (status IN ('drafted', 'approved', 'rejected')),
    CONSTRAINT company_proposals_check_chk CHECK (length(btrim(acceptance_check)) > 0),
    CONSTRAINT company_proposals_reference_chk CHECK (length(btrim(reference_artifact)) > 0),
    CONSTRAINT company_proposals_decider_chk
        CHECK ((status = 'drafted') = (decided_by IS NULL))
);

CREATE INDEX IF NOT EXISTS company_proposals_owner_created_idx
    ON company_proposals (owner_id, created_at DESC);
