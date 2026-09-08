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
--   BEFORE DELETE on events and receipts refuses a statement aimed at the
--   table and admits the cascade from intents and users. BEFORE DELETE on
--   intents refuses a statement aimed at intents and admits only the cascade
--   from users, because an owner's right to be removed outranks the audit
--   trail while nothing else may take an intent out from under its chain.
--   Direct and cascade are told apart by pg_trigger_depth(): a direct DELETE
--   fires the row trigger at depth 1, a cascade arrives inside the
--   referential integrity trigger at depth 2 or more. The first gauntlet of
--   2026-09-08 showed why DELETE could not stay open (delete the tail and
--   the receipt, append, re-issue, verified). The second showed why the
--   parent needed the same guard (delete the intent, re-insert its id,
--   replay a different history, verified).
--
--   Every trigger is ENABLE ALWAYS, so session_replication_role = replica,
--   which silences ordinary triggers, does not silence these.
--
-- What the database cannot own is stated rather than pretended away. A role
-- that can disable or drop these triggers, TRUNCATE the tables, or create a
-- table with a trigger of its own that deletes at depth 2 can rewrite
-- history; that is the table owner or a role with CREATE on the schema. The
-- production compose runs the API as a dedicated role with none of those
-- rights (infrastructure/docker/initdb/sql/api-role.sql) and runs
-- migrations as the owner in a separate one-shot step. Proving history to a
-- reader who does not trust the database at all needs the chain heads
-- anchored outside it, which is a later gate.
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

CREATE OR REPLACE FUNCTION ledger_refuse_delete() RETURNS TRIGGER AS $$
BEGIN
    IF pg_trigger_depth() <= 1 THEN
        RAISE EXCEPTION 'ledger table % is append only: row % may not be deleted. '
            'Only the cascade from a removed intent or owner may take it.',
            TG_TABLE_NAME, OLD.id
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN OLD;
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

-- The parent. An intent may leave only inside the cascade from its owner.
DROP TRIGGER IF EXISTS trg_intents_no_delete ON intents;
CREATE TRIGGER trg_intents_no_delete
    BEFORE DELETE ON intents
    FOR EACH ROW EXECUTE FUNCTION ledger_refuse_delete();
ALTER TABLE intents ENABLE ALWAYS TRIGGER trg_intents_no_delete;
