# Upstream provenance

`hypit` is third-party work vendored into this repository. Nothing under this
directory is ours except this file and `MANIFEST.sha256`, and nothing else
here is edited in place. Fixes go upstream.
`test_vendored_skills.py` enforces that: every file below is hashed into
`MANIFEST.sha256`, and a local edit fails the suite rather than surviving as a
silent fork.

| | |
| --- | --- |
| Upstream | https://github.com/hypit-ai/hypit |
| Author | Hypit.AI |
| Licence | Modified Apache 2.0, see `LICENSE` in this directory |
| Package version | 0.3.1 (root `package.json` at the commit below) |
| Vendored commit | `dc2b7a8f31b1ef1443a79ca448548d69e3ceb6a0` |
| Commit date | 2026-10-14 |
| Vendored on | 2026-10-16 |
| Upstream path | `skills/hypit/` |

The copy is byte identical to that upstream path at that commit, plus this file,
`MANIFEST.sha256`, and a copy of the upstream repository `LICENSE`. Every
relative link inside the skill resolves within this folder, checked when it was
vendored, so the folder relocates unedited. Tee asked for it on 2026-10-15 by
running `npx skills add hypit-ai/hypit -g`, and ruled it vendored the same day.

## Why vendored rather than installed per machine

That command installs to `~/.agents/skills/hypit` and symlinks it into
`~/.claude/skills/`. Both live under `$HOME`, which is in the ephemeral
container, so the install is gone when the container is reclaimed. A skill
committed under `.claude/skills/` is part of the checkout and loads in every
session with no per machine step. This is the same reasoning
`.claude/skills/scroll-craft/UPSTREAM.md` records.

Do not also run `npx skills add hypit-ai/hypit -g` in a session that has this
checkout. The global copy carries the same `hypit` skill name and would load
beside this one.

## The licence, read before it was vendored

It is not MIT. It is Apache 2.0 with three added conditions. Using it for our
own work, commercial work included, is permitted without a commercial licence,
and the producer claims no rights in the output: videos, audio and images made
with it are ours. Clause 3 adds that output made through a third-party model or
service may also fall under that provider's terms. What needs a commercial licence from Hypit.AI:

- running it as a multi-tenant or hosted service for other parties, where one
  tenant is one workspace
- selling or licensing it, or anything derived from it, for gain
- removing its name, logo or copyright from the CLI, run reports or manifests
  where those reach a user

Keeping this copy in our own repository for our own production is inside the
permitted use. Building it into a product or service sold to others is not, and
that is a ruling for Tee rather than a reading of this file.

## Syncing a newer upstream

```bash
git clone --depth 1 https://github.com/hypit-ai/hypit.git /tmp/hypit
rm -rf .claude/skills/hypit
mkdir -p .claude/skills/hypit
cp -R /tmp/hypit/skills/hypit/. .claude/skills/hypit/
cp /tmp/hypit/LICENSE .claude/skills/hypit/LICENSE
```

Restore this file, update the commit, version and date rows above, re-read the
licence for changes (clause 2a lets the producer tighten it), then regenerate
the manifest the drift check reads:

```bash
python3 - <<'PY'
import hashlib, pathlib
root = pathlib.Path(".claude/skills/hypit")
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

## What the skill needs, none of it installed by this repository

The folder is instructions and examples: markdown, `.svml`, `.svs` and
`.svrun` files and one `.ts` file. Nothing in it runs on its own. Producing
anything with it means the skill will steer the agent to:

- install the `@hypit/hypit` runtime from npm, globally or as a devDependency
- connect a model provider. It names TokenDance, HiAPI, Pollo, BeatAPI and
  Monid as npm provider packages, plus `@hypit/provider-hypihub` with an OAuth
  flow against `hypit.ai`.
  Generation through any of them spends real money, and credential setup and
  spending are Tee's to approve
- prepare local programs such as WhisperX, which download models

None of that is wired into CI or any workflow here.

## Corrections to the vendored text, which is never edited to fix them

- `agents/openai.yaml` is display metadata for other agent hosts. Whether
  Claude Code reads it is unverified; nothing in it is an instruction.
- The skill's production default is to generate people, voices and
  performances. For TQO and NCO Forge the presenter is Tee's own likeness and
  cloned voice, and for The Shadow We Share the voices are Tee's and his wife's
  under recorded consent. Point it at those owned assets. Never let it cast a
  generated presenter or a stock voice for a show.
