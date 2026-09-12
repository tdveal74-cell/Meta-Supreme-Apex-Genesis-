# The wire, the tab, and the wrapped token

2026-09-12. The render worker was deployed and proved from the box on the same
date, recorded in `SYS_OPS_the-render-worker-was-never-deployable_v1_2026-09-11.md`.
This doc covers what happened next: making n8n itself reach it.

`TSWS 00 (Render Job)` is the sub-workflow every TSWS pipeline calls to touch
media. Its own sticky note, rev 3, has carried this line since August:

> **SMOKE TEST BEFORE ANYTHING ELSE.** Execute this workflow manually with
> `{ "type": "exists", "params": { "path": "." } }`. `ok:true` proves Cloud
> reached the box, the token is right and the URL resolved. **That call has never
> once succeeded.**

At 03:29:09Z on 2026-09-12 it succeeded.

```
execution   11, manual, 2026-09-12T03:29:09.644Z to 03:29:24.786Z, 15.1s
Submit Job  202 Accepted, body.id 0b93daa1-e758-4498-b445-5d8be73c4d63, status queued
Wait        15s, one poll cycle
Poll Job    status done, ok true, result {"hit":false,"reason":"not a file"}, seconds 0.001
Return      {ok:true, status:"done", job_id:..., seconds:0.001, type:"exists"}
```

The 15.1 seconds is itself evidence. It is exactly one `Wait To Poll` cycle, so
the poll loop ran once and terminated, which a looping graph could not do.

## Defect one: a node wired to itself

Executions 3 and 4 ran for 3m33s and 2m07s and were cancelled by hand. The draft
carried a connection from `Submit Job` back into its own input:

```
"Submit Job": {"main": [[{"node": "Accepted?", ...}, {"node": "Submit Job", ...}]]}
```

It was not in the published version, only in the draft, so the callers were never
affected. The version history dates it exactly: added by a UI autosave at
02:11:30Z, thirty eight seconds after execution 1 errored.

The part worth keeping is what happened next. It was removed through MCP at
02:45Z and published. At 02:51:31Z an autosave from a browser tab that was still
open **restored it**, and also reverted an unrelated edit to `Prep Request` made
at 02:36Z. Execution 5 at 02:55Z therefore ran with the loop back in place.

**n8n writes the whole canvas on autosave, not a delta.** A tab holding older
state will silently overwrite anything changed through MCP, and the overwrite
looks exactly like the fix never applied. Two rules follow:

* Close the browser tab before editing a workflow through MCP. A refresh is not
  enough if the tab autosaves before it reloads.
* Confirm with `get_workflow_versions_diff` afterwards rather than trusting the
  update call's success response. The second removal was only caught because the
  diff was read, not because anything reported a problem.

## Defect two: a space where the terminal wrapped

With the loop gone, four consecutive runs returned HTTP 401 in about 15ms each.
Four theories were produced and all four were wrong. What ended it was reading
the wire:

```
tcpdump -i any -s0 -n -w /tmp/w.pcap 'tcp dst port 8080'
tcpdump -A -r /tmp/w.pcap | grep -i 'POST /jobs\|authorization'
```

The header was:

```
Authorization: Bearer <34 hex chars> <30 hex chars>
```

A 64 character token carrying a literal space 34 characters in. The header name
was right, the `Bearer` prefix was right, the single space after `Bearer` was
right. The token had been copied out of a wrapped terminal display and the wrap
became a space.

The worker strips exactly `Bearer ` and compares the remainder byte for byte, so
it failed, and the 401 carried no more information than that. Three lessons:

* **Read the wire earlier.** One `tcpdump` settled in a single round what four
  rounds of reasoning did not.
* **`tcpdump` piped into `grep` buffers in 4KB blocks.** Without `-l` the buffer
  never flushes before `timeout` kills it, and the operator sees nothing, which
  reads as "no traffic reached the box". Capture to a file instead. The first
  attempt at this diagnosis was lost to exactly that.
