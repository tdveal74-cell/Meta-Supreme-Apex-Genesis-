"""
Deployment integrity for the soul service.

`deploy/soul/` vendors a copy of the modules it serves, because the host
builds only that directory and cannot reach up into the repository. A copy
is a drift risk: someone edits the real module, the deployed one quietly
keeps answering from last month's rules, and nothing says so.

These tests make that drift loud. Every vendored file must be byte-identical
to the module it came from, and the service must stay read-only.
"""

import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent
DEPLOY = ROOT / "deploy" / "soul"

#: Vendored path -> the module it must match, exactly.
VENDORED = {
    "services/__init__.py": "services/__init__.py",
    "services/intelligence/soul.py": "services/intelligence/soul.py",
    "services/intelligence/providers/base.py": "services/intelligence/providers/base.py",
}
VENDORED.update(
    {
        f"services/devon/{p.name}": f"services/devon/{p.name}"
        for p in (ROOT / "services" / "devon").glob("*.py")
    }
)


@pytest.mark.parametrize("vendored,original", sorted(VENDORED.items()))
def test_vendored_module_matches_the_original(vendored, original):
    """A deployed module that has drifted from the real one is a lie."""
    shipped = DEPLOY / vendored
    source = ROOT / original
    assert shipped.exists(), (
        f"{vendored} is missing from deploy/soul. Re-vendor it, or the "
        f"deployed service imports something that is no longer there."
    )
    assert shipped.read_bytes() == source.read_bytes(), (
        f"{vendored} has drifted from {original}. The deployed soul service "
        f"would answer from stale rules. Copy the original over it."
    )


def test_the_console_shipped_with_the_service_is_the_current_one():
    consoles = sorted(
        p
        for p in (ROOT / "docs" / "devon" / "assets").glob("SYS_OPS_devon-console_v*.html")
        if not p.name.startswith("SUPERSEDED_")
    )
    assert len(consoles) == 1, f"expected one current console, found {consoles}"
    assert (DEPLOY / "console.html").read_bytes() == consoles[0].read_bytes(), (
        "deploy/soul/console.html is not the current console. Re-copy it."
    )


def test_the_deployed_service_has_no_write_surface():
    """Reads flow; this lane performs no effects, and that is structural."""
    source = (DEPLOY / "api" / "index.py").read_text()
    for verb in ("@app.post", "@app.put", "@app.patch", "@app.delete"):
        assert verb not in source, (
            f"{verb} appeared in the soul service. The phone lane is reads "
            f"only: a devon-soul write is an effect and belongs behind the "
            f"approval queue, not behind a shared token."
        )


def test_the_service_never_hardcodes_a_secret():
    source = (DEPLOY / "api" / "index.py").read_text()
    assert "pcsk_" not in source and "dst_" not in source, (
        "A literal key or token is in the deployed source. Secrets come from "
        "the host environment and nowhere else."
    )
