# Outward gate and TQO compliance: arc close

Session https://claude.ai/code/session_01AJJT3idgkDNWfEJjzCrX8Q, 2026-10-16 to
2026-10-23. Every state fact below was read on the date it carries. The n8n
facts are from 2026-10-17, because the n8n connector needed re-authorization
for the rest of the arc.

## What shipped

| PR | What | Merge |
|---|---|---|
| #359 | Scan, edit and verify agent types, the verifier rule, the fix loop stop | `fec7530` |
| #364 | The TypeSafe skill, vendored byte for byte with a manifest test | `9ff47d9` |
| #363 | Three Jev image lanes for TQO FINAL V5, shadow only, not wired into n8n | `3258308` |
| #367 | TQO compliance: the C4 disclosure line and the title laws enforced, the Doctor Gate able to clear | `c17711d` |
| #366 | Outward gate: the NAME=value scrub bounded so a padded command cannot outrun the hook | `e949bc7` |
| #369 | Outward gate: reserved words walked in linear time | `94f5a95` |
| #370 | Outward gate: bundled short flags checked in linear time | `bfc81f6` |
| #404 | `next` 15.5.28, clearing a critical and a high Next.js advisory | `d5c0fef` |
| #401 | Outward gate: git push options read the way git reads them | `05e59f4` |
| #403 | Outward gate: quotes kept when a statement past 20,000 characters is split | `0a7fc22` |
| #405 | Outward gate: a lease open only through a named remote | `e48fd6b` |

Other sessions merged #402, #406, #407 and #408 to main in the same window.
They are not part of this arc.

CI on main passed all five jobs on `e48fd6b`, the #405 merge, in run 1401,
read at 2026-10-23T13:33Z.

Each of #366, #367, #369, #370, #401, #403 and #405 went through at least one
independent verifier. #369 was confirmed as written; the others changed after
a verifier refuted something.
#367 round 0 passed hand-made rows and failed on the real shapes the lane
produces. #366 round 0 left a secret visible when 17 or more spaces sat
between its key and its value. #370 needed three rounds because mutants kept surviving its tests: first
two, then fifteen (thirteen letter widenings and two dropped clauses),
then none. The hook code of #370 never
changed after round 0; only the tests did. #401 took three rounds. Round 0 was
refuted on three counts: a `--force-with-lease<junk>` spelling main gated and
it did not, six mutants that survived the tests, and long options running
twice as slow as main. Round 1 fixed all three in the hook. Its verifier found
four mutations every test allowed, and round 2 added the tests that kill them.
The round 2 verifier then confirmed it against 80,000 real git pushes and
about 1.8 million commands compared with main, and found one gap main shares,
which became #405. #403 took five rounds and #405 four; each is told in
the section below.

## What the gate let through, and what closed it

The outward gate decides whether a tool call needs a recent human signal.
Three separate slowdowns could make it run past its 15 second timeout before
printing a deny: one in the scrub (25.41 s on a padded 2.5 KB command), one
in `_unwrap` (12 s on 300 KB of shell keywords), one in the three flag
regexes (21 to 23 s on one 80 KB flag token). #366, #369 and #370 close all
three. Whether Claude Code lets a call proceed when a PreToolUse hook times
out is still unmeasured, which is why the slowdowns were treated as holes.

The third verifier on #370 found a gap that had nothing to do with speed.
`git push -4f origin main` classified as an ungated plain push. Run against
a throwaway bare repository, git 2.43 printed `(forced update)`. The check
matched exact spellings; git reads a short bundle one letter at a time and
accepts any unambiguous prefix of a long option. The same root let `-ud`,
`-4d`, `--del`, `--dele`, `--mir` and `--pru` through, all measured against
real git, and let `--repo=<URL>` hide a URL remote from the URL check.

Tee ruled it fixed in its own PR. #401 reads push options the way git does
and over-gates every uncertain case. Against main's hook over 478,915
generated push commands it ungates none. One of its tests runs real git for
eleven flag shapes and requires the gate closed exactly when git forced,
deleted or mirrored.

A verifier on #401 found a fourth hole, in a different function.
For a statement over 20,000 characters, `_argv` used `statement.split()`,
because `shlex` is quadratic on one huge token. A plain split ignores
quotes. So `bash -c 'git push -f origin main; : <pad>'` was gated at 19,900
characters and came back `(None, False)` at 20,100. A `gh workflow run` and a
mutating `curl` inside the same wrapper did the same. Tee ruled it fixed in
its own PR too.

#403 needed five rounds, and each verifier found the next shape. Round 0
kept quotes but ran an unclosed quote to the end of the text and swallowed a
push. Round 1 made the splitter raise where `shlex` raises, and the next
verifier found that bash reads `\'` inside `$'..'` as a quote character where
`shlex` reads a closing quote; main's plain split had caught a push hidden
behind that by accident, so 258 commands bash would run were newly ungated.
Round 2 kept main's reading of a long statement beside the quote aware one,
and the next verifier found a shortcut that skipped it, and four nested
evals at 5 MB taking 21.6 s against the hook's 15 s timeout. Tee ruled on a
card on 2026-10-23: gate oversize commands. Round 3 reads every long
statement both ways at every level, so it cannot gate less than main by
construction, and gates any Bash command over 1,000,000 characters unread.
Round 4 added two tests a mutant run asked for.

