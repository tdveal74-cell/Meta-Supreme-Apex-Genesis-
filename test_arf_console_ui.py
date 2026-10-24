"""Execute the shipped diagnostic client with hostile inputs and a fake transport.

These tests prove browser client behavior, not production authorization or rate
limits. Real signed-in production readback remains a separate release check.
"""
import shutil
import subprocess
from pathlib import Path


def test_arf_console_behavior():
    node = shutil.which("node")
    assert node, "Node is required to execute the ARF console behavior checks"
    root = Path(__file__).resolve().parent
    result = subprocess.run(
        [node, "--test", str(root / "tests/js/arf-console.test.cjs")],
        cwd=root, capture_output=True, text=True, timeout=60, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
