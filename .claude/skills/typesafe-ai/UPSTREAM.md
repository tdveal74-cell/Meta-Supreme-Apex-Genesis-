# Upstream provenance

`typesafe-ai` is third-party work vendored into this repository. Nothing under
this directory is ours except this file and `MANIFEST.sha256`, and nothing else
here is edited in place. Fixes go upstream. `test_vendored_skills.py` enforces
that: every file below is hashed into `MANIFEST.sha256`, and a local edit fails
the suite rather than surviving as a silent fork.

| | |
| --- | --- |
| Upstream | https://github.com/typesafe-ai/skills |
| Author | TypeSafe AI |
| Licence | MIT, see `LICENSE` in this directory |
| Plugin version | 0.5.7 (`.claude-plugin/plugin.json` at the commit below) |
| Vendored commit | `65a39f393687675ce170e6094757de20370365b9` |
| Commit date | 2026-09-12 |
| Vendored on | 2026-10-16 |
| Upstream path | `skills/typesafe-ai/` |

The copy is byte identical to that upstream path at that commit, plus this file
and `MANIFEST.sha256`. The skill's own `LICENSE` is byte identical to the
upstream repository's root `LICENSE`. The skill is one Markdown file of
guidance and runs nothing: no hooks, no scripts, no MCP server. It was read in
full before it was installed.

Tee asked for it on 2026-10-16: install it with `claude plugin marketplace add
typesafe-ai/skills` and `claude plugin install typesafe@typesafe-ai`, then use
it when working on this project. The install landed under `/root/.claude`,
which is in the ephemeral container, so this copy is what makes it load in
every session. The installed file and this one hashed the same, `71ea90d7`.

## Do not also install the plugin

The plugin carries the same skill as `typesafe:typesafe-ai` and would load
beside this one. A session that already has this checkout needs neither the
marketplace nor the plugin.

## What the skill points at, and what it can reach from here

Its first rule is to read the live documentation at `docs.typesafe.ai` before
building. That documentation is remote and changes without a commit here, so
`MANIFEST.sha256` covers this copy of the skill and nothing it points at.

Two reads on 2026-10-16, both from the cloud environment:

- Early in the day the network policy refused `docs.typesafe.ai` with 403 and
  only `api.typesafe.ai` was allowed. What stood in for the docs then: the live
  spec at `https://api.typesafe.ai/openapi.json`, and the official SDKs,
  `typesafe-sdk` on PyPI and `@typesafe-ai/sdk` on npm.
- Later the same day, after Tee updated the environment, `docs.typesafe.ai`
  answered 200 (its root redirects to `/introduction`), and so did the spec,
  PyPI and npm. `typesafe.ai` itself, where the blog lives, was still refused.
  Read then: `openapi.json` reports `info.version` 0.2.0, PyPI's latest
  `typesafe-sdk` is 0.7.5 with author TypeSafe AI, npm's latest
  `@typesafe-ai/sdk` is 0.7.0, and upstream `HEAD` of `typesafe-ai/skills` is
  still `65a39f3`, the commit vendored here.

Those are dated reads of outside state. Re-read them before relying on them.

Calling the API needs `TYPESAFE_API_KEY`, which is an environment secret and
Tee's to set. A new session picks it up; a running one does not.

## Syncing a newer upstream

```bash
git clone --depth 1 https://github.com/typesafe-ai/skills.git /tmp/typesafe-skills
rm -rf .claude/skills/typesafe-ai
mkdir -p .claude/skills/typesafe-ai
cp -R /tmp/typesafe-skills/skills/typesafe-ai/. .claude/skills/typesafe-ai/
```

Restore this file, update the commit, version and date rows above, re-read the
licence for changes, then regenerate the manifest the drift check reads:

```bash
python3 - <<'PY'
import hashlib, pathlib
root = pathlib.Path(".claude/skills/typesafe-ai")
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
