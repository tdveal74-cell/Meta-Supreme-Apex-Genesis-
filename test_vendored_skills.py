"""Vendored skills are copies, not forks.

Each skill named in `VENDORED` is a byte for byte copy of a folder its
`UPSTREAM.md` records. Four are third party, each at a named upstream commit:
`scroll-craft` from `nateherkai/scroll-craft`, `hypit` from `hypit-ai/hypit`,
`typesafe-ai` from `typesafe-ai/skills`, and `watch` from
`bradautomates/claude-video`. Three are Tee's ArtCraft skills, written for him
and copied off his VPS as a zip on 2026-10-31, each file checked against that
zip's own manifest: `effectcraft`, `filmcraft` and `photocraft`. Prose in those
files says never edit them in place. Prose is not an invariant, so this module
makes it one: a local edit, a partial sync, or a deleted file fails here
instead of surviving as a silent fork nobody can reconcile with the source.

Regenerating a manifest is part of syncing a newer copy, and each
`UPSTREAM.md` carries the one liner that does it.
"""

import hashlib
import pathlib
import re

import pytest

SKILLS = pathlib.Path(__file__).parent / ".claude" / "skills"

# Each vendored skill and the lines its LICENSE must still carry. The
# licences differ: scroll-craft, typesafe-ai and watch are MIT, hypit is
# Apache 2.0 with conditions. None means the copy carried no licence file:
# the three ArtCraft skills were written for Tee and came off his VPS, so
# there is no third party licence to carry and none is written for them here.
VENDORED = {
    "scroll-craft": ("MIT License", "Nate Herk"),
    "hypit": ("Apache License 2.0", "Hypit.AI"),
    "typesafe-ai": ("MIT License", "TypeSafe AI"),
    "watch": ("MIT License", "Bradley Bonanno"),
    "effectcraft": None,
    "filmcraft": None,
    "photocraft": None,
}

# Written by us, so deliberately outside the manifest: everything else under
# a skill directory is upstream's and must hash to what upstream shipped.
OURS = {"UPSTREAM.md", "MANIFEST.sha256"}


def _recorded(skill: pathlib.Path) -> dict[str, str]:
    entries = {}
    for line in (skill / "MANIFEST.sha256").read_text().splitlines():
        if not line.strip():
            continue
        digest, rel = line.split("  ", 1)
        entries[rel] = digest
    return entries


def _on_disk(skill: pathlib.Path) -> dict[str, str]:
    entries = {}
    for path in skill.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(skill).as_posix()
        if rel in OURS:
            continue
        entries[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return entries


def test_every_vendored_skill_is_checked_here() -> None:
    marked = sorted(d.name for d in SKILLS.iterdir() if (d / "UPSTREAM.md").is_file())
    assert marked == sorted(VENDORED), (
        f"skills carrying UPSTREAM.md are {marked}, this module checks "
        f"{sorted(VENDORED)}. A vendored skill this file does not name is not "
        "protected from in-place edits."
    )


@pytest.mark.parametrize("name", sorted(VENDORED))
def test_manifest_covers_every_vendored_file(name: str) -> None:
    skill = SKILLS / name
    recorded, disk = _recorded(skill), _on_disk(skill)
    assert set(recorded) == set(disk), (
        f"the vendored {name} tree and its MANIFEST.sha256 disagree about which "
        f"files exist. only on disk: {sorted(set(disk) - set(recorded))}. "
        f"only in the manifest: {sorted(set(recorded) - set(disk))}"
    )


@pytest.mark.parametrize("name", sorted(VENDORED))
def test_no_vendored_file_was_edited_in_place(name: str) -> None:
    skill = SKILLS / name
    recorded, disk = _recorded(skill), _on_disk(skill)
    drifted = sorted(rel for rel in recorded.keys() & disk.keys() if recorded[rel] != disk[rel])
    assert not drifted, (
        f"vendored {name} files were modified in place: {drifted}. Fixes go "
        "upstream, not into this copy. If this is a deliberate sync, follow "
        f".claude/skills/{name}/UPSTREAM.md and regenerate the manifest."
    )


@pytest.mark.parametrize("name", sorted(VENDORED))
def test_upstream_records_a_full_commit_sha(name: str) -> None:
    text = (SKILLS / name / "UPSTREAM.md").read_text()
    assert re.search(r"`[0-9a-f]{40}`", text), (
        f"{name}/UPSTREAM.md must record the full 40 character upstream commit "
        "the copy was taken from, otherwise the manifest pins content nobody "
        "can trace."
    )


@pytest.mark.parametrize("name", sorted(VENDORED))
def test_upstream_licence_is_carried_with_the_code(name: str) -> None:
    markers = VENDORED[name]
    if markers is None:
        # The copy came with no licence file. UPSTREAM.md has to say so in
        # those words, and a LICENSE turning up here later would be terms
        # nobody at the source wrote, so its absence is pinned as well.
        text = (SKILLS / name / "UPSTREAM.md").read_text()
        assert "no licence file" in text, (
            f"{name}/UPSTREAM.md must say the copy carried no licence file, "
            "since this module checks no LICENSE for it"
        )
        assert not (SKILLS / name / "LICENSE").exists(), (
            f"{name}/LICENSE exists but the source carried none; a licence "
            "written here is not the source's and does not belong in the copy"
        )
        return
    licence = (SKILLS / name / "LICENSE").read_text()
    for marker in markers:
        assert marker in licence, (
            f"{name}/LICENSE no longer carries {marker!r}; redistribution keeps "
            "the original licence and copyright line"
        )
