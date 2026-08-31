-- 014: the capture payload has a body. estate:// is a path label, not a blob.
--
-- Before this, artifacts stored path + sha256 + media_type and no body. Find
-- could only return intents.stated. The URI was not resolvable. PostgreSQL is
-- the store; the body lives on the artifacts row.
--
-- Re-runnable. Existing rows get an empty body and kind 'lesson'. Knowledge
-- loop commits after this write the payload into body and the ledger kind
-- (including Tee rulings, which never enter Layer 1 Tee Soul).

ALTER TABLE artifacts
    ADD COLUMN IF NOT EXISTS body TEXT NOT NULL DEFAULT '';

ALTER TABLE artifacts
    ADD COLUMN IF NOT EXISTS kind VARCHAR(32) NOT NULL DEFAULT 'lesson';
