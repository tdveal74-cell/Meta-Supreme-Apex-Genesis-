import copy
import datetime
import hashlib
import unittest

import review_core as c
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

NOW = datetime.datetime(2026, 10, 21, 10, tzinfo=datetime.timezone.utc)


def packet(brand="TQO", producer="openai"):
    src = "A score below 90 must be held. A score of 90 meets only the numerical threshold. Tee approves publication."
    return c.prepare_packet(
        {
            "brand": brand,
            "producerProvider": producer,
            "artifact": "A score of 90 meets only the numerical threshold. Tee approves publication.",
            "rubricVersion": "quality90-ai-v2",
            "brandRules": "Use direct language. Do not invent personal tests. Preserve publication approval.",
            "sources": [
                {
                    "id": "policy",
                    "reference": "approved-policy:quality90-v2",
                    "kind": "canon" if brand in ("TSWS", "ACX") else "source",
                    "text": src,
                    "sha256": hashlib.sha256(src.encode()).hexdigest(),
                }
            ],
        }
    )


def report(p, score=90):
    return {
        "packetId": p["packetId"],
        "artifactSha256": p["artifactSha256"],
        "score": score,
        "verdict": "PASS",
        "coverageComplete": True,
        "checks": {"evidence": True, "voice": True, "brandRules": True, "canon": True},
        "findings": [],
        "claims": [
            {
                "artifactQuote": "A score of 90 meets only the numerical threshold.",
                "sourceId": "policy",
                "sourceQuote": "A score of 90 meets only the numerical threshold.",
                "status": "SUPPORTED",
            }
        ],
        "summary": "The text follows the supplied source and preserves Tee approval.",
    }


class ReviewTests(unittest.TestCase):
    def test_routing_prevents_self_review(self):
        self.assertEqual(c.route_reviewer("openai"), "claude")
        self.assertEqual(c.route_reviewer("anthropic"), "gemini")
        self.assertEqual(c.route_reviewer("Claude"), "gemini")
        with self.assertRaises(ValueError):
            c.route_reviewer("unknown")

    def test_packet_hash_covers_rules_sources_and_artifact(self):
        p = packet()
        self.assertEqual(len(p["packetId"]), 64)
        self.assertNotEqual(p["packetId"], packet("NCO_FORGE")["packetId"])
        bad = copy.deepcopy(p)
        bad["artifact"] += " Changed."
        self.assertFalse(c.packet_valid(bad))

    def test_no_claimed_source_hash_or_missing_canon_can_pass(self):
        p = packet()
        p["sources"][0]["sha256"] = "a" * 64
        self.assertFalse(c.packet_valid(p))
        with self.assertRaises(ValueError):
            c.prepare_packet(
                {
                    "brand": "TSWS",
                    "producerProvider": "openai",
                    "artifact": "text",
                    "rubricVersion": "v",
                    "brandRules": "rules",
                    "sources": [],
                }
            )

    def test_all_brands_boundary(self):
        for brand in c.BRANDS:
            p = packet(brand)
            self.assertEqual(c.validate_report(p, report(p, 89))["state"], "HOLD")
            good = c.validate_report(p, report(p, 90))
            self.assertEqual(good["state"], "READY_FOR_TEE_REVIEW")
            self.assertFalse(good["publicationAuthorized"])
            self.assertEqual(good["reviewKind"], "AI_REVIEW")

    def test_wrong_scores_and_false_passes_hold(self):
        p = packet()
        for score in [True, "90", 89.9, 101, float("nan"), None]:
            self.assertEqual(c.validate_report(p, report(p, score))["state"], "HOLD")
        for change in [
            lambda r: r.update(coverageComplete=False),
            lambda r: r["findings"].append({"severity": "HIGH", "issue": "unsourced"}),
            lambda r: r["checks"].update(evidence=False),
            lambda r: r["claims"][0].update(status="UNVERIFIED"),
            lambda r: r["claims"][0].update(sourceQuote="made up evidence"),
            lambda r: r["claims"][0].update(artifactQuote="claim absent from draft"),
            lambda r: r.update(packetId="a" * 64),
            lambda r: r.update(verdict="WAIVED"),
        ]:
            r = report(p, 100)
            change(r)
            self.assertEqual(c.validate_report(p, r)["state"], "HOLD")

    def test_empty_evidence_coverage_holds(self):
        p = packet()
        r = report(p)
        r["claims"] = []
        self.assertEqual(c.validate_report(p, r)["state"], "HOLD")

    def test_signed_ai_record_never_impersonates_human_approval(self):
        p = packet()
        key = Ed25519PrivateKey.generate()
        signed = c.sign_receipt(
            p,
            report(p),
            {
                "provider": "anthropic",
                "model": "claude-sonnet-5",
                "sessionId": "test-session",
                "authMethod": "claude.ai",
                "source": "observed_cli_run",
            },
            key,
            now=NOW,
        )
        r = c.verify_receipt(signed, p, key.public_key(), now=NOW)
        self.assertEqual(r["state"], "READY_FOR_TEE_REVIEW")
        self.assertEqual(r["reviewKind"], "AI_REVIEW")
        self.assertFalse(r["publicationAuthorized"])
        signed["payload"]["score"] = 100
        self.assertEqual(c.verify_receipt(signed, p, key.public_key(), now=NOW)["state"], "HOLD")

    def test_old_receipts_new_artifacts_and_wrong_signers_hold(self):
        p = packet()
        key = Ed25519PrivateKey.generate()
        signed = c.sign_receipt(
            p,
            report(p),
            {
                "provider": "anthropic",
                "model": "claude-sonnet-5",
                "sessionId": "test-session",
                "authMethod": "claude.ai",
                "source": "observed_cli_run",
            },
            key,
            now=NOW,
        )
        self.assertEqual(
            c.verify_receipt(signed, p, Ed25519PrivateKey.generate().public_key(), now=NOW)[
                "state"
            ],
            "HOLD",
        )
        self.assertEqual(
            c.verify_receipt(signed, p, key.public_key(), now=NOW + datetime.timedelta(hours=25))[
                "state"
            ],
            "HOLD",
        )
        changed = copy.deepcopy(p)
        changed["artifact"] += " Changed."
        self.assertEqual(
            c.verify_receipt(signed, changed, key.public_key(), now=NOW)["state"], "HOLD"
        )

    def test_no_self_issued_claude_review_for_claude_production(self):
        p = packet(producer="anthropic")
        key = Ed25519PrivateKey.generate()
        with self.assertRaises(ValueError):
            c.sign_receipt(
                p,
                report(p),
                {
                    "provider": "anthropic",
                    "model": "claude-sonnet-5",
                    "sessionId": "test-session",
                    "authMethod": "claude.ai",
                    "source": "observed_cli_run",
                },
                key,
                now=NOW,
            )

    def test_subscription_budget_guard(self):
        auth = {
            "loggedIn": True,
            "authMethod": "claude.ai",
            "apiProvider": "firstParty",
            "subscriptionType": "max",
        }
        use = "You are currently using your subscription to power your Claude Code usage\nCurrent session: 0% used\nCurrent week (all models): 2% used"
        self.assertTrue(c.included_usage_ok(auth, use))
        for bad in [
            use.replace("0%", "98%"),
            use.replace("2%", "100%"),
            "unknown",
            "Now using credits",
        ]:
            self.assertFalse(c.included_usage_ok(auth, bad))
        self.assertFalse(c.included_usage_ok({**auth, "authMethod": "api_key"}, use))


if __name__ == "__main__":
    unittest.main()
