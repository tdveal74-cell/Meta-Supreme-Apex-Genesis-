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
-- HMAC-SHA256 signature under the estate key. The hashing and signing live in
-- services/devon/provenance.py; the writer applies them on every append and
-- every receipt.
--
-- The database owns the other half: a BEFORE UPDATE trigger refuses any
-- rewrite of an event or a receipt. The ledger reports the worse truth by
-- appending, never by editing. DELETE is deliberately left to the existing
-- ON DELETE CASCADE from intents and users, because an owner's right to be
-- removed outranks the audit trail, and a removed row still shows: the chain
-- verifier reports the gap. TRUNCATE (what the test fixture uses) fires no
-- row trigger and is unaffected.
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

DROP TRIGGER IF EXISTS trg_events_append_only ON events;
CREATE TRIGGER trg_events_append_only
    BEFORE UPDATE ON events
    FOR EACH ROW EXECUTE FUNCTION ledger_refuse_update();

DROP TRIGGER IF EXISTS trg_universal_receipts_append_only ON universal_receipts;
CREATE TRIGGER trg_universal_receipts_append_only
    BEFORE UPDATE ON universal_receipts
    FOR EACH ROW EXECUTE FUNCTION ledger_refuse_update();