What merged, and what the round 3 verifier measured: the splitter reads every
statement and matches `shlex` on every string up to length 7 over an
8-character alphabet plus 1.5M random ones, raises included; 0 newly
ungated against main over about 88,000 long commands; 0 mismatches over
660,000 short ones; the slowest shape under the limit took 6.1 s through the
real hook script, and a 5 MB command is decided in under 0.1 s where main
took 10 s. The splitter also made the hook faster: 5 MB of `a;` dropped from
11.8 s to 6.6 s.

#405 came from the round 2 verifier on #401: a `--force-with-lease` to the
session's own `claude/` branch, open by design, could still reach a URL.
Git takes the next word as the value of `-o` at the end of a bundle and of
five long options written without `=`, so `-uo v e.example:claude/x` read `v`
as the remote; an scp-style `host:path` with no `@` read as a named remote.
Tee ruled it fixed in its own PR. Its verifiers ran 121,565 real pushes, all
80,999 that force-moved a URL remote through a lease now gated where main
left 11,158 open, and found `--recurse-submodules` missing from the value
options. Codex then found a path remote, `/tmp/r.git`, still open, the same
on main. The last round opens a lease only when the remote is one the
repository has configured by name, and bounds the hook's git lookups at 16
per command, failing closed past that, because a command naming thousands of
directories with `-C` could otherwise outrun the timeout on main as well.

An independent check on the final head, `462075e`, refuted none of its five
claims. Path remotes, and a bare lease whose default remote is a path or URL,
are gated, and real git did push to those paths. Nine everyday leases stay
open from the clone root, from a subdirectory and through `-C`. Against main
over 30,000 generated push commands, 0 were newly ungated, and a deliberately
broken copy of the hook showed up as violations. 1,000 `-C` directories gate
in 0.169 s. 846 gate and ledger receipt tests pass. The same round also closes a word that only a git
`insteadOf` alias turns into a URL, because that word is not a configured
remote name; #405's description listed it as left alone until this was
checked after the merge. The check found one more gap main shares, listed
under Open.

## A critical Next.js advisory, cleared in production

On 2026-10-22 the dependency audit went red on every push, with no
dependency change. It first showed on #401 at 19:48Z; main's last green run
was 12:41Z. Two advisories against `next` 15.5.27 had been published:
GHSA-2464-fhr4-w9xw, critical, unauthenticated remote code execution, and
GHSA-p3m5-59mp-jv5r, high, a denial of service in App Router server actions.
#404 moved the web app to 15.5.28. Vercel deployment
`dpl_A3yT72zc7kFq5kpfe8qQz7jv4Xhj` of `meta-supreme-apex-genesis-web` reads
READY with target production on `d5c0fef`, the #404 merge. That is the
deployment record. The version string the live site serves was not read.

## TQO FINAL V5

The #367 node bodies were written into n8n draft
`761302a2-9c51-4100-81c0-7103cf8a4cf9` on Tee's card on 2026-10-17. Live was
still `9320520f-2e59-4558-853b-2761e5023d67`. Publishing is Tee's. Whether he
has published since is unverified here; the check is the read back, where
`activeVersionId` equals `versionId` and `activeVersion.sameAsDraft` is true.

The OS 28 node in the draft differs from the merged file in one line. Its
`DASH` regex was sent with `\u2014\u2013` escapes and arrived holding the two
literal characters, because the n8n tool decoded them. It matches the same
two characters and every compliance test passes against the draft's code.
The same decoding happened twice more in this arc, both in the session's own
file tools: once in the handover file and once in the first draft of this doc. Write text
that carries those escapes from a script, not through a tool argument.

## Lessons worth keeping

A verifier that runs `git checkout -B verify <sha>` moves a branch every
older worktree on `verify` still sits on, so those worktrees then show the
older commit's files as staged changes. It looked like an agent had left
mutations behind twice. Both times the index tree matched a real commit
exactly and nothing was lost. Give each verifier its own branch name, as #401's
does with `verify401`.

A mutant run is only evidence if its control passes under the same harness.
The first #370 mutant run reported nine kills, and all nine came from one test
that fails outside a git checkout. Deselecting it and running a control turned
that into a real result.

A speed fix that changes how text is parsed needs the test the parser had.
The `split()` fallback made long statements fast and quietly changed what
counts as a word. #403's splitter is pinned to `shlex` by a test, not by
reading the code.

Two verifiers in this arc found a hole outside the diff they were checking.
The third verifier on #370 found the push gap, and a verifier on #401
found the long statement gap.

The audit can go red with no change in the repository, because advisories
are published against versions already pinned. Read the advisory before
reading the diff.

