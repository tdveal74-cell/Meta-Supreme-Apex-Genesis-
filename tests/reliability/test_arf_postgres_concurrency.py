"""Real, isolated PostgreSQL concurrency acceptance for ARF shadow readers.

Runs only when ARF_ISOLATED_TEST_DATABASE_URL points to a disposable database.
Never run against production, shared fixtures, or an existing application DB.
"""
from __future__ import annotations

import asyncio
import json
import os
import unittest
from dataclasses import replace

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.services.arf_evidence_source import collect_evidence
from app.services.arf_recovery_history import append_history
from services.agent_runtime.reliability.lineage import HistoryConflict, HistoryEvent

DSN = os.getenv("ARF_ISOLATED_TEST_DATABASE_URL")
try:
    _url = make_url(DSN) if DSN else None
except Exception:
    _url = None
_SAFE_DISPOSABLE = bool(_url and _url.database == "arf_shadow_test"
                        and _url.host == "arf-pg" and _url.username == "arf_tmp")
OWNER = "22222222-2222-4222-8222-222222222222"
ROOT = "ARF-ROOT"
TASK = "ARF-TASK"


class PausingSession(AsyncSession):
    """Pause before reading intents to insert a concurrent committed effect."""

    ready: asyncio.Event | None = None
    resume: asyncio.Event | None = None

    async def execute(self, statement, *args, **kwargs):
        if "FROM agent_effect_intents" in str(statement) and self.ready and self.resume:
            self.ready.set()
            await asyncio.wait_for(self.resume.wait(), 5)
        return await super().execute(statement, *args, **kwargs)


