import json
import unittest

import review_core as c
import review_registry as r
import test_review_gateway as fixtures
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


class RegistryTests(unittest.TestCase):
    setUp = fixtures.GatewayTests.setUp
    tearDown = fixtures.GatewayTests.tearDown
    signed_run = fixtures.GatewayTests.signed_run

    def test_registry_exports_only_verified_ai_summary_not_private_report(self):
        self.signed_run()
        folder = self.root / "runs" / "20261021T120000Z-fixture"
        key = Ed25519PrivateKey.generate()
        pub = self.root / "issuer" / "receipt-ed25519.pub.pem"
        pub.write_bytes(
            key.public_key().public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
            )
        )
        p = json.loads((folder / "packet.json").read_text())
        old = json.loads((folder / "receipt.json").read_text())
        old["signature"] = (
            __import__("base64").b64encode(key.sign(c.canonical(old["payload"]))).decode()
        )
        (folder / "receipt.json").write_bytes(c.canonical(old))
        result = r.export_summary(self.root, folder.name, key)
        self.assertTrue(result.exists())
        envelope = json.loads(result.read_text())
        payload = json.loads(envelope["payload"])
        self.assertEqual(payload["reviewKind"], "AI_REVIEW")
        self.assertFalse(payload["publicationAuthorized"])
        self.assertNotIn("report", payload)
        self.assertNotIn("artifact", payload)
        got = r.lookup(self.root, self.brands, "TQO", "script", p["artifactSha256"])
        self.assertEqual(got["signature"], envelope["signature"])
        self.assertEqual(
            r.lookup(self.root, self.brands, "TQO", "policy_brief", p["artifactSha256"])["state"],
            "HOLD",
        )
        (self.brands / "tqo" / "gates.md").write_text("Policy changed.")
        self.assertEqual(
            r.lookup(self.root, self.brands, "TQO", "script", p["artifactSha256"])["state"], "HOLD"
        )

    def test_traversal_and_invalid_query_hold(self):
        for brand, scope, h in [
            ("../issuer", "script", "a" * 64),
            ("TQO", "../issuer", "a" * 64),
            ("TQO", "script", "../../secret"),
        ]:
            self.assertEqual(r.lookup(self.root, self.brands, brand, scope, h)["state"], "HOLD")


if __name__ == "__main__":
    unittest.main()
