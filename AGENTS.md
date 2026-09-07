# AGENTS.md

For agents that read `AGENTS.md` rather than `CLAUDE.md`: Codex, Cursor, and
anything else pointed at this repository.

**`CLAUDE.md` is authoritative. Read it in full before you change anything.**

This file is deliberately not a copy of it. Two files carrying the same 216
lines is exactly the failure class the first law below exists to stop: one gets
updated, the other goes stale, and the stale one is still confidently read
aloud. What is inlined here is the part that is unsafe to learn one hop late.
Everything else is a pointer.

## The first law: check before you claim

Ruled by Tee 2026-09-06, after a single night produced five assertions that a
cheap check would have caught.

**Do not state anything as fact when a check is available and you have not run
it.** Not "probably", not "should be", not a number you remember. Either verify
it or label it unverified. "Unverified" is always an acceptable answer here. A
confident wrong one never is.

What follows from it:

- Read the file before saying where something lives. A path is not a memory.
- Count from the estate, not from the lane. That count has been wrong twice in
  the same direction because it was taken from a dependency list instead of
  from the workflows themselves.
- A fix is not fixed until it is re-measured. Reproduce the failure, apply the
  change, show the same measurement clean.
- Never widen a rule on speculation about intent. If a transformation could
  change a number, a name, a path or a line of dialogue, refuse instead.
- Grade your own findings before raising them. Over-calling a finding spends
  Tee's attention and is its own error.
- Green is not correct. Tests do not read the artifact. A human or an executed
  adversarial case does.

When a check genuinely cannot be run, say so with the reason and name who can
run it.

## Invariants that are never relaxed to make CI green

- `services/devon` stays effect free
- WRITE and HIGH_IMPACT tools require human approval
- Orphan effect intents refuse automatic retry; the intent commits durably
  before the adapter runs
- Receipts commit atomically with the lease fenced result
- Skill promotion is human gated; proposals dedupe by goal slug
- Materialize and spawn never auto run effects
- `deploy/soul/main.py` has no mutating routes. The one permitted non-GET is
  `POST /api/v1/soul/conflict-search`, allowlisted in `test_deploy_soul.py`
- No em or en dashes in `services/devon/*.py` or `docs/devon/*.md`, enforced by
  `test_devon_integrity.py`. Restructure the sentence, do not swap the
  punctuation. Note the sweep is a flat glob, so it does not reach
  subdirectories

## Routing: where to look for what

| If you need | Read |
|---|---|
| the operating rules, in full and authoritative | `CLAUDE.md` |
| what the system is, and the reading order | `README.md`, then `ARCHITECTURE.md`, `RUNBOOK.md`, `OPERATING.md` |
| DEVON's design and its stated boundaries | `docs/devon/DEVON.md` |
| current status on any topic | the newest dated `docs/devon/SYS_OPS_*` file on it, which supersedes the older ones |
| what Tee said in his own words, by topic | `docs/devon/CAPTURE_*` |
| whether a record is still true | `scripts/estate_reconcile.py`, and `.claude/skills/estate-reconcile/` |
| CI, PRs, and the failure catalogue with root causes | `.claude/skills/steward/` |
| what production is actually serving | `.claude/skills/deploy-readback/` |
| the Build 12 learning lane and n8n house conventions | `.claude/skills/devon-learning-lane/` |
| API service code | `app/`, `services/` |
| the web workspace | `apps/web`, `packages/ui` |
| schema and migrations | `database/`, and confirm head with `alembic heads`, never from a doc |
| the live estate's recorded facts | `services/devon/vault.py` (data only, importing it performs no effect) |

## Before you push

CI is six jobs and the environment has real traps in it. Both are documented in
`CLAUDE.md` under "Reproducing CI", including the two that silently pass a
broken run: `pytest ... | tail` reports tail's exit code, and `next lint` drops
into an interactive setup that looks like a lint failure and is not one.

Small PRs on the designated branch, draft first, full local validation before
every push. Merge only with Tee's explicit authorization.
