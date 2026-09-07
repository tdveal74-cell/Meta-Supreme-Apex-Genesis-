# Reconciler score and the grill lane (v1, 2026-09-07)

Status doc for the 2026-09-07 arc that began as a request to analyse one
GitHub repository and ended with one merged pull request, three adoptions,
a corrected record, and one estate defect found by accident. Supersedes
nothing.

Tee authorized the work and the merge in three steps, each quoted as given:
"Ok do it", then "merge it", then "close the arc".

## How the arc started

Tee asked for an analysis of "the utopia repo". No repository of that name
exists in his account, which was checked against `list_repos` before
answering rather than assumed, so the ambiguity went back to him and he
picked `deeplethe/utopia`. Two YouTube videos followed, both scouting
roundups. The arc is what survived the filter.

## Scoreboard

| Item | State | Receipt |
|---|---|---|
| `deeplethe/utopia` analysed against the estate | DONE, verdict DO NOT ADOPT | This doc, "What was rejected" |
| `estate_reconcile` reports a score and keeps a history | DONE | PR #156, merged `c034c31`; `test_estate_reconcile.py`, 59 passed from a 48 baseline |
| `AGENTS.md` exists for agents that do not read `CLAUDE.md` | DONE | PR #156; written as a pointer, not a copy |
| `devon-grill` skill files what only Tee knows | DONE | PR #156; `.claude/skills/devon-grill/SKILL.md` |
| `CLAUDE.md` skill count corrected from five to six | DONE | PR #156; counted from the directory, not the sentence |
| First reconciler score from an environment holding real keys | NOT DONE | Only Tee can run it. See "What this arc did not do" |
| Vercel account block cleared | NOT DONE, NOT OURS | See "The defect this arc found by accident" |

CI on the merged head `2f3e128`: five checks green, being standalone,
container contract, engine, api suite and dependency audit. `web-ci`
correctly did not run, because no changed path matches its filter.

## What was adopted, and the reasoning that survives

**The reconciler now has a second axis.** It already failed on drift, which
is the gate and remains the gate. What it could not do was show a trend.
Between 2026-08-23 and 2026-09-01 five records went stale and every run that
could have caught one looked purely local, because there was nothing to
compare a run against. `check --history FILE` appends one JSON line per run
and names the move since the previous row.

Three judgement calls are pinned in docstrings and held by tests, because
each has a friendlier reading that would quietly make the number useless:

- `UNVERIFIED` counts against the score. A source with no key is not a
  passing source. Excluded, losing every key would read as a perfect estate.
- `RETIRED` stays out of the denominator. A tripwire on a sentence that no
  longer exists has nothing live to be true about.
- Nothing checkable scores 0, not 100. The friendlier reading would let the
  score climb by deleting claims.

The row is appended after the report prints, so a failing run still records
the score it failed at. The trend is most useful on the bad runs.

**`AGENTS.md` is a pointer, not a second copy.** The common advice is to
carry identical content in both files. Two files holding the same content is
precisely the drift class the first law exists to stop, so this one
inlines only what is unsafe to learn one hop late, being the first law and
the invariants, adds a routing table, and names `CLAUDE.md` authoritative.

**`devon-grill` closes a structural hole.** DEVON records what already
happened. Threads get receipts, jobs get ledger rows, the estate gets
reconciled. Nothing in it ever asks Tee a question. Set against his stated
preference for giving minimal direction, the estate was guaranteed to stay
starved of the context that makes the rest of it worth having. The skill
interviews him one question at a time, writes as it goes so a dropped
session loses nothing, files to `docs/devon/CAPTURE_*`, marks inference as
inference, and names contradictions rather than resolving them, because
resolving is `devon-precedence`'s job and it is a ruling, not a merge.

## What was rejected, and why

Recorded so it is not re-litigated by the next session that watches the same
videos.

- **`deeplethe/utopia` as infrastructure.** The engineering is strong and the
  bitemporal design is right where most retrieval systems are wrong. Its
  history opens on 2026-08-27 with one squashed commit, one author holds 329
  of the 339 reachable through a shallow clone while GitHub reported 354 in
  total, it is v0.1, migrations roll forward only, 167 of its 174 Rust files
  carry Chinese comments, and the quick start pulls `0.1.0-rc5` because
  `0.1.0` was withdrawn. Its search and chat half also duplicates `services/knowledge`,
  which already does chunking, retrieval and RRF fusion in 1,118 lines. The
  bitemporal split and its human gated `remember` tool were worth taking as
  design. The dependency was not.
