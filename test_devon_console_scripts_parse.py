"""Every inline script in the served consoles has to parse, alone and together.

Found 2026-10-16 while proving the console sign-in in a real browser: the
console's main script had not run since PR #192 merged on 2026-09-10. Commit
747fcb6 left five lines of a patch note, "NOTE ON HUNK 2: ...", inside the
script as bare text, so the browser threw `SyntaxError: Unexpected identifier
'ON'` and every handler in it was dead: remember, find, recall, approve, the
Soul Layer status check. It passed every gate the estate had for five weeks,
because the console tests read the HTML as text and none of them ever handed
the script to a JavaScript parser.

This hands each inline script to `node --check`, and then the page's inline
scripts joined in document order, because classic scripts share one global
lexical scope in the browser: a `const` declared in both is a SyntaxError
that kills the later script while each one parses alone. A critic proved that
gap on the first version of this file.

What it cannot see is a runtime throw at load, a missing element or a null
dereference. apps/web/scripts/console-smoke.mjs loads the console in Chromium
in panel-smoke-ci.yml and fails on any page error; this file is the cheap
guard that runs in the api job on every push.

Node is on every GitHub ubuntu runner and in this container; a machine without
it fails here rather than skipping, because a check that skips quietly reads
as a pass.
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
# A browser executes any script whose type it recognises as JavaScript, so the
# filter names what it skips, the data and template types, rather than
# allowlisting two JavaScript spellings.
NOT_JAVASCRIPT = {
    "application/json",
    "application/ld+json",
    "importmap",
    "speculationrules",
    "text/template",
    "text/html",
    "text/plain",
}


def _inline_scripts(page: Path) -> list[str]:
    scripts = []
    for match in SCRIPT.finditer(page.read_text()):
        attrs = match.group("attrs")
        if re.search(r"\bsrc\s*=", attrs):
            continue
        kind = re.search(r"""type\s*=\s*["']?([^"'\s>]+)""", attrs)
        if kind and kind.group(1).lower() in NOT_JAVASCRIPT:
            continue
        scripts.append(match.group("body"))
    return scripts


def _node() -> str:
    node = shutil.which("node")
    assert node, "node is not on PATH, so these scripts cannot be parsed here"
    return node


def _check(node: str, probe: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [node, "--check", str(probe)], capture_output=True, text=True, timeout=60
    )


def test_the_served_consoles_are_found():
    names = {p.name for p in CONSOLES}
    assert "console.html" in names
    assert "terminal.html" in names
    assert any(n.startswith("SYS_OPS_devon-console_v") for n in names)
    for page in CONSOLES:
        assert page.exists(), page


@pytest.mark.parametrize("page", CONSOLES, ids=lambda p: p.name)
def test_every_inline_script_parses(page: Path, tmp_path: Path):
    node = _node()
    scripts = _inline_scripts(page)
    assert scripts, f"{page.name}: no inline script found, so the glob or the pattern is wrong"
    for index, body in enumerate(scripts):
        probe = tmp_path / f"{page.stem}_{index}.js"
        probe.write_text(body)
        result = _check(node, probe)
        assert result.returncode == 0, (
            f"{page.name} inline script {index} does not parse, so none of it runs "
            f"in a browser:\n{result.stderr.strip()}"
        )


@pytest.mark.parametrize("page", CONSOLES, ids=lambda p: p.name)
def test_the_inline_scripts_parse_together_as_the_page_runs_them(page: Path, tmp_path: Path):
    node = _node()
    probe = tmp_path / f"{page.stem}_joined.js"
    probe.write_text("\n;\n".join(_inline_scripts(page)))
    result = _check(node, probe)
    assert result.returncode == 0, (
        f"{page.name}: its inline scripts parse alone but not together, which is how "
        f"a browser runs them, so a later one dies at load:\n{result.stderr.strip()}"
    )


def test_a_redeclared_name_across_scripts_is_caught(tmp_path: Path):
    """The joined check is the one that sees this; prove it still does."""
    node = _node()
    probe = tmp_path / "redeclared.js"
    probe.write_text("const STATE = 1;\n;\nconst STATE = 2;\n")
    assert _check(node, probe).returncode != 0