* **Length is a usability property of a token, not only a security one.** The
  replacement is 32 hex characters, chosen so that `Bearer ` plus the token fits
  one line at the 39 column width of the operator's terminal and cannot wrap.
  128 bits, still well over the worker's own 24 character floor.

## A diagnosis withdrawn

Between the two defects a wrong call was made and is recorded here rather than
quietly dropped. The claim was that `$json` does not resolve to the incoming item
in a Code node's "Run Once for All Items" mode, and that `Prep Request` had
therefore been broken since it was written in August. The stack trace naming
`JsTaskRunner.runForAllItems` was read as confirmation.

It was wrong. Execution 3 reached `Submit Job` with `$json` still in place, which
it could not have done if `$json` were failing. Execution 1 failed for the plain
reason that the run was started with no input at all.

The `$input.all()` rewrite was kept, because it is correct in either Code node
mode and the new throw reports how many items arrived and what the first one
contained. The reasoning behind it was wrong, and the node comment now says so in
the file rather than only here. Four other Code nodes in the same workflow carry
the same `$json` pattern and were deliberately left alone once the theory
collapsed.

## A secret that went where it should not have

The header above was read off the operator's screen, and the natural way to
report it was a screenshot, which put a live bearer token into a chat transcript.
The instruction had said not to paste the token; it had not anticipated the
screenshot, which is the same failure as not anticipating the wrap.

The token was rotated immediately, the pcap was deleted, and the old value is
dead. The rule that follows is a design rule rather than an instruction: a check
that requires a human to look at a secret will eventually put that secret
somewhere it does not belong. Build the check so the secret is never displayed,
or rotate as part of the procedure rather than as a reaction.

## A configuration lesson worth keeping, without the target

One general rule came out of an unrelated check on the same box and is recorded
here because it will catch someone else:

**`sshd` takes the FIRST matching directive, not the last.** Ubuntu puts an
`Include /etc/ssh/sshd_config.d/*.conf` at the top of the main config and reads
those files in lexical order, so a hardening file named `99-` is silently
ignored when a `50-` file already set the same directive. `sshd -T` is the only
honest read, because it prints the effective config rather than what any one file
says. A hardening that never took effect is worse than none, because it reads as
protection to the next person.

The state of any specific host is deliberately not recorded in this repository,
which is public. Live posture findings for the estate's boxes belong in the
private DEVON log, and the one from this session is filed there.

## What is proved and what is not

Proved: the plumbing. n8n resolves the URL, reaches `BRIDGE-GATEWAY:8080`,
authenticates, submits, polls, and returns a result, and it degrades through
`Submit Rejected` with the worker's own error text when the worker refuses.

Not proved: anything about what the worker produces. No acceptance check has
measured a single audio sample or video frame. The four step suite in
`deploy/render-worker/DEPLOY.md` is what settles that, and step 3, the A1 gain
envelope, is the one that decides whether the sound bed comes back after a duck.
That is the defect that killed the bed for the last 53 seconds of EP01 and passed
every gate the estate had, because the only gate measured length.

## DEVON RECEIPT

