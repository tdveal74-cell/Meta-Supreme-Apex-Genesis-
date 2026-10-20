"""Stage 2 history audit persistence contract tests (no real database)."""
import unittest

from app.services.arf_recovery_history import append_history, read_history
from services.agent_runtime.reliability.lineage import HistoryConflict, HistoryEvent


class FakeRows:
    def __init__(self, rows): self.rows=rows
    def mappings(self): return self
    def all(self): return self.rows

class SpySession:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.queries = []
    async def execute(self, statement, params=None):
        self.queries.append((str(statement), params))
        return FakeRows(self.rows)


def e():
    return HistoryEvent(event_id='EVENT-1', owner_id='owner-one',root_task_id='ROOT-1',
                        task_id='TASK-1',parent_event_id='',delegated_from_event_id='',
                        failure_fingerprint='a'*64,outcome_digest='b'*64,
                        evidence_revision='REV-1',control='evidence_gate',attempt_no=1)


class StoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_reads_are_owner_scoped(self):
        s=SpySession()
        self.assertEqual(await read_history(s,owner_id='owner-one',root_task_id='ROOT-1'),())
        self.assertIn('WHERE owner_id',s.queries[0][0])
        self.assertEqual(s.queries[0][1]['owner_id'],'owner-one')

    async def test_write_denied_by_default(self):
        s=SpySession()
        with self.assertRaises(PermissionError):
            await append_history(s,owner_id='owner-one',event=e(),policy_digest='c'*64)
        self.assertFalse(s.queries)

    async def test_review_authorized_insert_is_separate_from_observer(self):
        s=SpySession()
        await append_history(s,owner_id='owner-one',event=e(),policy_digest='c'*64,
                             shadow_audit_write_authorized=True)
        self.assertEqual(len(s.queries),2)
        self.assertIn('INSERT INTO arf_shadow_history',s.queries[-1][0])
        self.assertNotIn('approval_token',str(s.queries[-1][1]))

    async def test_oversized_ids_refused_before_db_query(self):
        from dataclasses import replace
        for field, n in (("event_id", 81), ("root_task_id", 65),
                         ("task_id", 65), ("control", 81),
                         ("parent_event_id", 81), ("delegated_from_event_id", 81)):
            with self.subTest(field=field):
                s = SpySession()
                with self.assertRaises(HistoryConflict):
                    await append_history(s, owner_id="owner-one",
                                         event=replace(e(), **{field: "x" * n}),
                                         policy_digest="c" * 64,
                                         shadow_audit_write_authorized=True)
                self.assertFalse(s.queries)

    async def test_cross_owner_write_denied(self):
        s=SpySession()
        with self.assertRaisesRegex(HistoryConflict,'owner'):
            await append_history(s,owner_id='not-owner',event=e(),policy_digest='c'*64,
                                 shadow_audit_write_authorized=True)
        self.assertFalse(s.queries)

    async def test_existing_parent_missing_refuses_insert(self):
        from dataclasses import replace
        s=SpySession()
        with self.assertRaisesRegex(HistoryConflict,'ancestor'):
            await append_history(s,owner_id='owner-one',event=replace(e(),parent_event_id='MISSING'),
                                 policy_digest='c'*64,shadow_audit_write_authorized=True)
        self.assertEqual(len(s.queries),1)

if __name__ == "__main__":
    unittest.main()
