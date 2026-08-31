-- DEVON Live State Ledger, the Event Bus, and the Universal Receipt.
-- Re-runnable incremental schema for PostgreSQL 16.
--
-- Compiled from the DEVON ECOSYSTEM diagram: "One organism. One intent. One
-- receipt." The ten ledger tables carry the diagram's own names so a reader can
-- hold the picture and the schema side by side without translating.
--
-- Two invariants are enforced here rather than in application code, because a
-- constraint the database owns survives a caller that forgets:
--   1. One receipt per intent (unique intent_id on universal_receipts).
--   2. Only the thirteen universal events may be appended (check on events.name),
--      each at its own position (unique intent_id + sequence_no).
--
-- The approvals table OBSERVES the approval authority. It never grants. The
-- authority stays in services/devon/approval.py and devon_approvals, and a row
-- here only records which request was raised against which intent and how it
-- was ruled.

CREATE TABLE IF NOT EXISTS intents (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    channel VARCHAR(32) NOT NULL,
    stated TEXT NOT NULL,
    state VARCHAR(24) NOT NULL DEFAULT 'received',
    is_effect BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_intents_channel CHECK (channel IN (
        'chat_voice', 'forms', 'email', 'documents', 'web_apis', 'other_systems'
    )),
    CONSTRAINT ck_intents_state CHECK (state IN (
        'received', 'planned', 'awaiting_approval', 'executing',
        'completed', 'failed', 'receipted'
    ))
);

CREATE INDEX IF NOT EXISTS ix_intents_owner_created
    ON intents(owner_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_intents_state
    ON intents(state);

-- The Event Bus. Append only: no UPDATE or DELETE path exists in the writer,
-- and the sequence number makes a gap or a reorder visible rather than silent.
CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    intent_id UUID NOT NULL REFERENCES intents(id) ON DELETE CASCADE,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(32) NOT NULL,
    sequence_no INTEGER NOT NULL,
    action_id VARCHAR(64) NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_events_intent_sequence UNIQUE(intent_id, sequence_no),
    CONSTRAINT ck_events_name CHECK (name IN (
        'INTENT_RECEIVED', 'CONTEXT_LOADED', 'SOUL_READ', 'SUBCONSCIOUS_RECALLED',
        'PLAN_CREATED', 'APPROVAL_REQUESTED', 'APPROVAL_GRANTED', 'ACTION_STARTED',
        'ACTION_COMPLETED', 'ACTION_FAILED', 'VERIFICATION_PASSED',
        'ARTIFACT_CREATED', 'LEARNING_CAPTURED'
    ))
);

CREATE INDEX IF NOT EXISTS ix_events_intent_sequence
    ON events(intent_id, sequence_no);
CREATE INDEX IF NOT EXISTS ix_events_owner_occurred
    ON events(owner_id, occurred_at DESC);

CREATE TABLE IF NOT EXISTS actions (
    id VARCHAR(64) PRIMARY KEY,
    intent_id UUID NOT NULL REFERENCES intents(id) ON DELETE CASCADE,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    duty VARCHAR(200) NOT NULL,
    executor VARCHAR(32) NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'planned',
    detail JSONB NOT NULL DEFAULT '{}',
    started_at TIMESTAMPTZ NULL,
    ended_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_actions_executor CHECK (executor IN ('n8n', 'zapier', 'UNROUTED')),
    CONSTRAINT ck_actions_status CHECK (status IN (
        'planned', 'awaiting_approval', 'started', 'completed', 'failed', 'refused'
    ))
);

CREATE INDEX IF NOT EXISTS ix_actions_intent
    ON actions(intent_id, created_at DESC);

-- Observes the approval authority. Never grants.
CREATE TABLE IF NOT EXISTS approvals (
    id VARCHAR(64) PRIMARY KEY,
    intent_id UUID NOT NULL REFERENCES intents(id) ON DELETE CASCADE,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    approval_request_id VARCHAR(64) NOT NULL,
    action_id VARCHAR(64) NULL REFERENCES actions(id) ON DELETE SET NULL,
    state VARCHAR(24) NOT NULL,
    what_happens TEXT NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at TIMESTAMPTZ NULL,
    decided_by VARCHAR(120) NOT NULL DEFAULT '',
    CONSTRAINT uq_approvals_request UNIQUE(approval_request_id),
    CONSTRAINT ck_approvals_state CHECK (state IN (
        'pending', 'approved', 'refused', 'expired'
    ))
);

CREATE INDEX IF NOT EXISTS ix_approvals_intent
    ON approvals(intent_id, requested_at DESC);

