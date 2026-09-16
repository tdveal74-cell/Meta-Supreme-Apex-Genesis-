# A picked suffix races

2026-09-16. The sequence letter rule was one day old when it broke the build it
was written to protect. This replaces the picked letter with a derived stamp,
and records that OS 29 is fully unblocked.

## What went wrong with the letter

Ruled 2026-09-15, landed 2026-09-16: every status doc's filename carries a
sequence letter after the date so a day's docs sort into the order they were
written. On the first full day it existed, two of them chose `a`.

```
SYS_OPS_the-vps-cutover-proven_v1_2026-09-16a.md               01:08:41
SYS_OPS_the-qc-gate-called-his-own-receipts-invented_v1_...a.md 01:51:18
```

Neither session was careless. Each read `docs/devon/`, found no doc for
2026-09-16, and took the first free letter. The other session's file existed
only on an unmerged branch in another container, where it is invisible. Both
answers were correct against the evidence each could see, and they were
different answers to the same question.

PR #236 merged at 01:58 and PR #235 at 02:00, and the second merge put two `a`
files on the same day. `main` went red. The next PR inherited it, because its
base was that commit.

The letter was not the problem. Picking was. Any suffix chosen by reading a
directory races whenever two sessions write on the same day, and this estate
runs several sessions at once by design.

## What replaces it

From 2026-09-17 the suffix is the UTC hour and minute the doc was written:

```
SYS_OPS_a-thing-that-happened_v1_2026-09-17-0342.md
```

`date -u +%Y-%m-%d-%H%M` prints it. The rule is to take it from the clock, not
from the directory, because the whole point is that it is derived. Two sessions
in different containers reach different answers without seeing each other, and
the filename still sorts a day into writing order, which is the only thing the
suffix was ever for.

A collision now needs two docs written inside the same minute. That is rare
rather than impossible, and the uniqueness assertion that caught this one still
catches that one.

2026-09-16 stays letters only. Its docs are already named, and digits sort
before letters, so accepting both forms on one day would misorder the very
thing the suffix exists to order. This doc is `d` under the old rule, which is
the last one written that way.

## Proving it bites

The regex change alone would pass every test while enforcing nothing, so the
rule was run against four real files in `docs/devon/` and each was removed
again:

```
SYS_OPS_probe_v1_2026-09-17.md        no suffix     -> failed, names the fix
SYS_OPS_probe_v1_2026-09-17-9999.md   not a time    -> failed, 9999 is not 99:99
SYS_OPS_probe_v1_2026-09-17a.md       old form      -> failed, letter after the cutover
two docs both -0342                   duplicate     -> failed, names the reused suffix
SYS_OPS_probe_v1_2026-09-17-0342.md   correct       -> passed
```

The `9999` case is the one worth keeping. Four digits is not a time of day, and
a typo that parsed would sort silently into the wrong place, which is exactly
the failure this rule exists to prevent. The test now reads the stamp as hours
and minutes rather than as a shape.

## OS 29 is unblocked

Both refusals that had it detecting policy changes and assessing none of them
are cleared, and each was measured rather than taken on report.

The assessment call runs on Cerebras `gpt-oss-120b`, proven in both directions
on the real credential: execution 218 returned material true, gate disclosure,
all three shows named on a seeded synthetic media rule; execution 219 returned
material false, gate none on a seeded support hub link.

The Firecrawl key Tee rotated is now in credential `Nld2jqeJyTfv8jNh`. Probe
execution 225 ran the real `Firecrawl Render` node, with `onError` stripped so
a bad key would throw rather than pass its error downstream, and scraped
example.com: `success: true`, 167 characters of markdown. All three throwaway
probes are archived.

What has not been run is OS 29 end to end. That fetches every watched policy
page, writes to Airtable and emails Tee, so it is his to trigger rather than
something to fire off as a test. The two nodes that were broken are each proven
working; the sweep around them is unchanged since it last ran.

## What is still open

The Anthropic account is unfunded. Nothing on the VPS calls it now, which makes
it harmless today and a trap for the next node that reaches for it.

Neither code review bot has reviewed any recent pull request. CodeRabbit
reports that this repository gets no automatic reviews because it has fewer
than ten stars, and the Codex connector reports its account is out of code
review usage. Recent PRs had CI and the session's own checks and nothing else,
which is worth knowing before reading a green tick as coverage.

Three of OS 29's twenty three nodes are mirrored into `n8n/os29/`. The rest are
live only.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_a-picked-suffix-races_v1_2026-09-16d.md
DATE: 2026-09-16
DECISIONS: Tee ruled to fix the sequence letter race rather than leave it to the test to catch each time, overruling the recommendation to leave it. From 2026-09-17 the suffix is the UTC hour and minute the doc was written, taken from date -u rather than by reading the directory, so it is derived and two sessions reach different answers without coordinating. 2026-09-16 stays letters only because its docs are named and digits sort before letters, so a mixed day would misorder the thing the suffix exists to order. OS 29 was left for Tee to run end to end rather than fired as a test, because a real pass writes to Airtable and sends mail.
FINDINGS: The letter collided on the first full day it existed. Two sessions forty three minutes apart each read an empty 2026-09-16 and each took the first free letter; the other's file was on an unmerged branch in another container and invisible. PR #235 merging second turned main red and the next PR inherited it. The letter was not at fault, picking was: any suffix chosen by reading a directory races when two sessions write on the same day, which this estate does by design. The new rule was run against four real files rather than only synthetic strings: a bare date, a 9999 stamp, an old style letter after the cutover, and a duplicate stamp all failed with messages naming the fix, and a correct stamp passed. Tee's two reports were both checked rather than recorded: the Cerebras repoint is proven by executions 218 and 219, and the rotated Firecrawl key by probe execution 225 returning success true and 167 characters of markdown with onError stripped so a bad key would throw. Neither code review bot has reviewed a recent PR: CodeRabbit is off below ten stars and Codex is out of usage.
OPEN: The Anthropic account is unfunded, harmless while nothing on the VPS calls it and a trap for the next node that does. OS 29 has not been run end to end since both blockers cleared, and that is Tee's to trigger because a real pass writes rows and sends mail. Three of OS 29's twenty three nodes are mirrored; the rest are live only. The two review bots are silent by configuration, so a green tick on a recent PR is CI and the session's own checks, not bot review.
STATUS: The sequence suffix is derived from the clock from 2026-09-17 and enforced by test_devon_receipt_shape.py, proven to fail on four real mutations and pass on the correct form. OS 29's two blockers are both cleared and both measured. CLAUDE.md carries the ruling.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
