from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

FILE = Path(__file__).resolve().parent / "app/security/creator_read.py"


class GrantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = None
        if FILE.exists():
            spec = importlib.util.spec_from_file_location("creator_read_under_test", FILE)
            cls.mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = cls.mod
            spec.loader.exec_module(cls.mod)

    def module(self):
        self.assertIsNotNone(self.mod, "delegated read grant validator is not implemented")
        return self.mod

    def sample(self, scope="active"):
        now = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
        token = "cwread_" + "A" * 43
        cfg = {
            "enabled": True,
            "grant_id": "fce36945-c73d-42af-8a4c-765a6c2ae719",
            "scope": scope,
            "key_sha256": hashlib.sha256(token.encode()).hexdigest(),
            "not_before": (now - timedelta(minutes=1)).isoformat(),
            "expires_at": (now + timedelta(days=7)).isoformat(),
            "owner_id": "f5133f79-f597-40c3-98b0-017471432415",
            "owner_email": None,
            "projects": {"tqo": ["0250f4b1-736a-4fcd-8d2f-0ca27ebbe0c6"]},
        }
        if scope == "inventory":
            cfg.update(owner_id=None, owner_email="owner@example.com", projects={})
        return now, token, cfg

    def parse(self, cfg, header=None, now=None):
        m = self.module()
        n, t, _ = self.sample()
        return m.authenticate_grant(json.dumps(cfg), header or "CreatorRead " + t, now=now or n)

    def denied(self, cfg, header=None, now=None):
        m = self.module()
        with self.assertRaises(m.GrantRefused):
            self.parse(cfg, header, now)

    def test_extreme_offset_is_a_generic_refusal(self):
        _, _, cfg = self.sample()
        cfg["not_before"] = "0001-01-01T00:00:00+14:00"
        self.denied(cfg)

    def test_correct_form_but_different_key_is_refused(self):
        _, _, cfg = self.sample()
        self.denied(cfg, "CreatorRead cwread_" + "B" * 43)

    def test_equivalent_timezone_offsets_do_not_change_validity(self):
        now, _, cfg = self.sample()
        zone = timezone(timedelta(hours=3))
        cfg["not_before"] = (now - timedelta(minutes=1)).astimezone(zone).isoformat()
        cfg["expires_at"] = (now + timedelta(hours=1)).astimezone(zone).isoformat()
        accepted = self.parse(cfg, now=now)
        self.assertEqual(accepted.expires_at, now + timedelta(hours=1))
        self.denied(cfg, now=now + timedelta(hours=1))

    def test_default_closed(self):
        m = self.module()
        for raw in ("", "{}", "null", "[]", "{bad"):
            with self.subTest(raw=raw), self.assertRaises(m.GrantRefused):
                m.authenticate_grant(raw, None)

    def test_active_valid_and_scope_enforced(self):
        _, _, c = self.sample()
        g = self.parse(c)
        self.assertEqual(g.owner_id, c["owner_id"])
        self.assertTrue(g.allows("tqo", c["projects"]["tqo"][0]))
        self.assertFalse(g.allows("acx", c["projects"]["tqo"][0]))
        self.assertFalse(g.allows("tqo", "ef21448b-3e2b-40cd-8c7d-3f1d85c60354"))

    def test_wrong_auth_scheme_and_token(self):
        _, t, c = self.sample()
        for h in ("Bearer " + t, "CreatorRead wrong", "CreatorRead " + t + "x", "", "Basic " + t):
            self.denied(c, h if h else " ")

    def test_disabled_and_truthy_strings_refused(self):
        for val in (False, "true", 1, None):
            _, _, c = self.sample()
            c["enabled"] = val
            self.denied(c)

    def test_expired_future_and_overlong_grants_refused(self):
        n, _, c = self.sample()
        c["expires_at"] = n.isoformat()
        self.denied(c)
        c["expires_at"] = (n + timedelta(days=31)).isoformat()
        self.denied(c)
        c["expires_at"] = (n + timedelta(days=1)).isoformat()
        c["not_before"] = (n + timedelta(minutes=1)).isoformat()
        self.denied(c)

    def test_naive_time_rejected(self):
        _, _, c = self.sample()
        c["expires_at"] = "2026-10-22T12:00:00"
        self.denied(c)

    def test_bad_digest_rejected(self):
        _, _, c = self.sample()
        c["key_sha256"] = "abc"
        self.denied(c)

    def test_duplicate_json_key_rejected(self):
        n, t, c = self.sample()
        m = self.module()
        raw = json.dumps(c)
        raw = raw[:-1] + ',"enabled":true}'
        with self.assertRaises(m.GrantRefused):
            m.authenticate_grant(raw, "CreatorRead " + t, now=n)

    def test_unknown_config_key_rejected(self):
        _, _, c = self.sample()
        c["allow_all_projects"] = True
        self.denied(c)

    def test_invalid_owner_and_project_rejected(self):
        for owner in ("*", "", None, "owner@example.com"):
            _, _, c = self.sample()
            c["owner_id"] = owner
            self.denied(c)
        for p in ("*", "", None, "../../private"):
            _, _, c = self.sample()
            c["projects"] = {"tqo": [p]}
            self.denied(c)

    def test_empty_active_scope_rejected(self):
        _, _, c = self.sample()
        c["projects"] = {}
        self.denied(c)
        c["projects"] = {"tqo": []}
        self.denied(c)

    def test_unknown_brand_rejected(self):
        _, _, c = self.sample()
        c["projects"] = {"all": c["projects"]["tqo"]}
        self.denied(c)

    def test_duplicate_or_crossbrand_projects_rejected(self):
        _, _, c = self.sample()
        p = c["projects"]["tqo"][0]
        c["projects"]["tqo"].append(p)
        self.denied(c)
        c["projects"] = {"tqo": [p], "acx": [p]}
        self.denied(c)

    def test_inventory_cannot_read_project_content(self):
        _, _, c = self.sample("inventory")
        g = self.parse(c)
        self.assertFalse(g.allows("tqo", "0250f4b1-736a-4fcd-8d2f-0ca27ebbe0c6"))
        self.assertEqual(g.owner_email, "owner@example.com")

    def test_inventory_cannot_smuggle_project_scope(self):
        _, _, c = self.sample("inventory")
        c["projects"] = {"tqo": ["0250f4b1-736a-4fcd-8d2f-0ca27ebbe0c6"]}
        self.denied(c)

    def test_inventory_requires_exact_email_and_no_owner_override(self):
        for email in ("*", "@example.com", "owner@example.com\n", "OWNER@example.com"):
            _, _, c = self.sample("inventory")
            c["owner_email"] = email
            self.denied(c)
        _, _, c = self.sample("inventory")
        c["owner_id"] = "f5133f79-f597-40c3-98b0-017471432415"
        self.denied(c)

    def test_active_scope_has_no_email_fallback(self):
        _, _, c = self.sample()
        c["owner_email"] = "owner@example.com"
        self.denied(c)

    def test_header_and_json_bounds(self):
        m = self.module()
        n, _, c = self.sample()
        with self.assertRaises(m.GrantRefused):
            m.authenticate_grant(json.dumps(c), "CreatorRead " + "a" * 9000, now=n)
        with self.assertRaises(m.GrantRefused):
            m.authenticate_grant(" " * 13000, None, now=n)

    def test_no_raw_secret_in_grant_or_error(self):
        _, t, c = self.sample()
        g = self.parse(c)
        self.assertNotIn(t, repr(g))
        self.assertNotIn(t, str(g))
        m = self.module()
        try:
            self.parse(c, "CreatorRead " + t + "a")
        except m.GrantRefused as e:
            self.assertNotIn(t, str(e))


if __name__ == "__main__":
    unittest.main()
