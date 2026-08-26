-- WebAuthn passkeys for DEVON Command Center authentication.
-- Challenges are one-time, short-lived server state. Credentials never store
-- a private key; only the authenticator public key and signature counter live here.

CREATE TABLE IF NOT EXISTS passkey_credentials (
    credential_id TEXT PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    credential_public_key TEXT NOT NULL,
    sign_count BIGINT NOT NULL DEFAULT 0,
    label VARCHAR(120) NOT NULL DEFAULT 'DEVON passkey',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS ix_passkey_credentials_user_id
    ON passkey_credentials (user_id);

CREATE TABLE IF NOT EXISTS passkey_challenges (
    id VARCHAR(64) PRIMARY KEY,
    challenge TEXT NOT NULL,
    kind VARCHAR(24) NOT NULL,
    user_id UUID NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_passkey_challenge_kind CHECK (kind IN ('registration', 'authentication'))
);

CREATE INDEX IF NOT EXISTS ix_passkey_challenges_expires_at
    ON passkey_challenges (expires_at);
