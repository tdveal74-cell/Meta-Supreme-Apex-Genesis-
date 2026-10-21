"""Stage 3 default-disabled, owner-scoped API smoke contract."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.api.v1.arf_shadow import reliability_shadow, shadow_read_enabled


class ShadowSurfaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_by_default(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(shadow_read_enabled())
            with self.assertRaises(HTTPException) as result:
                await reliability_shadow("TASK", SimpleNamespace(id="owner"), db=None)
            self.assertEqual(result.exception.status_code, 404)

    async def test_unknown_flag_does_not_enable(self):
        with patch.dict("os.environ", {"ARF_SHADOW_READ_ENABLED": "release"}):
            self.assertFalse(shadow_read_enabled())

    async def test_auth_connection_released_before_rate_limit_and_snapshot(self):
        # An authenticated GET already has a DB transaction. Keeping that
        # checkout open while a second session opens can exhaust the pool.
        order = []
        original = SimpleNamespace(rollback=AsyncMock(side_effect=lambda: order.append("release")))

        def budget_call(owner):
            order.append("budget")

        def task_call(db, *, owner_id, task_id):
            self.assertIs(db, original)
            order.append("lookup")
            return SimpleNamespace(id=task_id)

        def observe_call(**kwargs):
            self.assertIs(kwargs["db"], original)
            self.assertIs(kwargs["gate_reader"]._db, original)
            order.append("observe")
            return SimpleNamespace(to_dict=lambda: {"verdict": "WOULD_HOLD"})

        with patch.dict("os.environ", {"ARF_SHADOW_READ_ENABLED": "true"}):
            with patch("app.api.v1.arf_shadow.consume_shadow_budget",
                       new_callable=AsyncMock, side_effect=budget_call):
                with patch("app.api.v1.arf_shadow.agent_tasks_service.get_task",
                           new_callable=AsyncMock, side_effect=task_call):
                    with patch("app.api.v1.arf_shadow.AsyncSessionLocal", create=True,
                               side_effect=AssertionError("route allocated a second session")):
                        with patch("app.api.v1.arf_shadow.observe_persisted_task",
                                   new_callable=AsyncMock, side_effect=observe_call):
                            result = await reliability_shadow("TASK", SimpleNamespace(id="owner-a"), db=original)
        self.assertEqual(result["verdict"], "WOULD_HOLD")
        self.assertEqual(order, ["release", "budget", "lookup", "release", "observe"])
        self.assertEqual(original.rollback.await_count, 2)

    async def test_wrong_owner_returns_not_found_without_shadow_call(self):
        with patch.dict("os.environ", {"ARF_SHADOW_READ_ENABLED": "true"}):
            with patch("app.api.v1.arf_shadow.consume_shadow_budget", new_callable=AsyncMock) as budget:
                with patch("app.api.v1.arf_shadow.agent_tasks_service.get_task", new_callable=AsyncMock, return_value=None) as get:
                    with patch("app.api.v1.arf_shadow.observe_persisted_task", new_callable=AsyncMock) as observe:
                        db = SimpleNamespace(rollback=AsyncMock())
                        with self.assertRaises(HTTPException) as failure:
                            await reliability_shadow("TASK", SimpleNamespace(id="owner-a"), db=db)
                        self.assertEqual(failure.exception.status_code, 404)
                        budget.assert_awaited_once_with("owner-a")
                        get.assert_awaited_once_with(db, owner_id="owner-a", task_id="TASK")
                        observe.assert_not_awaited()



if __name__ == "__main__":
    unittest.main()
