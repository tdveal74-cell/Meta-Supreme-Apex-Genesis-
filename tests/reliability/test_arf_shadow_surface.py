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

    async def test_evidence_reads_have_separate_fresh_session(self):
        class Context:
            async def __aenter__(self):
                return snapshot
            async def __aexit__(self, *args):
                return False

        original, snapshot = object(), object()
        with patch.dict("os.environ", {"ARF_SHADOW_READ_ENABLED": "true"}):
            with patch("app.api.v1.arf_shadow.agent_tasks_service.get_task",
                       new_callable=AsyncMock, return_value=SimpleNamespace(id="TASK")):
                with patch("app.api.v1.arf_shadow.AsyncSessionLocal", return_value=Context()):
                    with patch("app.api.v1.arf_shadow.observe_persisted_task",
                               new_callable=AsyncMock,
                               return_value=SimpleNamespace(to_dict=lambda: {"verdict": "WOULD_HOLD"})) as observe:
                        result = await reliability_shadow("TASK", SimpleNamespace(id="owner-a"), db=original)
                        self.assertEqual(result["verdict"], "WOULD_HOLD")
                        self.assertIs(observe.await_args.kwargs["db"], snapshot)
                        self.assertIs(observe.await_args.kwargs["gate_reader"]._db, snapshot)

    async def test_wrong_owner_returns_not_found_without_shadow_call(self):
        with patch.dict("os.environ", {"ARF_SHADOW_READ_ENABLED": "true"}):
            with patch("app.api.v1.arf_shadow.agent_tasks_service.get_task", new_callable=AsyncMock, return_value=None) as get:
                with patch("app.api.v1.arf_shadow.observe_persisted_task", new_callable=AsyncMock) as observe:
                    with self.assertRaises(HTTPException) as failure:
                        await reliability_shadow("TASK", SimpleNamespace(id="owner-a"), db=None)
                    self.assertEqual(failure.exception.status_code, 404)
                    get.assert_awaited_once_with(None, owner_id="owner-a", task_id="TASK")
                    observe.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
