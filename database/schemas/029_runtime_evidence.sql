-- Durable result references, verification receipts, and immutable skill history.
CREATE TABLE IF NOT EXISTS agent_tool_results (
 id varchar(64) PRIMARY KEY,
 owner_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 task_id varchar(64) NOT NULL REFERENCES agent_tasks(id) ON DELETE CASCADE,
 step_id varchar(64) NOT NULL, generation integer NOT NULL,
 body text NOT NULL, content_hash varchar(64) NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 CONSTRAINT uq_agent_tool_result_step_generation UNIQUE(owner_id,task_id,step_id,generation)
);
CREATE TABLE IF NOT EXISTS agent_verifications (
 id varchar(64) PRIMARY KEY,
 owner_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 task_id varchar(64) NOT NULL REFERENCES agent_tasks(id) ON DELETE CASCADE,
 generation integer NOT NULL, body text NOT NULL, content_hash varchar(64) NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS agent_skill_revisions (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 skill_name varchar(200) NOT NULL, version integer NOT NULL CHECK(version>0),
 parent_version integer, description text NOT NULL, instructions text NOT NULL,
 content_hash varchar(64) NOT NULL, provenance varchar(120) NOT NULL,
 evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
 created_at timestamptz NOT NULL DEFAULT now(),
 CONSTRAINT uq_agent_skill_revision_version UNIQUE(owner_id,skill_name,version)
);
CREATE TABLE IF NOT EXISTS skill_evaluation_runs (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 skill_name varchar(200) NOT NULL, content_hash varchar(64) NOT NULL,
 suite_id varchar(200) NOT NULL, suite_version varchar(100) NOT NULL,
 source_task_id varchar(100) NOT NULL, evidence jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_agent_tool_results_owner_task ON agent_tool_results(owner_id,task_id);
CREATE INDEX IF NOT EXISTS ix_agent_verifications_owner_task ON agent_verifications(owner_id,task_id);
-- API code never updates evidence/history. SQL updates also fail loudly.
CREATE OR REPLACE FUNCTION refuse_runtime_evidence_update() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'runtime evidence is immutable'; END $$;
DROP TRIGGER IF EXISTS immutable_tool_results ON agent_tool_results;
CREATE TRIGGER immutable_tool_results BEFORE UPDATE ON agent_tool_results FOR EACH ROW EXECUTE FUNCTION refuse_runtime_evidence_update();
DROP TRIGGER IF EXISTS immutable_verifications ON agent_verifications;
CREATE TRIGGER immutable_verifications BEFORE UPDATE ON agent_verifications FOR EACH ROW EXECUTE FUNCTION refuse_runtime_evidence_update();
DROP TRIGGER IF EXISTS immutable_skill_revisions ON agent_skill_revisions;
CREATE TRIGGER immutable_skill_revisions BEFORE UPDATE ON agent_skill_revisions FOR EACH ROW EXECUTE FUNCTION refuse_runtime_evidence_update();
DROP TRIGGER IF EXISTS immutable_skill_evaluations ON skill_evaluation_runs;
CREATE TRIGGER immutable_skill_evaluations BEFORE UPDATE ON skill_evaluation_runs FOR EACH ROW EXECUTE FUNCTION refuse_runtime_evidence_update();

-- Retention deletion is allowed only as an owning user/task FK cascade.
CREATE OR REPLACE FUNCTION refuse_runtime_evidence_delete() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM users WHERE id=OLD.owner_id) THEN RETURN OLD; END IF;
 IF TG_TABLE_NAME IN ('agent_tool_results','agent_verifications') THEN
   IF NOT EXISTS (SELECT 1 FROM agent_tasks WHERE id=OLD.task_id) THEN RETURN OLD; END IF;
 END IF;
 RAISE EXCEPTION 'runtime evidence cannot be deleted directly';
END $$;
DROP TRIGGER IF EXISTS retain_tool_results ON agent_tool_results;
CREATE TRIGGER retain_tool_results BEFORE DELETE ON agent_tool_results FOR EACH ROW EXECUTE FUNCTION refuse_runtime_evidence_delete();
DROP TRIGGER IF EXISTS retain_verifications ON agent_verifications;
CREATE TRIGGER retain_verifications BEFORE DELETE ON agent_verifications FOR EACH ROW EXECUTE FUNCTION refuse_runtime_evidence_delete();
DROP TRIGGER IF EXISTS retain_skill_revisions ON agent_skill_revisions;
CREATE TRIGGER retain_skill_revisions BEFORE DELETE ON agent_skill_revisions FOR EACH ROW EXECUTE FUNCTION refuse_runtime_evidence_delete();
DROP TRIGGER IF EXISTS retain_skill_evaluations ON skill_evaluation_runs;
CREATE TRIGGER retain_skill_evaluations BEFORE DELETE ON skill_evaluation_runs FOR EACH ROW EXECUTE FUNCTION refuse_runtime_evidence_delete();
