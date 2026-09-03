-- 018: make the Alembic build and the SQL build the same database, and give
-- the ledger the approval state its own commit path already reaches.
--
-- Two divergences, both measured rather than assumed, both closed here.
--
-- --- knowledge_items.content ---
-- The repository carries the schema twice: the Alembic chain, which is what
-- Railway runs before every deploy, and these mirrored scripts, which is what
-- conftest applies to the test database. Nothing compared them until the CI
-- step this migration ships beside. Comparing them found one difference:
-- 004_federated_knowledge_waist.sql adds knowledge_items.content, and the
-- Alembic 004 does not. Every ingest path writes that column
-- (app/services/knowledge.py, services/knowledge/pipeline.py, both knowledge
-- routes), so on an Alembic-built database the write raises
-- UndefinedColumnError. Adding the column the model has always declared.
--
-- --- approvals.state ---
-- 013 taught the DEVON approval queue that an approved effect is spent when it
-- runs. The Live State Ledger's own approvals table never learned the same
-- word: its check constraint stops at pending, approved, refused and expired,
-- so a knowledge-loop approval that has been consumed still reads 'approved'
-- on the ledger forever, and the ledger misreports the authority's outcome.
-- Adding 'consumed' to the constraint; the transitions that write it ship in
-- the same commit.
--
-- Re-runnable on purpose, like 013: it lands against live shared tables, so it
-- adds the column only if absent and drops and re-adds the constraint rather
-- than assuming its prior shape. No row is rewritten.

ALTER TABLE knowledge_items ADD COLUMN IF NOT EXISTS content TEXT;

ALTER TABLE approvals DROP CONSTRAINT IF EXISTS ck_approvals_state;
ALTER TABLE approvals ADD CONSTRAINT ck_approvals_state CHECK (state IN (
    'pending', 'approved', 'consumed', 'refused', 'expired'
));