@unittest.skipUnless(_SAFE_DISPOSABLE, "needs dedicated arf-pg disposable DB")
class IsolatedPostgresConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(DSN, pool_size=4, max_overflow=0)
        self.session = async_sessionmaker(self.engine, expire_on_commit=False)
        self.pausing = async_sessionmaker(self.engine, class_=PausingSession,
                                          expire_on_commit=False)
        async with self.engine.begin() as c:
            for name in ("arf_shadow_history", "agent_effect_receipts",
                         "agent_effect_intents", "agent_tasks", "projects", "users"):
                await c.execute(text(f"DROP TABLE IF EXISTS {name} CASCADE"))
            await c.execute(text("CREATE TABLE users (id UUID PRIMARY KEY)"))
            await c.execute(text("CREATE TABLE projects (id UUID PRIMARY KEY)"))
            await c.execute(text("INSERT INTO users (id) VALUES (:owner)"), {"owner": OWNER})
            await c.execute(text("""
                CREATE TABLE agent_tasks (
                  id VARCHAR(64) PRIMARY KEY, owner_id UUID NOT NULL REFERENCES users(id),
                  project_id UUID NULL REFERENCES projects(id), goal TEXT NOT NULL,
                  state VARCHAR(32) NOT NULL, current_step INTEGER NOT NULL DEFAULT 0,
                  payload JSONB NOT NULL, lease_token VARCHAR(64), lease_owner VARCHAR(200),
                  lease_expires_at TIMESTAMPTZ, execution_generation BIGINT NOT NULL DEFAULT 1,
                  created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL
                )"""))
            await c.execute(text("""
                CREATE TABLE agent_effect_intents (
                  id VARCHAR(64) PRIMARY KEY, intent_id VARCHAR(64) NOT NULL,
                  task_id VARCHAR(64) NOT NULL REFERENCES agent_tasks(id),
                  owner_id UUID NOT NULL REFERENCES users(id), step_id VARCHAR(64) NOT NULL,
                  tool_name VARCHAR(200) NOT NULL, arguments_hash VARCHAR(64) NOT NULL,
                  idempotency_key VARCHAR(200) NOT NULL, execution_generation BIGINT NOT NULL,
                  lease_token VARCHAR(64), created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )"""))
            await c.execute(text("""
                CREATE TABLE agent_effect_receipts (
                  id VARCHAR(64) PRIMARY KEY, intent_id VARCHAR(64) NOT NULL,
                  task_id VARCHAR(64) NOT NULL REFERENCES agent_tasks(id),
                  owner_id UUID NOT NULL REFERENCES users(id),
                  status VARCHAR(16) NOT NULL, provider_receipt_id VARCHAR(200) NOT NULL,
                  raw_response JSONB NOT NULL, execution_generation BIGINT NOT NULL,
                  lease_token VARCHAR(64), recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )"""))
            await c.execute(text("""
                CREATE TABLE arf_shadow_history (
                  event_id VARCHAR(80) PRIMARY KEY,
                  recorded_sequence BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,
                  owner_id UUID NOT NULL REFERENCES users(id), root_task_id VARCHAR(64) NOT NULL,
                  task_id VARCHAR(64) NOT NULL,
                  parent_event_id VARCHAR(80) NULL REFERENCES arf_shadow_history(event_id),
                  delegated_from_event_id VARCHAR(80) NULL REFERENCES arf_shadow_history(event_id),
                  failure_fingerprint CHAR(64) NOT NULL, outcome_digest CHAR(64) NOT NULL,
                  evidence_revision VARCHAR(128) NOT NULL, control VARCHAR(80) NOT NULL,
                  attempt_no INTEGER NOT NULL CHECK (attempt_no > 0),
                  policy_digest CHAR(64) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                  UNIQUE (owner_id, root_task_id, failure_fingerprint, attempt_no)
                )"""))

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_second_history_writer_waits_then_gets_typed_conflict(self):
        event = HistoryEvent("ARF-EVENT1", OWNER, ROOT, TASK, "", "",
                             "a" * 64, "b" * 64, "REV-1", "evidence_gate", 1)
        first_done = asyncio.Event()
        first_release = asyncio.Event()

        async def writer_a():
            async with self.session() as session:
                async with session.begin():
                    await append_history(session, owner_id=OWNER, event=event,
                                         policy_digest="c"*64,
                                         shadow_audit_write_authorized=True)
                    first_done.set()
                    await asyncio.wait_for(first_release.wait(), 5)

        async def writer_b():
            await first_done.wait()
            async with self.session() as session:
                async with session.begin():
                    await append_history(session, owner_id=OWNER,
                                         event=replace(event, event_id="ARF-EVENT2"),
                                         policy_digest="c"*64,
                                         shadow_audit_write_authorized=True)

        a = asyncio.create_task(writer_a())
        await asyncio.wait_for(first_done.wait(), 5)
        b = asyncio.create_task(writer_b())
        await asyncio.sleep(0.2)
        self.assertFalse(b.done(), "contending writer must not read stale lineage")
        first_release.set()
        await asyncio.wait_for(a, 5)
        with self.assertRaises(HistoryConflict):
            await asyncio.wait_for(b, 5)
        async with self.session() as s:
            count = await s.scalar(text("SELECT count(*) FROM arf_shadow_history"))
        self.assertEqual(count, 1)

    async def test_effect_reads_share_pre_concurrent_write_snapshot(self):
        from app.services.agent_effect_receipts import arguments_hash
        payload = {"task_id": TASK, "state": "completed",
                   "plan": {"steps": [{"step_id": "one",
                                       "tool_call": {"name": "repo.write", "arguments": {"x": 1}}}]}}
        async with self.engine.begin() as c:
            await c.execute(text("""
                INSERT INTO agent_tasks
                (id, owner_id, goal, state, payload, created_at, updated_at)
                VALUES (:task, :owner, 'diagnostic', 'completed', CAST(:payload AS JSONB), now(), now())
            """), {"task": TASK, "owner": OWNER, "payload": json.dumps(payload)})
        reader_ready, reader_continue = asyncio.Event(), asyncio.Event()

        async def read_snapshot():
            async with self.pausing() as s:
                s.ready, s.resume = reader_ready, reader_continue
                return await collect_evidence(db=s, approval_db=None,
                                              task_id=TASK, owner_id=OWNER, domain="devon",
                                              workflow_stage="build", policy_digest="a"*64)

        reader = asyncio.create_task(read_snapshot())
        await asyncio.wait_for(reader_ready.wait(), 5)
        async with self.engine.begin() as c:
            await c.execute(text("""
                INSERT INTO agent_effect_intents
                (id, intent_id, task_id, owner_id, step_id, tool_name, arguments_hash,
                 idempotency_key, execution_generation, lease_token)
                VALUES ('IR1','INT1',:task,:owner,'one','repo.write',:hash,'KEY',1,'LEASE')
            """), {"task":TASK, "owner": OWNER,"hash":arguments_hash({"x":1})})
            await c.execute(text("""
                INSERT INTO agent_effect_receipts
                (id, intent_id, task_id, owner_id, status, provider_receipt_id,
                 raw_response, execution_generation, lease_token)
                VALUES ('RE1','INT1',:task,:owner,'succeeded','PROVIDER','{}',1,'LEASE')
            """), {"task":TASK, "owner": OWNER})
        reader_continue.set()
        _, evidence = await asyncio.wait_for(reader, 5)
        self.assertFalse(evidence.receipted_step_ids,
                         "new effects must not be blended into older task snapshot")
        async with self.session() as s:
            self.assertEqual(await s.scalar(text("SELECT count(*) FROM agent_effect_receipts")), 1)
