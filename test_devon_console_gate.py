"""Static contracts for the public DEVON gate and console chrome.

Cheap on purpose: no TestClient, no vendored import, no network.
Behavioural 404 probes live in deploy/soul/_selftest.py.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEPLOY = ROOT / "deploy" / "soul"
CONSOLE = (DEPLOY / "console.html").read_text()
MAIN = (DEPLOY / "main.py").read_text()
WEBSITE = (ROOT / "website" / "index.html").read_text()
GAUNTLET = (ROOT / "docs" / "GAUNTLET.md").read_text()


def _door_script() -> str:
    start = MAIN.index("document.getElementById('f').addEventListener('submit'")
    end = MAIN.index("</script>", start)
    return MAIN[start:end]


def test_gate_submit_does_not_put_the_token_in_the_url():
    script = _door_script()
    assert "location.href = '/console'" in script
    assert "?t=" not in script
    assert "encodeURIComponent(v)" in script  # cookie still encodes
    assert "sessionStorage.setItem('devon.soul.token'" in script
    assert "console.log" not in script


def test_console_strips_legacy_query_param_t_without_putting_it_back():
    assert "searchParams.get('t')" in CONSOLE
    assert "searchParams.delete('t')" in CONSOLE
    assert "history.replaceState" in CONSOLE
    assert "sessionStorage.setItem('devon.soul.token'" in CONSOLE
    assert re.search(r"location\.href\s*=\s*['\"][^'\"]*\?t=", CONSOLE) is None
    assert "/console?t=" not in CONSOLE


def test_flagship_tokens_are_navy_amber_surface_not_terracotta_primary():
    for blob in (CONSOLE, MAIN):
        assert "#0A1628" in blob
        assert "#D4A017" in blob
        assert "#F8F5F0" in blob
        root = blob[blob.index(":root") : blob.index(":root") + 600]
        assert "#C77B4A" not in root
        assert "--navy:#0A1628" in root.replace(" ", "")
        assert "--amber:#D4A017" in root.replace(" ", "")
    assert "#C77B4A" not in CONSOLE
    assert "#C77B4A" not in MAIN
    oxide = re.search(r"--oxide:([^;]+);", CONSOLE)
    assert oxide is not None
    assert "#C77B4A" not in oxide.group(1)


def test_console_html_has_no_backdrop_filter_blur():
    compact = re.sub(r"\s+", "", CONSOLE.lower())
    assert "backdrop-filter:blur" not in compact
    assert "backdrop-filter" not in CONSOLE.lower()


def test_website_has_no_backdrop_filter_blur():
    compact = re.sub(r"\s+", "", WEBSITE.lower())
    assert "backdrop-filter:blur" not in compact


def test_gate_is_top_aligned_with_full_width_44px_targets():
    assert "place-items:center" not in MAIN
    assert "align-items:flex-start" in MAIN
    assert "min-height:44px" in MAIN
    assert "OPEN THE CONSOLE" in MAIN
    assert "Reads only. Nothing here writes to either soul." in MAIN
    assert "no-referrer" in MAIN
    assert "referrer" in MAIN


def test_gate_does_not_wear_a_live_badge():
    door = MAIN[MAIN.index("DOOR_HTML") : MAIN.index("</script>\"\"\"", MAIN.index("DOOR_HTML"))]
    assert "Live" not in door
    assert "LIVE" not in door


def test_gauntlet_ledger_floor_is_56_not_72():
    assert "**56**" in GAUNTLET
    assert "Ledger floor" in GAUNTLET
    assert "~72" not in GAUNTLET
    assert "**~72**" not in GAUNTLET
    assert "CI-live, not operator-live" in GAUNTLET
    assert "executed: false" in GAUNTLET
    assert "2026-08-22 ID snapshot" in GAUNTLET
    assert "Flagship UI" in GAUNTLET and "38" in GAUNTLET
    assert "Honesty" in GAUNTLET and "64" in GAUNTLET
    assert "Human gates" in GAUNTLET and "86" in GAUNTLET
