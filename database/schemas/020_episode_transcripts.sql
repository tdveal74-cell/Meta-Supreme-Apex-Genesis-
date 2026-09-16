-- 020_episode_transcripts
--
-- Let a knowledge item be an episode transcript.
--
-- `knowledge_items.source_type` has carried a CHECK since 001 listing six
-- document kinds. Every one of them describes a FILE FORMAT: pdf, docx, txt,
-- markdown, url, manual. An episode transcript is not a seventh format, it is
-- a different KIND of thing, and the coverage question ("have I already said
-- this on air") has to be able to ask for it by name.
--
-- Widening the CHECK rather than reusing `markdown` is deliberate. The
-- alternative was to tag episodes through the free text `source` column, which
-- exists for connector provenance and is written by the FKR path. Overloading
-- it would make the episode filter depend on a column another subsystem owns,
-- and a collision there returns "yes, you covered that" about a document that
-- was never spoken. A false positive is the one answer this feature must never
-- give, so the type is a type.
--
-- Idempotent: the constraint is dropped by name if present and recreated, so
-- the Alembic path and the SQL script path converge on the same definition.
-- CI asserts those two builds match.

ALTER TABLE knowledge_items
    DROP CONSTRAINT IF EXISTS knowledge_items_source_type_check;

ALTER TABLE knowledge_items
    ADD CONSTRAINT knowledge_items_source_type_check
    CHECK (source_type IN (
        'pdf', 'docx', 'txt', 'markdown', 'url', 'manual', 'episode_transcript'
    ));

-- One episode per distinct transcript per owner. The fingerprint is a sha256
-- of the whitespace normalised text and lives in `external_id`.
--
-- Enforced here rather than trusted to the service, because the read-then-write
-- in `record_episode_transcript` is not atomic: two renders finishing together
-- would both find nothing and both insert. Three exports of one episode landed
-- in Drive inside an hour on 2026-09-15, so concurrent ingests of identical
-- text is the expected case, not a corner. A duplicate would let one episode
-- outvote the whole catalogue on every later search.
CREATE UNIQUE INDEX IF NOT EXISTS knowledge_items_episode_fingerprint_key
    ON knowledge_items (owner_id, external_id)
    WHERE source_type = 'episode_transcript' AND external_id IS NOT NULL;