- **Heretic**, which strips refusal behaviour out of a model. Compliance is
  the one area with no exception path.
- **Moving the operating system to Codex.** It would cost the entire Claude
  Code estate and buy nothing. The files and folders are already owned.
- **A 3D knowledge graph render.** A prettier picture of stale facts is still
  stale facts.
- **A resource pack audit skill** that scores your own files against a
  rubric. `estate_reconcile` makes the live estate the authority and exits
  nonzero on disagreement. Only its scoring mechanic was worth taking.

## The defect this arc found by accident

CI on PR #156 reported a red combined status while all five checks were
green. The cause was two legacy commit statuses:

```
Vercel - meta-supreme-apex-genesis-web   failure   "Account is blocked."
Vercel - devon-soul                      failure   "Account is blocked."
```

**Both production surfaces, not one.** While that block stands, nothing that
lands on `main` can deploy, whatever CI says. It is an account level
condition on Vercel's side, and no change in this repository clears it.

It is also not the ordinary skip the `steward` skill documents. That one
records as `CANCELED` with an "Ignored" bot comment and is the per project
`ignoreCommand` working. This is different and should not be read as that.

What was not established: when the block began, or why. Neither is readable
from here. Tee has the Vercel dashboard and it is a ten second answer there.

## Four lessons worth keeping

**A baseline beats a theory.** Nineteen tests failed after the score was
added. The temptation was to explain them. Stashing the change and running
the suite on clean HEAD took one command and showed 48 passing, which
converted a theory into a fact: the regression was mine. The cause was a new
`_finding` helper appended to `test_estate_reconcile.py`, where a helper of
that exact name already existed and was silently shadowed by the later
definition. Every new name in a shared file now gets checked against what is
already in it.

**"Verified" is a claim about the reader, not the file.** The first pass at
the Utopia analysis said the MCP surface exposed seven tools and called them
verified. `crates/utopia-server/src/api/mcp.rs:43` declares
`const EXPOSED: [&str; 8]`, and the array states its own length on the line
above the list that was transcribed. Two tools were dropped. A fresh critic
caught it. The file was open the whole time.

**A shallow clone reports a different repository than the one you named.**
Every history figure in the first analysis came from a bounded `FETCH_HEAD`
fetch at an older tip while the prose credited the depth 1 `HEAD` it had
actually cloned. The numbers were internally consistent and attributed to
the wrong object. This is the same class as reading the file before saying
where something lives.

**A number written into prose is a claim with a shelf life.** `AGENTS.md` was
written in this arc to stop two files drifting apart, and it opened by saying
`CLAUDE.md` was 216 lines. The same pull request corrected the skill count in
`CLAUDE.md` and made it 217. The anti drift file drifted inside its own commit,
against the very file it points at. The fix was not to update the number. It
was to delete the number, because the next edit would have staled it again.
Assert a count only where something re-derives it, which for this estate means
`estate_reconcile`, not a sentence.

## What this arc did not do

- **The reconciler's first real score is still untaken.** The 6 out of 100
  recorded on 2026-09-07 came from a keyless container: 4 verified, 65
  unverified, 14 retired, 0 drift. It is honest and it is not a baseline.
  Run `python3 scripts/estate_reconcile.py check --history
  docs/devon/reconcile-history.jsonl` from an environment holding the real
  keys. That first row is what every later run gets measured against, so it
  is worth taking deliberately.
- **`devon-grill` has never been run.** It is committed and it loads. No
  capture exists yet, so `docs/devon/CAPTURE_*` is an empty convention until
  the first session.
- **The Vercel block is untouched.** Named above, owned by Tee.

## One thing the arc corrected about the gates

CodeRabbit does not review this repository. Its comment first read "Review
skipped: draft pull request", which looks like a draft only condition, and
was then edited to "This repository does not receive automatic reviews
because it has fewer than 10 stars." It would not have reviewed PR #156
after it left draft either. The `steward` skill already treats it as
cosmetic for merging, which stands, but it is not a second pair of eyes and
should not be counted as one. The real gates are the five CI jobs and a
direct read.
