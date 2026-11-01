# The thread pin is live on the n8n box, and the box rebuilt Proof 0

Written 2026-11-01. It follows
`SYS_OPS_render-worker-node01-acceptance_v1_2026-11-01-0056.md`, merged in PR
#472, and closes the two items that doc left open: the redeploy of the pinned
`acx_node.js` and the rerun on the box.

## The redeploy

PR #472 merged as `a85af9a`. Its six worker files differ from what the box ran,
`122bc70`, in `acx_node.js` alone, and Tee ruled on a card to copy that file
alone. The copy therefore left the box on one commit.

The merge commit was fetched into `/tmp/rw-a85af9a` on the box and the seven
files hashed equal to the repository's. The five suites ran on the box's own
Node 18.19.1. jobs.test.js read 136, acx_node.test.js 36 and tsws-repair.test.js
22, and the negative control passed; each exited 0. server.test.js read 46
passed and 1 failed on its first run, and 47 of 47 on its one re-run at load
0.41. The failing test is the next section.

`/status` read 0 running and 0 queued immediately before the copy and again
immediately before the restart. The old file was kept as
`acx_node.js.bak-20261101-pin`, with its owner and mode carried over. The
service restarted at 06:28:57Z with no restarts counted. `/health` on the bridge
address read 25 job types, with `tsws_repair`, `word_timings`,
`acx_node_assemble` and `caption_srt` among them. All six live files hash byte
identical to `a85af9a`.

The restart dropped the job table. It held five finished jobs from the session
Tee started, the last ending at 01:39:21Z, about five hours before. Their
records went with the table; their output files stay on disk.

## The test that lost a race on the box

`server.test.js` checked the access line for a file read after a fixed 50 ms
wait. The line is written on the response's finish event, which lands after the
client sees the end. With no wait at all the check failed 6 runs of 6 in the
container, so the 50 ms was a race that the 2 core box lost once in two runs.

The test now waits for the line itself, up to 2 s. Five plain runs passed and
three runs on one loaded core passed. As a negative control, a copy of
`server.js` writing `type=blob` made the test fail after its deadline, 46 passed
and 1 failed. This is a test change only; `server.js` is unchanged.

## The rerun on the box

Job `f733b68c-fa3e-4b9f-bc54-686feb420a1c` ran Node 01 on the box's masters and
lines with the sandbox word timings, from 06:29:42Z to 06:36:49Z (426.6 s). Its
master hashed `9e2802af97d8a235d0029b22a027d4efacd755617c448359fd700bfeabc4d16e`,
the Proof 0 master byte for byte. The five shot segments, the silent picture,
the overlay picture, the narration mix and the three caption files matched the
sandbox too, and the box's five masters hash the same as the sandbox's.

So with the pin, a box render differs from Proof 0 only through the word
timings the box's own speech model produces. The acceptance render made from
those timings, `c2562dd5...`, stays in `acx/node01/out` for Tee's watch.

## Cleanup

Tee ruled on a card to read the result and clean up. Removed by exact path and
read back gone: the rerun's output `acx/node01/out_pin` (257 MB), the sandbox
words file, `/tmp/acx-node01-job-pin.json` and the staged `/tmp/rw-a85af9a`.
`/tmp/rw-122bc70`, the staging of the session Tee started, was left alone. The
worker still read 25 afterwards.

## The gate

The outward gate refused this session's box calls twice. The first refusal came
when Tee's last answered card read 162 minutes old, the second at 670 minutes;
both came after container restarts. Each time the decision went to Tee on a card
and the identical call was retried after his answer. Nothing was rephrased.

## The critic

A fresh critic checked 72 claims in commit `0b759c0` and raised one: that the
00:59Z upgrade was "by another session" was inferred, since the transcript shows
only that this session did not make it. An independent verifier confirmed it.
Tee then said on a card that it was a session he started. The acceptance doc and
`DEPLOY.md` now say so.

## DEVON RECEIPT

AREA: Systems, Podcast
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_render-worker-pin-on-the-box_v1_2026-11-01-1720.md
DATE: 2026-11-01
DECISIONS: Tee ruled on cards to redeploy only acx_node.js from the merge of PR #472, to go ahead with it when the gate needed a fresh word, and to read the box rerun and clean up its output and the sandbox words file. He confirmed on a card that the 00:59Z upgrade of the box to 122bc70 was a session he started.
FINDINGS: The pinned acx_node.js is live on the n8n box since 06:28:57Z; all six worker files equal a85af9a and /health reads 25. On the box, with the sandbox word timings, the pinned code rebuilt the Proof 0 master 9e2802af byte for byte in 426.6 s, so a box render now differs from Proof 0 only through the box's own word timings. server.test.js lost a fixed 50 ms race once on the 2 core box; the test now waits for the line, with a negative control. The restart dropped five finished job records of the session Tee started; their files stay.
OPEN: Tee's watch of the Node 01 master in acx/node01/out (c2562dd5). Why the box's base.en run differs from the sandbox's by 20 to 40 ms on 33 of 260 word edges. The session Tee started has not recorded its 00:59Z deploy or its 01:05Z to 01:39Z jobs in this repository.
STATUS: Redeployed and proved on the box; rerun output and the sandbox words file removed; the acceptance render kept for Tee's watch.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
