import unittest

import review_gateway as gateway
import test_review_gateway as fixtures


class ProducerBindingTests(unittest.TestCase):
    setUp = fixtures.GatewayTests.setUp
    tearDown = fixtures.GatewayTests.tearDown
    signed_run = fixtures.GatewayTests.signed_run

    def test_lightweight_lookup_requires_the_original_producer(self):
        self.signed_run()
        request = {k: v for k, v in self.req.items() if k != "sources"}
        self.assertEqual(
            gateway.verify_latest(request, self.root, self.brands)["state"],
            "READY_FOR_TEE_REVIEW",
        )
        for provider in ("anthropic", "Claude", "google", "human", "", None, "unknown"):
            changed = {**request, "producerProvider": provider}
            self.assertEqual(
                gateway.verify_latest(changed, self.root, self.brands)["state"],
                "HOLD",
                str(provider),
            )
        missing = {k: v for k, v in request.items() if k != "producerProvider"}
        self.assertEqual(gateway.verify_latest(missing, self.root, self.brands)["state"], "HOLD")

    def test_same_provider_alias_remains_compatible(self):
        self.signed_run()
        request = {k: v for k, v in self.req.items() if k != "sources"}
        for provider in ("openai", "ChatGPT", " CODEX "):
            self.assertEqual(
                gateway.verify_latest(
                    {**request, "producerProvider": provider}, self.root, self.brands
                )["state"],
                "READY_FOR_TEE_REVIEW",
            )


if __name__ == "__main__":
    unittest.main()
