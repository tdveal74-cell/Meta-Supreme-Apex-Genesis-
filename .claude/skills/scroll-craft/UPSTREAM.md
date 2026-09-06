# Upstream provenance

`scroll-craft` is third-party work vendored into this repository. Nothing under
this directory is ours, and nothing here should be edited in place. Fixes go
upstream; local changes are lost on the next sync.

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

The copy is byte identical to that upstream path at that commit, plus this file
and a copy of the repository `LICENSE`. No file inside the skill referenced its
plugin path, so the folder relocates without edits.

## Why vendored rather than pinned as a plugin

Upstream also ships as a Claude Code plugin, and this repository already pins
three community plugins through `.claude-plugin/marketplace.json`. That route
was not taken here. A pinned plugin has to be installed once per machine with
`claude plugin install`, which never runs in a Claude Code on the web session,
so the skill would be absent exactly where most of this estate's sessions
happen. A skill committed under `.claude/skills/` loads in every session with no
per-machine step.

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

Then restore this file and update the commit, version, and date rows above.
Read upstream `CHANGELOG.md` before syncing; it records what broke on each build
rather than a feature list.

## Runtime dependencies, none of them installed by this repository

The skill authors a page with no help, but its asset and verification scripts
need tools this repository does not pin or install:

- Node 18 or newer, for every script in `scripts/`
- a full ffmpeg build, for encoding clips that scrub rather than play
- `playwright-core` plus Chrome, installed in the build folder, for the
  verification pass
- `KIE_AI_API_KEY`, only if you want assets generated rather than supplied

`node .claude/skills/scroll-craft/scripts/doctor.mjs` reports which of these are
present. Run it before a build, not after a confusing failure. Builds land in a
workspace resolved from `SCROLLCRAFT_HOME`, the nearest `.scrollcraft.json`, or
`<project root>/scrollcraft`, and that workspace is not committed here.
