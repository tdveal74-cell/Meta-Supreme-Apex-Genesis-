-- 027: a Sales draft may carry no AI disclosure.
--
-- Tee ruled on 2026-10-14 that a one to one sales email needs no disclosure line,
-- after being offered the opposite as the recommendation. This is the one place in
-- the company layer where the disclosure may be absent; Marketing posts and Support
-- replies still require it. A disclosure that IS given must still be non-blank,
-- and the rules in services/company/sales.py hold the 10 character floor.
--
-- Existing rows keep their disclosure. Re-runnable.

ALTER TABLE company_lead_drafts ALTER COLUMN ai_disclosure DROP NOT NULL;

ALTER TABLE company_lead_drafts DROP CONSTRAINT IF EXISTS company_lead_drafts_disclosure_chk;
ALTER TABLE company_lead_drafts ADD CONSTRAINT company_lead_drafts_disclosure_chk
    CHECK (ai_disclosure IS NULL OR length(btrim(ai_disclosure)) > 0);
