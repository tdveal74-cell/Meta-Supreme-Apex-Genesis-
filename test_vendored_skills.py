"""Vendored third-party skills are copies, not forks.

`.claude/skills/scroll-craft` is a byte for byte copy of upstream
`nateherkai/scroll-craft` at the commit `UPSTREAM.md` records. Prose in that
file says never edit it in place. Prose is not an invariant, so this module
makes it one: a local edit, a partial sync, or a deleted file fails here
instead of surviving as a silent fork nobody can reconcile with upstream.

Regenerating the manifest is part of syncing a newer upstream, and
`UPSTREAM.md` carries the one liner that does it.
"""

import hashlib
import pathlib
import re

SKILL = pathlib.Path(__file__).parent / ".claude" / "skills" / "scroll-craft"
MANIFEST = SKILL / "MANIFEST.sha256"
UPSTREAM = SKILL / "UPSTREAM.md"

# Written by us, so deliberately outside the manifest: everything else under
# the skill directory is upstream's and must hash to what upstream shipped.
OURS = {"UPSTREAM.md", "MANIFEST.sha256"}


def _recorded() -> dict[str, str]:
    entries = {}
    for line in MANIFEST.read_text().splitlines():
        if not line.strip():
            continue
        digest, rel = line.split("  ", 1)
        entries[rel] = digest
    return entries


def _on_disk() -> dict[str, str]:
    entries = {}
    for path in SKILL.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(SKILL).as_posix()
        if rel in OURS:
            continue
        entries[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return entries


def test_manifest_covers_every_vendored_file() -> None:
    recorded, disk = _recorded(), _on_disk()
    assert set(recorded) == set(disk), (
        "the vendored tree and MANIFEST.sha256 disagree about which files exist. "
        f"only on disk: {sorted(set(disk) - set(recorded))}. "
        f"only in the manifest: {sorted(set(recorded) - set(disk))}"
    )


def test_no_vendored_file_was_edited_in_place() -> None:
    recorded, disk = _recorded(), _on_disk()
    drifted = sorted(rel for rel in recorded.keys() & disk.keys() if recorded[rel] != disk[rel])
    assert not drifted, (
        f"vendored files were modified in place: {drifted}. Fixes go upstream, "
        "not into this copy. If this is a deliberate sync, follow "
        ".claude/skills/scroll-craft/UPSTREAM.md and regenerate the manifest."
    )


def test_upstream_records_a_full_commit_sha() -> None:
    text = UPSTREAM.read_text()
    assert re.search(r"`[0-9a-f]{40}`", text), (
        "UPSTREAM.md must record the full 40 character upstream commit the copy "
        "was taken from, otherwise the manifest pins content nobody can trace."
    )


def test_upstream_licence_is_carried_with_the_code() -> None:
    licence = (SKILL / "LICENSE").read_text()
    assert "MIT License" in licence
    assert "Nate Herk" in licence, "MIT redistribution keeps the original copyright line"
