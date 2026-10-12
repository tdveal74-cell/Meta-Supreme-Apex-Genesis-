-- 025: the Research findings queue's storage, one row per finding.
--
-- Research is a READ function: it finds and recommends, a human decides what to
-- adopt. A row is a finding, an adoption record or a dismissal record. Nothing
-- here acts on a finding.
--
-- owner_id is the account that owns the finding. It is not a foreign key, for
-- the same reason company_post_drafts.owner_id is not. The rules live in
-- services/company/research.py; the CHECK constraints hold the ones that must
-- survive a caller that skips it. A claim is recorded once per owner (claim_key
-- is a sha256 of the case and whitespace folded claim), so a repeated research
-- pass cannot stack copies.
--
-- Re-runnable.

CREATE TABLE IF NOT EXISTS company_findings (
    owner_id VARCHAR(64) NOT NULL,
    draft_id VARCHAR(64) NOT NULL,
    claim_key VARCHAR(64) NOT NULL,
    claim TEXT NOT NULL,
    evidence_kind VARCHAR(16) NOT NULL,
    evidence_ref TEXT NOT NULL,
    evidence_excerpt TEXT,
    recommendation TEXT NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'drafted',
    decided_by VARCHAR(320),
    decision_note TEXT,
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (owner_id, draft_id),
    CONSTRAINT company_findings_claim_uq UNIQUE (owner_id, claim_key),
    CONSTRAINT company_findings_claim_key_chk CHECK (claim_key ~ '^[0-9a-f]{64}$'),
    CONSTRAINT company_findings_kind_chk
        CHECK (evidence_kind IN ('source', 'measured', 'unverified')),
    CONSTRAINT company_findings_status_chk
        CHECK (status IN ('drafted', 'approved', 'rejected')),
    CONSTRAINT company_findings_ref_chk CHECK (length(btrim(evidence_ref)) > 0),
    CONSTRAINT company_findings_source_chk
        CHECK (evidence_kind <> 'source' OR evidence_ref ~ '^https://[^[:space:]]+$'),
    CONSTRAINT company_findings_decider_chk
        CHECK ((status = 'drafted') = (decided_by IS NULL))
);

CREATE INDEX IF NOT EXISTS company_findings_owner_created_idx
    ON company_findings (owner_id, created_at DESC);
