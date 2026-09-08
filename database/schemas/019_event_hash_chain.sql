-- 019: the Event Bus becomes a hash chain, and the Universal Receipt is signed.
--
-- Before this, the ledger owned two refusals (only the thirteen events, one
-- receipt per intent) and both were checks on the next write. Nothing checked
-- the past. An event rewritten in place, a row removed from the middle of an
-- intent, or a receipt edited after issue all read as legal history.
--
-- Now every event carries the SHA-256 of its own material linked to the hash
-- of the event before it (the first links to the empty string), and every
-- receipt carries the chain head it certifies, the chain length, and an
-- HMAC-SHA256 signature under the receipt signing key. The hashing and
-- signing live in services/devon/provenance.py; the writer applies them on
-- every append and every receipt.
--
-- The database owns the other half, in triggers:
--
--   BEFORE UPDATE on events and receipts refuses any rewrite. The ledger
--   reports the worse truth by appending, never by editing.
--
--   BEFORE DELETE on events and receipts admits a row only once its intent
--   is gone, and BEFORE DELETE on intents admits a row only once its owner
--   is gone. That is what a cascade is: the parent row has already been
--   deleted in this transaction when the referential action reaches the
--   child. A statement aimed at the child while the parent still stands is
--   refused, whoever issues it and from whatever trigger depth. The first
--   gauntlet of 2026-09-08 showed why DELETE could not stay open (delete
--   the tail and the receipt, append, re-issue, verified). The second showed
--   why the parent needed the same guard (delete the intent, re-insert its
--   id, replay, verified). The third showed why trigger depth was the wrong
--   test: a temporary table with a trigger of its own deletes at depth 2 and
--   was admitted. An owner's right to be removed still outranks the audit
--   trail; the cascade from users is the one door, and only a role allowed
--   to delete users can open it.
--
--   BEFORE UPDATE on intents admits changes to state and updated_at, which
--   are the two columns the writer moves, and refuses every other column:
--   the intent's id, owner, channel, statement, effect flag and creation
--   time are part of what the chain certifies (the opening event hashes the
--   owner and the statement), and an intent handed to another owner or
--   reworded after the fact is a rewrite.
--
--   Every trigger is ENABLE ALWAYS, so session_replication_role = replica,
--   which silences ordinary triggers, does not silence these.
--
-- What the database cannot own is stated rather than pretended away. A role
-- that can disable or drop these triggers, TRUNCATE the tables, or delete
-- users can rewrite or erase history; that is the table owner, or a role
-- granted more than the application uses. The production compose runs the
-- API as a dedicated role with none of those rights (created by
-- infrastructure/docker/initdb/sql/api-role.sql, granted by
-- database/grants/devon_api.sql after every migration) and runs migrations
-- as the owner in a separate one-shot step. Proving history to a reader who
-- does not trust the database at all needs the chain heads anchored outside
-- it, which is a later gate.
--
-- TRUNCATE (what the test fixture uses) fires no row trigger and is a
-- privilege the runtime role does not hold.
--
-- Re-runnable on purpose. Existing rows keep an empty hash and an empty
-- signature: that is the honest state of a row written before the chain
-- existed, and the verifier counts them as unhashed rather than broken.
-- Backfilling would claim a provenance those rows never had.

ALTER TABLE events
    ADD COLUMN IF NOT EXISTS prev_hash VARCHAR(64) NOT NULL DEFAULT '';

ALTER TABLE events
    ADD COLUMN IF NOT EXISTS hash VARCHAR(64) NOT NULL DEFAULT '';

ALTER TABLE universal_receipts
    ADD COLUMN IF NOT EXISTS head_hash VARCHAR(64) NOT NULL DEFAULT '';

ALTER TABLE universal_receipts
    ADD COLUMN IF NOT EXISTS chain_length INTEGER NOT NULL DEFAULT 0;

ALTER TABLE universal_receipts
    ADD COLUMN IF NOT EXISTS signature VARCHAR(64) NOT NULL DEFAULT '';

ALTER TABLE universal_receipts
    ADD COLUMN IF NOT EXISTS signature_key_id VARCHAR(16) NOT NULL DEFAULT '';

