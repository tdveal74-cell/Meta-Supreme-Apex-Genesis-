"""Run with python -m unittest discover -s docs/integrations/markup-ai -p 'test_*.py'."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("review_adapter", Path(__file__).with_name("review_adapter.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

TEXT = "Test one task."
AGENTS = ["terminology", "brand_voice"]


def sample(*, agents=None, warnings=None, issues=None, voice="TQO Quiet Precision"):
    names = AGENTS if agents is None else agents
    return {
        "checked": {"characters": len(TEXT), "agents_run": names, "voice_profile": voice},
        "warnings": [] if warnings is None else warnings,
        "results": [{"agent": name, "issues": (issues or []) if name == "brand_voice" else []} for name in names],
    }


class AdapterTests(unittest.TestCase):
    def check(self, payload):
        return module.normalize(TEXT, "TQO", AGENTS, payload, voice_profile="TQO Quiet Precision")

    def test_unrun(self):
        result = self.check(None)
        self.assertEqual(result["markup_ai_status"], "NOT_RUN")
        self.assertFalse(result["release_approved"])

    def test_clean_not_release(self):
        result = self.check(sample())
        self.assertEqual(result["markup_ai_status"], "EDITORIAL_CLEAR")
        self.assertIsNone(result["script_doctor_score"])
        self.assertFalse(result["release_approved"])

    def test_issue(self):
        result = self.check(sample(issues=[{"severity": "high", "position": {"start": 0, "end": 4}}]))
        self.assertEqual(result["markup_ai_status"], "EDITORIAL_ISSUES")

    def test_missing_agent(self):
        self.assertEqual(self.check(sample(agents=["terminology"]))["markup_ai_status"], "INCOMPLETE")

    def test_warning(self):
        self.assertEqual(self.check(sample(warnings=[{"code": "agent_failed"}]))["markup_ai_status"], "INCOMPLETE")

    def test_wrong_profile(self):
        self.assertEqual(self.check(sample(voice="Other"))["markup_ai_status"], "INCOMPLETE")

    def test_invalid_position(self):
        self.assertEqual(self.check(sample(issues=[{"position": {"start": 2, "end": 99}}]))["markup_ai_status"], "INCOMPLETE")

    def test_malformed_envelope(self):
        self.assertEqual(self.check({"checked": {}})["markup_ai_status"], "INCOMPLETE")


if __name__ == "__main__":
    unittest.main()
