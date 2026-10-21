"""Offline client tests. They never read a production credential or call a network."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

FILE = Path(__file__).resolve().parent / "tools/creator_workspace_reader.py"
TOKEN = "cwread_" + "A" * 43
OWNER = "f5133f79-f597-40c3-98b0-017471432415"
GRANT = "fce36945-c73d-42af-8a4c-765a6c2ae719"
PROJECT = "0250f4b1-736a-4fcd-8d2f-0ca27ebbe0c6"
OTHER = "ef21448b-3e2b-40cd-8c7d-3f1d85c60354"
ITEM = "84d59550-f332-42a1-915c-486c3ad7c445"
BASE = "https://api-production-5644.up.railway.app/api/v1/creator-workspace"


class ClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = None
        if FILE.exists():
            spec = importlib.util.spec_from_file_location("creator_reader_client_test", FILE)
            cls.mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = cls.mod
            spec.loader.exec_module(cls.mod)

    def setUp(self):
        self.assertIsNotNone(self.mod, "metadata-only client is not implemented")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.key = Path(self.tmp.name) / "devon-read.key"
        self.key.write_text(TOKEN + "\n")
        self.key.chmod(0o600)
        self.expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        self.cfg = {
            "schema": "creator-workspace-reader-v1",
            "enabled": True,
            "api_base": BASE,
            "grant_id": GRANT,
            "scope": "active",
            "owner_id": OWNER,
            "projects": {"tqo": [PROJECT]},
            "expires_at": self.expiry,
        }
        self.status = {
            "principal": "CREATOR_WORKSPACE_METADATA_READER",
            "grant_id": GRANT,
            "owner_id": OWNER,
            "scope": "active",
            "expires_at": self.expiry,
            "project_scopes": {"tqo": [PROJECT]},
            "knowledge_writes": False,
            "provider_calls": False,
            "publishing_authorized": False,
        }
        self.metadata = {
            "brand": "tqo",
            "project_id": PROJECT,
            "grant_id": GRANT,
            "items": [
                {
                    "id": ITEM,
                    "project_id": PROJECT,
                    "title": "Source",
                    "status": "ready",
                    "source_type": "markdown",
                    "source_uri": "https://example.com/source",
                    "created_at": "2026-10-20T00:00:00Z",
                    "updated_at": "2026-10-21T00:00:00Z",
                }
            ],
            "offset": 0,
            "has_more": False,
            "source_contents_fetched": False,
            "publishing_authorized": False,
            "provenance_state": "METADATA_ONLY_ORIGINAL_SOURCE_NOT_READ",
        }
        self.calls = []
        self.response_code = 200
        self.response_type = "application/json"
        self.override_body = None

    def transport(self, url, headers):
        self.calls.append((url, headers))
        if self.override_body is not None:
            body = self.override_body
        else:
            body = json.dumps(self.status if url.endswith("/status") else self.metadata).encode()
        return self.response_code, self.response_type, body

    def reader(self):
        return self.mod.Reader(self.cfg, key_file=self.key, transport=self.transport)

    def read(self, **kw):
        return self.reader().metadata(brand="tqo", project_id=PROJECT, **kw)

    def test_valid_metadata_is_not_content_or_publication(self):
        result = self.read()
        self.assertEqual([x["id"] for x in result["items"]], [ITEM])
        self.assertEqual(result["state"], "LIVE_METADATA_CANDIDATES_ONLY")
        self.assertFalse(result["source_contents_fetched"])
        self.assertFalse(result["publishing_authorized"])
        self.assertEqual(len(self.calls), 2)
        self.assertTrue(all(u.startswith(BASE + "/") for u, _ in self.calls))
        self.assertTrue(all(h["Authorization"] == "CreatorRead " + TOKEN for _, h in self.calls))
        self.assertNotIn(TOKEN, json.dumps(result))

    def test_disabled_config_refuses_before_transport(self):
        for enabled in (False, "true", 1, None):
            self.cfg["enabled"] = enabled
            with self.assertRaises(self.mod.ReaderHold):
                self.read()
        self.assertEqual(self.calls, [])

    def test_origin_is_pinned(self):
        for url in (
            "http://api-production-5644.up.railway.app/api/v1/creator-workspace",
            "https://attacker.example/api",
            BASE + "?secret=x",
            "https://user:pass@api-production-5644.up.railway.app/api/v1/creator-workspace",
        ):
            self.cfg["api_base"] = url
            with self.assertRaises(self.mod.ReaderHold):
                self.read()
        self.assertEqual(self.calls, [])

    def test_foreign_project_and_brand_refused_before_transport(self):
        reader = self.reader()
        with self.assertRaises(self.mod.ReaderHold):
            reader.metadata(brand="tqo", project_id=OTHER)
        with self.assertRaises(self.mod.ReaderHold):
            reader.metadata(brand="acx", project_id=PROJECT)
        self.assertEqual(self.calls, [])

    def test_request_bounds(self):
        for values in (
            {"limit": 21},
            {"limit": 0},
            {"limit": True},
            {"offset": -1},
            {"offset": 5001},
        ):
            with self.assertRaises(self.mod.ReaderHold):
                self.read(**values)
        self.assertEqual(self.calls, [])

    def test_public_or_linked_key_refused(self):
        self.key.chmod(0o644)
        with self.assertRaises(self.mod.ReaderHold):
            self.read()
        self.key.chmod(0o600)
        alias = self.key.with_name("link.key")
        alias.symlink_to(self.key)
        with self.assertRaises(self.mod.ReaderHold):
            self.mod.Reader(self.cfg, key_file=alias, transport=self.transport).metadata(
                brand="tqo", project_id=PROJECT
            )
        self.assertEqual(self.calls, [])

    def test_malformed_personal_token_refused(self):
        self.key.write_text("eyJ.personal.jwt")
        with self.assertRaises(self.mod.ReaderHold):
            self.read()
        self.assertEqual(self.calls, [])

    def test_missing_key_does_not_fallback(self):
        self.key.unlink()
        with self.assertRaises(self.mod.ReaderHold):
            self.read()
        self.assertEqual(self.calls, [])

    def test_redirect_and_non200_refused(self):
        for code in (301, 302, 307, 308, 401, 403, 404, 500):
            self.response_code = code
            with self.assertRaises(self.mod.ReaderHold):
                self.read()

    def test_oversized_or_nonjson_reply_refused(self):
        self.override_body = b"x" * (128 * 1024 + 1)
        with self.assertRaises(self.mod.ReaderHold):
            self.read()
        self.override_body = b"<html>login</html>"
        self.response_type = "text/html"
        with self.assertRaises(self.mod.ReaderHold):
            self.read()

    def test_duplicate_json_key_refused(self):
        self.override_body = b'{"grant_id":"a","grant_id":"b"}'
        with self.assertRaises(self.mod.ReaderHold):
            self.read()

    def test_wrong_owner_or_grant_status_refused(self):
        for field in ("owner_id", "grant_id"):
            old = self.status[field]
            self.status[field] = OTHER
            with self.assertRaises(self.mod.ReaderHold):
                self.read()
            self.status[field] = old

    def test_server_scope_expansion_refused(self):
        self.status["project_scopes"]["acx"] = [OTHER]
        with self.assertRaises(self.mod.ReaderHold):
            self.read()

    def test_server_effect_permissions_refused(self):
        for field in ("knowledge_writes", "provider_calls", "publishing_authorized"):
            self.status[field] = True
            with self.assertRaises(self.mod.ReaderHold):
                self.read()
            self.status[field] = False

    def test_status_expiry_is_enforced(self):
        self.status["expires_at"] = "2000-01-01T00:00:00Z"
        with self.assertRaises(self.mod.ReaderHold):
            self.read()

    def test_config_expiry_is_enforced(self):
        self.cfg["expires_at"] = "2000-01-01T00:00:00Z"
        with self.assertRaises(self.mod.ReaderHold):
            self.read()
        self.assertEqual(self.calls, [])

    def test_wrong_response_brand_project_or_grant_refused(self):
        for field in ("brand", "project_id", "grant_id"):
            old = self.metadata[field]
            self.metadata[field] = "acx" if field == "brand" else OTHER
            with self.assertRaises(self.mod.ReaderHold):
                self.read()
            self.metadata[field] = old

    def test_one_foreign_item_refuses_whole_response(self):
        row = copy.deepcopy(self.metadata["items"][0])
        row["id"] = OTHER
        row["project_id"] = OTHER
        self.metadata["items"].append(row)
        with self.assertRaises(self.mod.ReaderHold):
            self.read()

    def test_duplicate_ids_refused(self):
        self.metadata["items"].append(copy.deepcopy(self.metadata["items"][0]))
        with self.assertRaises(self.mod.ReaderHold):
            self.read()

    def test_response_exceeding_requested_limit_refused(self):
        row = copy.deepcopy(self.metadata["items"][0])
        row["id"] = OTHER
        self.metadata["items"].append(row)
        with self.assertRaises(self.mod.ReaderHold):
            self.read(limit=1)

    def test_extra_private_fields_are_not_returned(self):
        self.metadata["items"][0].update(
            content="PRIVATE_BODY", metadata={"password": "PRIVATE_META"}
        )
        self.metadata["secret"] = "PRIVATE_TOP"
        result = self.read()
        for text in ("PRIVATE_BODY", "PRIVATE_META", "PRIVATE_TOP", TOKEN):
            self.assertNotIn(text, json.dumps(result))

    def test_content_or_publication_flag_cannot_be_promoted(self):
        for field in ("source_contents_fetched", "publishing_authorized"):
            self.metadata[field] = True
            with self.assertRaises(self.mod.ReaderHold):
                self.read()
            self.metadata[field] = False

    def test_invalid_date_or_status_refused(self):
        self.metadata["items"][0]["updated_at"] = "not-a-date"
        with self.assertRaises(self.mod.ReaderHold):
            self.read()
        self.metadata["items"][0]["updated_at"] = "2026-10-21T00:00:00Z"
        self.metadata["items"][0]["status"] = "approved"
        with self.assertRaises(self.mod.ReaderHold):
            self.read()

    def test_url_query_secret_is_removed(self):
        self.metadata["items"][0]["source_uri"] = "https://example.com/path?token=SECRET#SECRET"
        result = self.read()
        self.assertEqual(result["items"][0]["source_uri"], "https://example.com/path")
        self.assertNotIn("SECRET", json.dumps(result))

    def test_inventory_is_metadata_only_and_bound_to_status_owner(self):
        self.cfg.update(scope="inventory", owner_id=None, projects={})
        self.status.update(scope="inventory", project_scopes={})
        self.metadata = {
            "scope": "inventory",
            "owner_id": OWNER,
            "items": [
                {
                    "id": PROJECT,
                    "name": "The Quiet Operator",
                    "status": "active",
                    "private": "NO_RETURN",
                }
            ],
            "offset": 0,
            "has_more": False,
            "source_contents_fetched": False,
            "publishing_authorized": False,
        }
        result = self.reader().inventory()
        self.assertEqual(result["owner_id"], OWNER)
        self.assertEqual(result["items"][0]["id"], PROJECT)
        self.assertNotIn("NO_RETURN", json.dumps(result))
        self.assertFalse(result["publishing_authorized"])
        self.metadata["owner_id"] = OTHER
        with self.assertRaises(self.mod.ReaderHold):
            self.reader().inventory()

    def test_inventory_and_active_methods_cannot_cross(self):
        with self.assertRaises(self.mod.ReaderHold):
            self.reader().inventory()
        self.cfg.update(scope="inventory", owner_id=None, projects={})
        with self.assertRaises(self.mod.ReaderHold):
            self.read()
        self.assertEqual(self.calls, [])

    def test_unknown_config_fields_cannot_supply_a_token(self):
        self.cfg["token"] = TOKEN
        with self.assertRaises(self.mod.ReaderHold):
            self.read()
        self.assertEqual(self.calls, [])

    def test_crossbrand_duplicate_project_config_refused(self):
        self.cfg["projects"]["acx"] = [PROJECT]
        with self.assertRaises(self.mod.ReaderHold):
            self.read()
        self.assertEqual(self.calls, [])

    def test_expiry_checked_again_before_each_request(self):
        reader = self.reader()
        reader.expiry = datetime(2000, 1, 1, tzinfo=timezone.utc)
        with self.assertRaises(self.mod.ReaderHold):
            reader.metadata(brand="tqo", project_id=PROJECT)
        self.assertEqual(self.calls, [])

    def test_redirect_handler_never_supplies_a_new_request(self):
        handler = self.mod._NoRedirect()
        self.assertIsNone(
            handler.redirect_request(None, None, 302, "redirect", {}, "https://other.example")
        )

    def test_transport_error_is_generic(self):
        def bad(*args):
            raise RuntimeError("Credential " + TOKEN)

        with self.assertRaises(self.mod.ReaderHold) as caught:
            self.mod.Reader(self.cfg, key_file=self.key, transport=bad).metadata(
                brand="tqo", project_id=PROJECT
            )
        self.assertNotIn(TOKEN, str(caught.exception))


if __name__ == "__main__":
    unittest.main()
