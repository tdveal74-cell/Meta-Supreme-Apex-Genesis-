# Upstream provenance

`scroll-craft` is third-party work vendored into this repository. Nothing under
this directory is ours, and nothing here is edited in place. Fixes go upstream.
`test_vendored_skills.py` enforces that: every file below is hashed into
`MANIFEST.sha256`, and a local edit fails the suite rather than surviving as a
silent fork.

| | |
| --- | --- |
| Upstream | https://github.com/nateherkai/scroll-craft |
| Author | Nate Herk (https://github.com/nateherkai) |
| Licence | MIT, see `LICENSE` in this directory |
| Skill version | 0.3.0 (from `plugins/nateherk-design` `plugin.json`) |
| Vendored commit | `0b816225945e45380397d6a0487efa3c98916858` |
| Commit date | 2026-09-04 |
| Vendored on | 2026-09-06 |
| Upstream path | `plugins/nateherk-design/skills/scroll-craft/` |

The copy is byte identical to that upstream path at that commit, plus this file,
`MANIFEST.sha256`, and a copy of the upstream repository `LICENSE`. No file
inside the skill referenced its plugin path, so the folder relocates unedited.

## Why vendored rather than pinned as a plugin

Upstream also ships as a Claude Code plugin, and this repository already pins
three community plugins through `.claude-plugin/marketplace.json`. That route
was not taken, and the reason was measured rather than assumed.

A pinned plugin is installed once per machine with `claude plugin install`.
Enabling it in `.claude/settings.json` does not install it. In the Claude Code
on the web session that vendored this skill, `.claude/settings.json` listed all
three pinned plugins as enabled while `~/.claude/plugins/installed_plugins.json`
read `{"version": 2, "plugins": {}}`. None of the three were present. A plugin
carried that way is therefore absent from web sessions unless somebody installs
it inside each container by hand, and the container is reclaimed after it goes
idle.

A user level install at `~/.claude/skills/` has the same problem for the same
reason: `$HOME` lives in the ephemeral container, so a copy placed there is gone
with the container. A skill committed under `.claude/skills/` is part of the
checkout and loads in every session with no per machine step.

Do not add `nateherk-design` to `.claude-plugin/marketplace.json` while this
copy exists. The plugin carries the same `scroll-craft` skill name, and two
copies loading together is the collision `CLAUDE.md` already warns about for
`@claude-community` duplicates.

## Syncing a newer upstream

```bash
git clone --depth 1 https://github.com/nateherkai/scroll-craft.git /tmp/scroll-craft
rm -rf .claude/skills/scroll-craft
mkdir -p .claude/skills/scroll-craft
cp -R /tmp/scroll-craft/plugins/nateherk-design/skills/scroll-craft/. .claude/skills/scroll-craft/
cp /tmp/scroll-craft/LICENSE .claude/skills/scroll-craft/LICENSE
```

Restore this file, update the commit, version and date rows above, then
regenerate the manifest the drift check reads:

```bash
python3 - <<'PY'
import hashlib, pathlib
root = pathlib.Path(".claude/skills/scroll-craft")
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

Read upstream `CHANGELOG.md` before syncing. It records what broke on each build
and the rule that came out of it, rather than a feature list.

## Runtime dependencies, none of them installed by this repository

The skill authors a page unaided, but its asset and verification scripts need
tools this repository neither pins nor installs:

- Node 18 or newer, for every script in `scripts/`
- a full ffmpeg build, for encoding clips that scrub rather than play. A
  stripped build reports a missing filter as a syntax error in your own command.
  `SCROLLCRAFT_FFMPEG` overrides the search, and the ffmpeg that ships beside
  Playwright is a stripped one, so do not point it there
- `playwright-core` plus Chrome, installed in the build folder, for the
  verification pass. `SCROLLCRAFT_CHROME` overrides the search
- `KIE_AI_API_KEY`, only if you want assets generated rather than supplied.
  Generation costs real money. Building from your own photos and footage is a
  first class route and costs nothing

`node .claude/skills/scroll-craft/scripts/doctor.mjs` reports which are present.
Run it before a build, not after a confusing failure. Builds land in a workspace
resolved from `SCROLLCRAFT_HOME`, then the nearest `.scrollcraft.json`, then
`<project root>/scrollcraft`. None of those are committed here: `.gitignore`
excludes the default location, `.scrollcraft.json`, and the video extensions a
build produces, because the location is configurable and the content is not.

## Corrections to the vendored text, which is never edited to fix them

Upstream prose is preserved exactly, so the following read wrong in this
install and are corrected here instead:

- `CHANGELOG.md` says to invoke the skill as `/nateherk-design:scroll-craft`.
  That is the plugin namespace. In this install there is no plugin, and the
  skill is invoked as `scroll-craft`.
- `doctor.mjs` suggests copying `.env.example` to `.env`. That file lives at the
  upstream repository root and was not vendored, since only the skill folder
  was. Set `KIE_AI_API_KEY` in the environment, or write a `.env` by hand with
  the single line `KIE_AI_API_KEY=your-key-here`. This repository already
  gitignores `.env`.
- Upstream states the skill has only ever been run on Windows. The scripts do
  search macOS and Linux locations, but no build has been verified on either.

## Read before running `scripts/serve.mjs`

Two upstream properties of the local verification server are worth knowing.
Neither is exercised unless you run that script, and it is not wired into
anything here:

- it calls `listen(PORT)` with no host, so it binds every interface rather than
  loopback. Do not run it on an untrusted network
- its path containment is a `startsWith` prefix check on the resolved path, not
  a boundary check. Classic `../` escapes are rejected, but a sibling directory
  whose name begins with the workspace name is servable

Separately, `scripts/kie.mjs` sends the `Authorization: Bearer` header to two
hosts, `api.kie.ai` and `kieai.redpandaai.co`, the second for base64 file
upload. Both are kie.ai endpoints and the key is never logged, only the path of
the file it was read from. This is only relevant if you set the key at all.