CREATE OR REPLACE FUNCTION ledger_refuse_update() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'ledger table % is append only: row % may not be rewritten. '
        'The ledger reports a later truth by appending, never by editing.',
        TG_TABLE_NAME, OLD.id
        USING ERRCODE = 'integrity_constraint_violation';
END;
$$ LANGUAGE plpgsql;

-- A child row may leave only once its parent is already gone. During a
-- cascade the referential action runs after the parent's own delete, so the
-- parent is absent from this transaction's view; a statement aimed at the
-- child, from any depth, still sees the parent standing and is refused.
CREATE OR REPLACE FUNCTION ledger_refuse_delete() RETURNS TRIGGER AS $$
DECLARE
    parent_present BOOLEAN;
BEGIN
    IF TG_TABLE_NAME = 'intents' THEN
        SELECT EXISTS (SELECT 1 FROM users WHERE id = OLD.owner_id) INTO parent_present;
    ELSE
        SELECT EXISTS (SELECT 1 FROM intents WHERE id = OLD.intent_id) INTO parent_present;
    END IF;
    IF parent_present THEN
        RAISE EXCEPTION 'ledger table % is append only: row % may not be deleted. '
            'Only the cascade from a removed intent or owner may take it.',
            TG_TABLE_NAME, OLD.id
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION ledger_refuse_intent_rewrite() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.id IS DISTINCT FROM OLD.id
        OR NEW.owner_id IS DISTINCT FROM OLD.owner_id
        OR NEW.channel IS DISTINCT FROM OLD.channel
        OR NEW.stated IS DISTINCT FROM OLD.stated
        OR NEW.is_effect IS DISTINCT FROM OLD.is_effect
        OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'intent % may only move its state: its owner, channel, '
            'statement, effect flag and creation time are certified by its chain.',
            OLD.id
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_events_append_only ON events;
CREATE TRIGGER trg_events_append_only
    BEFORE UPDATE ON events
    FOR EACH ROW EXECUTE FUNCTION ledger_refuse_update();
ALTER TABLE events ENABLE ALWAYS TRIGGER trg_events_append_only;

DROP TRIGGER IF EXISTS trg_events_no_delete ON events;
CREATE TRIGGER trg_events_no_delete
    BEFORE DELETE ON events
    FOR EACH ROW EXECUTE FUNCTION ledger_refuse_delete();
ALTER TABLE events ENABLE ALWAYS TRIGGER trg_events_no_delete;

DROP TRIGGER IF EXISTS trg_universal_receipts_append_only ON universal_receipts;
CREATE TRIGGER trg_universal_receipts_append_only
    BEFORE UPDATE ON universal_receipts
    FOR EACH ROW EXECUTE FUNCTION ledger_refuse_update();
ALTER TABLE universal_receipts ENABLE ALWAYS TRIGGER trg_universal_receipts_append_only;

DROP TRIGGER IF EXISTS trg_universal_receipts_no_delete ON universal_receipts;
CREATE TRIGGER trg_universal_receipts_no_delete
    BEFORE DELETE ON universal_receipts
    FOR EACH ROW EXECUTE FUNCTION ledger_refuse_delete();
ALTER TABLE universal_receipts ENABLE ALWAYS TRIGGER trg_universal_receipts_no_delete;

-- The parent. An intent may leave only inside the cascade from its owner,
-- and may change nothing but its state.
DROP TRIGGER IF EXISTS trg_intents_no_delete ON intents;
CREATE TRIGGER trg_intents_no_delete
    BEFORE DELETE ON intents
    FOR EACH ROW EXECUTE FUNCTION ledger_refuse_delete();
ALTER TABLE intents ENABLE ALWAYS TRIGGER trg_intents_no_delete;

DROP TRIGGER IF EXISTS trg_intents_state_only ON intents;
CREATE TRIGGER trg_intents_state_only
    BEFORE UPDATE ON intents
    FOR EACH ROW EXECUTE FUNCTION ledger_refuse_intent_rewrite();
ALTER TABLE intents ENABLE ALWAYS TRIGGER trg_intents_state_only;
