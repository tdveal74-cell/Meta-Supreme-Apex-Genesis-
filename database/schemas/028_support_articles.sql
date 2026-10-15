-- 028: the Support knowledge base, and the article every Support reply cites.
--
-- Tee ruled on 2026-10-15: Support replies take their facts from approved
-- articles he writes, and a reply with no article id is refused. An article is a
-- draft until a human approves it, and only an approved article can be cited.
-- Nothing here posts anything.
--
-- The rules live in services/company/knowledge.py; the CHECK constraints hold
-- the ones that must survive a caller that skips it. company_comment_drafts
-- gains article_id. It is nullable because rows from before this migration have
-- none; the application refuses a new draft without one, and the composite
-- foreign key keeps a cited article real and owned by the same account.
--
-- Re-runnable.

CREATE TABLE IF NOT EXISTS company_support_articles (
    owner_id VARCHAR(64) NOT NULL,
    article_id VARCHAR(63) NOT NULL,
    title VARCHAR(200) NOT NULL,
    body TEXT NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'drafted',
    decided_by VARCHAR(320),
    decision_note TEXT,
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (owner_id, article_id),
    CONSTRAINT company_support_articles_status_chk
        CHECK (status IN ('drafted', 'approved', 'rejected')),
    CONSTRAINT company_support_articles_id_chk
        CHECK (article_id ~ '^[a-z0-9][a-z0-9-]{1,62}$'),
    CONSTRAINT company_support_articles_title_chk
        CHECK (length(btrim(title)) > 0),
    CONSTRAINT company_support_articles_body_chk
        CHECK (length(btrim(body)) > 0),
    CONSTRAINT company_support_articles_decider_chk
        CHECK ((status = 'drafted') = (decided_by IS NULL))
);

CREATE INDEX IF NOT EXISTS company_support_articles_owner_created_idx
    ON company_support_articles (owner_id, created_at DESC);

ALTER TABLE company_comment_drafts
    ADD COLUMN IF NOT EXISTS article_id VARCHAR(63);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'company_comment_drafts_article_fk'
    ) THEN
        ALTER TABLE company_comment_drafts
            ADD CONSTRAINT company_comment_drafts_article_fk
            FOREIGN KEY (owner_id, article_id)
            REFERENCES company_support_articles (owner_id, article_id);
    END IF;
END
$$;