```
AREA: Podcast, Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-wire-the-tab-and-the-wrapped-token_v1_2026-09-12
DATE: 2026-09-12
DECISIONS: keep the worker bound to the n8n_backend bridge gateway BRIDGE-GATEWAY rather than loopback, because a container's 127.0.0.1 is the container; rotate the worker token to 32 hex characters, chosen so that Bearer plus the token cannot wrap at the operator's 39 column terminal width, 128 bits and still over the worker's 24 character floor; keep the $input.all() rewrite in Prep Request even though the reasoning that produced it was wrong, because it is correct in either Code node mode, and record the withdrawal in the node comment rather than only in a doc; leave the four other Code nodes carrying $json untouched once that theory collapsed; defer a host hardening change rather than fight a terminal that had refused three consecutive commands, having established that nothing was reloaded and therefore nothing is half applied; keep live host posture findings out of this repository, which is public, and file them in the private DEVON log instead.
FINDINGS: TSWS 00 returned ok:true end to end for the first time in the project's life at 2026-09-12T03:29:09Z, execution 11, 15.1 seconds, job id 0b93daa1-e758-4498-b445-5d8be73c4d63, result hit false reason not a file, seconds 0.001, against a sticky note that had recorded the call as having never once succeeded since August. Two defects stood in the way. The first was a connection from Submit Job back into its own input, present only in the draft and never in the published version, added by a UI autosave at 02:11:30Z; removed through MCP at 02:45Z and then RESTORED at 02:51:31Z by an autosave from a browser tab still holding the older canvas, which also reverted an unrelated edit, because n8n writes the whole canvas on autosave rather than a delta, so a stale tab silently overwrites MCP edits and the overwrite is indistinguishable from the fix never applying. The second was a bearer token carrying a literal space 34 characters into a 64 character value, where the operator's terminal had wrapped the line during a copy; the header name, the Bearer prefix and the single space after it were all correct, and the worker's 401 carried no further information. Four consecutive 401s produced four wrong theories and one tcpdump read of the wire ended it in a single round; a first attempt at that read was lost because tcpdump piped into grep buffers in 4KB blocks and without -l the buffer never flushes before timeout kills it, which presents as no traffic. A diagnosis is withdrawn: the claim that $json does not resolve in a Code node's Run Once For All Items mode, and that Prep Request had been broken since August, was disproved by execution 3 reaching Submit Job with $json still in place; execution 1 failed because the run was started with no input. A live bearer token reached a chat transcript because the header was read off a screen and answered with a screenshot; the token was rotated and the pcap deleted, and the rule taken from it is that a check requiring a human to look at a secret will eventually put that secret somewhere it does not belong. One general configuration lesson is recorded here and its target is not: sshd takes the FIRST matching directive rather than the last, and Ubuntu's Include of sshd_config.d is read in lexical order, so a hardening file named 99- is silently ignored when a 50- file already set the same directive, and sshd -T is the only honest read because it prints the effective config. The live SSH and firewall posture of the estate's hosts was checked in this session and is filed in the private DEVON log rather than in this repository, which is public.
OPEN: run the two TSWS 00 failure path checks, type exists with empty params and type nope, both of which must return ok false and status invalid rather than throwing; run the four step acceptance suite in deploy/render-worker/DEPLOY.md on real media, because nothing yet has measured a single audio sample or video frame and step 3, the A1 gain envelope, is the one that decides whether the sound bed comes back after a duck; the host posture items raised in this session are tracked in the private DEVON log rather than here; decide what to do about the host identifiers and public addresses already recorded in this public repository by earlier commits in this branch; replace the account level shadow-we-share-brand skill body with the committed v2, 4,532 bytes against 9,203 and missing 103 lines across 7 sections, which only Tee can do from the skill settings page; add request logging to the render worker, whose absence is the direct reason this diagnosis took as long as it did; split Header Auth account 10 so the worker holds its own credential rather than sharing one of eleven similarly named header credentials on that instance.
STATUS: the plumbing is proved end to end and nothing about the render output is. n8n resolves the URL, reaches BRIDGE-GATEWAY:8080, authenticates, submits, polls and returns a result, and degrades through Submit Rejected carrying the worker's own error text when the worker refuses. TSWS 00 draft and published agree at ef28bc43-b1fa-43e2-a389-8224edb2234e with 13 nodes, and the graph is proved free of the self connection by behaviour rather than by diff, because a looping graph could not have terminated in one poll cycle. The worker token is rotated and the value that reached the transcript is dead. A separate host posture finding from this session is filed in the private DEVON log, not here. PR 207 head 21ec2f3 was green on all seven checks and clean before this correction was pushed.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