CREATE TABLE IF NOT EXISTS artifacts (
    id VARCHAR(64) PRIMARY KEY,
    intent_id UUID NOT NULL REFERENCES intents(id) ON DELETE CASCADE,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action_id VARCHAR(64) NULL REFERENCES actions(id) ON DELETE SET NULL,
    path TEXT NOT NULL,
    sha256 VARCHAR(64) NOT NULL DEFAULT '',
    media_type VARCHAR(200) NOT NULL DEFAULT 'application/octet-stream',
    body TEXT NOT NULL DEFAULT '',
    kind VARCHAR(32) NOT NULL DEFAULT 'lesson',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_artifacts_intent
    ON artifacts(intent_id, created_at DESC);

-- The executor registry. Health is written by whatever probes the executor;
-- an absent probe leaves last_seen_at NULL rather than claiming health.
CREATE TABLE IF NOT EXISTS executors (
    name VARCHAR(32) PRIMARY KEY,
    role VARCHAR(64) NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'unknown',
    note TEXT NOT NULL DEFAULT '',
    last_seen_at TIMESTAMPTZ NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_executors_status CHECK (status IN ('unknown', 'ok', 'degraded', 'down'))
);

INSERT INTO executors (name, role, note)
VALUES
    ('n8n', 'internal executor',
     'Runs inside the estate. Still passes the approval gate for effects.'),
    ('zapier', 'external executor',
     'Reaches commercial services. Never holds DEVON canon or secrets.')
ON CONFLICT (name) DO NOTHING;

-- Systems and controls. The emergency stop is a control row: when its status is
-- 'stopped' for an owner, no action may start for that owner.
CREATE TABLE IF NOT EXISTS systems (
    id VARCHAR(64) PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(64) NOT NULL,
    kind VARCHAR(24) NOT NULL DEFAULT 'service',
    status VARCHAR(24) NOT NULL DEFAULT 'ok',
    reason TEXT NOT NULL DEFAULT '',
    changed_by VARCHAR(120) NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_systems_owner_name UNIQUE(owner_id, name),
    CONSTRAINT ck_systems_kind CHECK (kind IN ('service', 'executor', 'control')),
    CONSTRAINT ck_systems_status CHECK (status IN ('ok', 'degraded', 'down', 'stopped'))
);

CREATE INDEX IF NOT EXISTS ix_systems_owner
    ON systems(owner_id, name);

CREATE TABLE IF NOT EXISTS errors (
    id VARCHAR(64) PRIMARY KEY,
    intent_id UUID NULL REFERENCES intents(id) ON DELETE CASCADE,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action_id VARCHAR(64) NULL REFERENCES actions(id) ON DELETE SET NULL,
    message TEXT NOT NULL,
    detail JSONB NOT NULL DEFAULT '{}',
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_errors_owner_occurred
    ON errors(owner_id, occurred_at DESC);

CREATE TABLE IF NOT EXISTS verifications (
    id VARCHAR(64) PRIMARY KEY,
    intent_id UUID NOT NULL REFERENCES intents(id) ON DELETE CASCADE,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action_id VARCHAR(64) NULL REFERENCES actions(id) ON DELETE SET NULL,
    method VARCHAR(200) NOT NULL,
    passed BOOLEAN NOT NULL,
    evidence TEXT NOT NULL,
    verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_verifications_intent
    ON verifications(intent_id, verified_at DESC);

CREATE TABLE IF NOT EXISTS learning_candidates (
    id VARCHAR(64) PRIMARY KEY,
    intent_id UUID NOT NULL REFERENCES intents(id) ON DELETE CASCADE,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'candidate',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_learning_candidates_status CHECK (status IN (
        'candidate', 'promoted', 'refused'
    ))
);

CREATE INDEX IF NOT EXISTS ix_learning_candidates_status
    ON learning_candidates(status, created_at DESC);

-- One receipt per intent. The unique constraint is the rule, not a convention.
CREATE TABLE IF NOT EXISTS universal_receipts (
    id VARCHAR(64) PRIMARY KEY,
    intent_id UUID NOT NULL REFERENCES intents(id) ON DELETE CASCADE,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    what_happened TEXT NOT NULL,
    verification TEXT NOT NULL,
    provenance TEXT NOT NULL,
    artifacts JSONB NOT NULL DEFAULT '[]',
    learned TEXT NOT NULL DEFAULT '',
    next_steps TEXT NOT NULL DEFAULT '',
    issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_universal_receipts_intent UNIQUE(intent_id)
);

CREATE INDEX IF NOT EXISTS ix_universal_receipts_owner_issued
    ON universal_receipts(owner_id, issued_at DESC);