Fixing one shape at a time did not converge on #403; a guarantee by
construction did. Three verifiers in a row found a new way the long path
read differently from main. Reading every long statement main's way as well
as the new way ended that class in one round, and a size limit ended the
timing class for every shape.

A bot reviewer is worth reading after the verifiers. Codex found the path
remote on #405 after two verifier rounds had passed the option rules. The
fix checks the remote against the repository's configured names, not its
punctuation.

The container restarted several times during this arc. The scratchpad and
the pushed branches survived every time; background verifiers did not
always, and one had to be started again. Write results to files as they come.

The handover to ChatGPT was first started as a multi-agent workflow and Tee
stopped it. It was written directly.

## Open

- Tee: publish the TQO FINAL V5 draft, then a session reads it back.
- Tee: rule on the four gaps #367 left alone. Preflight still accepts "Not
  required"; the tension word pattern has no word boundaries; a doctor verdict
  "PASS WITH NOTES" clears; QC at 80 to 84 ships in Parse QC while the Doctor
  Gate wants 85.
- Tee: fund TypeSafe before any Jev lane is wired.
- The Jev router hook, PR #368, held for an allowlist rebuild. The spec is in
  the ChatGPT handover.
- Tee: rule on gaps the verifiers found that are the same on main and were
  left alone. Bash's `$'..'` quoting hides a gated command at any length (a
  short `echo $'it\'s' && git push -f origin main` is ungated); `$( )` nested
  five deep is past the depth limit; a quoted `'>'` value is read as a
  redirect and drops the next word; a quote inside a heredoc line fools the
  heredoc stripper; shell indirection such as `$R` or `$(echo URL)`;
  `git -C push push`; the hook reads git config only from the first `-C`
  directory or the session cwd, so `git -C A -C B push --force-with-lease` and
  `cd B && git push --force-with-lease` stay open when B's
  `remote.pushDefault` is a path or URL. Git itself pushes there only when it
  can pick a branch to push, through `push.default=current`, an upstream or
  `push.autoSetupRemote`; with git's default it refused with "no upstream
  branch". `git stash push -m"...f..."` over-gates.
- Tee: remove the Agent Archive plugin from the claude.ai account. It syncs
  into every cloud session and asks to create an account at session start.
  This repository already turns it off (#402, 2026-10-22), measured
  2026-10-23 with `claude plugin list` and a headless session with and
  without the setting; other repositories still load it.
- A fresh session reads back what #359 set: the model, the ultracode reminder,
  a scanner's tool limits, an editor's worktree base.
- The Pulse watchdog went red at runs 140, 141, 142 and 146, from 2026-10-20
  to 2026-10-22, with the heartbeat healthy each time. Runs 140 and 141 both
  report execution 3671, node `Send Email Alert`, timed out. Run 146 reports
  execution 4024, node `Alert Tee`, timed out. Run 142 reports a node it could
  not classify (execution 3855, `RECEIPT_OR_MARKER_WRITE_FAILED`). Run 121 on 2026-10-16 was the VPS API
  timing out from the runner, and run 122 passed. None of those executions
  were opened from this session.

## DEVON RECEIPT

AREA: Systems, TQO
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_outward-gate-and-tqo-compliance-arc-close_v1_2026-10-23-1300.md
DATE: 2026-10-23
DECISIONS: Tee ruled on cards: ship the image lanes and the TypeSafe skill and merge on green; hold the Jev router hook for an allowlist rebuild; fix the gate timeout, the _unwrap slowdown, the flag regex slowdowns and the git push option gap each in its own PR; fix the dead compliance gates before anything else; write the TQO FINAL V5 n8n draft now; fix the 20,000 character quoted payload gap and the lease to a URL remote each in its own PR; gate Bash commands over 1,000,000 characters unread. He stopped the handover workflow, and on 2026-10-23 ruled the arc closed.
FINDINGS: The outward gate could outrun its 15 s timeout three ways, closed by #366, #369 and #370. git push -4f, -ud, --del, --mir and --pru force, delete or mirror under real git 2.43 and passed the gate ungated, closed by #401. A quoted bash -c payload padded past 20,000 characters hid a gated command, closed by #403 with a size limit that also ends the timeout class. A lease to the session's own branch could reach a URL or path remote, closed by #405. The critical Next.js RCE advisory GHSA-2464-fhr4-w9xw was cleared by #404 and its production deployment read back. The #367 compliance code reaches READY_FOR_HUMAN_REVIEW on the export's own chain and never releases alone. The Pulse watchdog shows alert sends timing out on 2026-10-20 and 2026-10-22.
OPEN: Publish the TQO FINAL V5 draft and read it back; four #367 gaps to rule on; TypeSafe funding; the Jev hook allowlist rebuild; the #359 read back in a fresh session; the watchdog's timed out alert sends unread at the execution; eight gate gaps that main shares, listed under Open; removing the Agent Archive plugin from the claude.ai account.
STATUS: Everything listed under What shipped is merged. CI on main is green on `e48fd6b`. The n8n draft is unpublished as of 2026-10-17.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
