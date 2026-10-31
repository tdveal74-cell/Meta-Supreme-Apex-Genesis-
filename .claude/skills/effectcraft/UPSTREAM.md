# Upstream provenance

`effectcraft` is one of Tee's ArtCraft skills, vendored into this repository
from his VPS by way of a zip he sent. Nothing under this directory is ours
except this file and `MANIFEST.sha256`, and nothing else here is edited in
place. Fixes go to the source copy on the VPS and come back the way this copy
came, as a new zip checked against its own manifest. `test_vendored_skills.py`
enforces that: every file below is hashed into `MANIFEST.sha256`, and a local
edit fails the suite rather than surviving as a silent fork.

| | |
| --- | --- |
| Source | `ArtCraft_Skills_for_Claude.zip`, uploaded by Tee on 2026-10-31 |
| Zip sha256 | `39ce1650184662d1c4c4db5168e4d7e660b971a7390b369379e665445bb29f60` |
| Zip size | 239,511 bytes, 47 entries, 13 skills |
| Path in the zip | `skills/effectcraft/` |
| Copied off the VPS | 2026-10-31, per the zip's `README_CLAUDE.md` |
| Written | 2026-10-18, per the skill's own `Sources & evidence` section |
| Vendored on | 2026-10-31 |
| Author | written for Tee against his own checkout and install; the files carry no author line |
| Licence | none carried, see below |
| App it documents | EffectCraft, https://github.com/storytold/effectcraft, tag `v0.11.1`, commit `2a01226894c6bc58ae4fadcc24a10198d693acaa` |
| App licence | MIT OR Apache-2.0, read from `LICENSE-MIT`, `LICENSE-APACHE` and the README at that commit on 2026-10-31 |

The copy is byte identical to that path in the zip, plus this file and
`MANIFEST.sha256`. The 40 character commit above is the app commit the skill
was written against, which is the one its text cites throughout. The copy
itself came out of a zip and not out of a git checkout, so the bytes are
pinned by the zip's sha256 and its `MANIFEST.json`, and by `MANIFEST.sha256`
here, rather than by that commit.

## Why it is here

Tee ruled it on a card on 2026-10-31: "Vendor the three that touch this work",
each "with a manifest and UPSTREAM.md, a separate PR". The three are
`effectcraft`, `filmcraft` and `photocraft`. The zip carries thirteen skills,
"copied unchanged from Tee's VPS on 2026-10-31" per its `README_CLAUDE.md`; the
other ten (`cadcraft`, `deckcraft`, `designcraft`, `figcraft`, `gridcraft`,
`lightcraft`, `pdfcraft`, `soundcraft`, `vectorcraft`, `wordcraft`) are not
vendored and stay with Tee. The zip itself is not committed.

## What was checked before the copy

- The zip was re-measured in the session that vendored it: sha256
  `39ce1650184662d1c4c4db5168e4d7e660b971a7390b369379e665445bb29f60`,
  239,511 bytes, 47 entries.
- The zip's `MANIFEST.json` lists 45 files with a sha256 each. The three files
  of this skill were hashed and compared: 3 of 3 match, and no file on disk
  under `skills/effectcraft/` is missing from that manifest.
- After `cp -R`, `diff -r` between the extracted folder and
  `.claude/skills/effectcraft` reported no difference.
- Every file was read in full before it was copied.

## What is in it and what it runs

Three files: `SKILL.md` (28,857 bytes), `evidence.md` (6,740 bytes) and
`agents/openai.yaml` (147 bytes). The skill is Markdown plus one three line
YAML file. It carries no scripts, no hooks and no MCP configuration, so
loading it runs nothing.

`agents/openai.yaml` is display metadata (a display name and a short
description) in the shape OpenAI's Codex skill format uses. Whether Claude
Code reads it is unverified; nothing in it is an instruction. It is carried
because the copy is byte identical, as `hypit`'s is.

Following the skill means running `effectcraft-cli`, `effectcraft --control
<port>` or the app's MCP server. None of those is in this repository or in the
cloud image: `which` finds none of them, and neither `/opt/artcraft` nor
`/Applications` exists in the container (checked 2026-10-31).

The `SKILL.md` frontmatter names the skill `effectcraft`, which is this folder's
name, so it is invoked as `effectcraft`. Every path it references is inside
this folder, so it relocates unedited.

## Where the app lives, and what is unverified from here

The zip's `README_CLAUDE.md` says "ArtCraft applications are installed under
/opt/artcraft on srv1936199". That is Tee's VPS and a cloud session cannot
read it, so the install, its version and its CLI path are unverified here.

The skill itself was written on a macOS machine: its launch section uses
`open -a EffectCraft`, `/Applications/EffectCraft.app` and the bundle's
`Info.plist`, and it records that the `.app` contains no CLI. `/opt/artcraft`
is a Linux path. Which build the VPS carries, whether it matches `v0.11.1`,
and which launch line applies there, are all unverified. Read the VPS before
running any command the skill gives, and re-read `effectcraft-cli --version`
as the skill itself says to.

The skill records that the app's control channel binds `127.0.0.1` and has
no authentication (`docs/control-protocol.md:9-25` in the app repository).
Do not expose the port.

## The licence, and why none is written here

The copy carried no licence file and no author line. The skill was written
for Tee against his own checkout, so there is no third party licence to carry,
and none is written for it here: a `LICENSE` added in this folder would be
terms nobody at the source wrote. `test_vendored_skills.py` registers this
skill with `None` in place of licence markers, and for that case checks two
things, that this file says the copy carried no licence file and that no
`LICENSE` appears in the folder.

The app the skill describes is a separate matter. `storytold/effectcraft` is
dual licensed MIT OR Apache-2.0 at the documented commit, and its README says
the ArtCraft name and logos are trademarks of the ArtCraft Team under
`docs/brand/LICENSE-brand.txt`, not covered by that licence. Nothing of the
app is copied here, only a description of it.

## Dashes

The vendored text carries 10 em dashes (7 in `SKILL.md`, 3 in `evidence.md`)
and no en dashes. The house dash ban is enforced on `services/devon` and
`docs/devon` only, and a vendored file is not edited for it. This file and
`MANIFEST.sha256` carry none.

## Syncing a newer copy

Get the folder from Tee as a zip with a `MANIFEST.json`, verify every file
against that manifest, then:

```bash
rm -rf .claude/skills/effectcraft
mkdir -p .claude/skills/effectcraft
cp -R <extracted zip>/skills/effectcraft/. .claude/skills/effectcraft/
```

Restore this file, update the zip, date and app rows above, re-read the files
for new paths or commands, then regenerate the manifest the drift check reads:

```bash
python3 - <<'PY'
import hashlib, pathlib
root = pathlib.Path(".claude/skills/effectcraft")
ours = {"UPSTREAM.md", "MANIFEST.sha256"}
lines = [
    f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.relative_to(root).as_posix()}"
    for f in sorted(p for p in root.rglob("*") if p.is_file())
    if f.relative_to(root).as_posix() not in ours
]
(root / "MANIFEST.sha256").write_text("\n".join(lines) + "\n")
PY
python3 -m pytest -q test_vendored_skills.py
```
