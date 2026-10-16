"""Every inline script in the served consoles has to parse.

Found 2026-10-16 while proving the console sign-in in a real browser: the
console's main script had not run since PR #192 merged on 2026-09-10. Commit
747fcb6 left five lines of a patch note, "NOTE ON HUNK 2: ...", inside the
script as bare text, so the browser threw `SyntaxError: Unexpected identifier
'ON'` and every handler in it was dead on both hosts: remember, find, recall,
approve, the Soul Layer status check. It passed every gate the estate had for
five weeks, because the console tests read the HTML as text and none of them
ever handed the script to a JavaScript parser.

This hands each inline script to `node --check`. Node is on every GitHub
ubuntu runner and in this container; a machine without it fails here rather
than skipping, because a check that skips quietly reads as a pass.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
CONSOLES = sorted(
    [ROOT / "deploy" / "soul" / "console.html", ROOT / "deploy" / "soul" / "terminal.html"]
    + [
        p
        for p in (ROOT / "docs" / "devon" / "assets").glob("SYS_OPS_devon-console_v*.html")
        if not p.name.startswith("SUPERSEDED_")
    ]
)
SCRIPT = re.compile(r"<script(?P<attrs>[^>]*)>(?P<body>.*?)</script>", re.S)


def _inline_scripts(page: Path) -> list[str]:
    scripts = []
    for match in SCRIPT.finditer(page.read_text()):
        attrs = match.group("attrs")
        if "src=" in attrs:
            continue
        kind = re.search(r'type="([^"]+)"', attrs)
        if kind and kind.group(1) not in ("text/javascript", "module"):
            continue
        scripts.append(match.group("body"))
    return scripts


def test_the_served_consoles_are_found():
    names = {p.name for p in CONSOLES}
    assert "console.html" in names
    assert any(n.startswith("SYS_OPS_devon-console_v") for n in names)
    for page in CONSOLES:
        assert page.exists(), page


@pytest.mark.parametrize("page", CONSOLES, ids=lambda p: p.name)
def test_every_inline_script_parses(page: Path, tmp_path: Path):
    node = shutil.which("node")
    assert node, "node is not on PATH, so these scripts cannot be parsed here"
    scripts = _inline_scripts(page)
    assert scripts, f"{page.name}: no inline script found, so the glob or the pattern is wrong"
    for index, body in enumerate(scripts):
        probe = tmp_path / f"{page.stem}_{index}.js"
        probe.write_text(body)
        result = subprocess.run(
            [node, "--check", str(probe)], capture_output=True, text=True, timeout=60
        )
        assert result.returncode == 0, (
            f"{page.name} inline script {index} does not parse, so none of it runs "
            f"in a browser:\n{result.stderr.strip()}"
        )
