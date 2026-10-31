# The render worker ran a build no commit held, and two steps went to the wrong box

Written 2026-10-31. It covers one session's work on deploying the ACX Node build
(PR #431) to the render worker, which found two things before anything was
deployed: the steps were being run on the wrong VPS, and the live worker carried
a job the repository did not have.

## The wrong box

The ACX box steps in `deploy/render-worker/DEPLOY.md` were handed to Tee one line
at a time. Asked which VPS, the session answered the EditForge VPS from memory.
That was wrong: the worker runs on the n8n box, which `DEPLOY.md`, the
2026-10-16 Voice Lab status doc, the 2026-09-05 estate map and Tee's own R22
ruling ("Render worker job on the n8n box") all say. Two steps ran on the
EditForge box. The first made a 451 MB whisper venv at
`/opt/tsws-render-worker/whisper` (it also hit a missing `requests` package,
fixed in PR #445). The second failed on `chown: invalid user: tsws:tsws` and
`/etc/tsws-render-worker.env: No such file or directory`, and in failing it
created that file with two lines, plus empty `/data/tsws/hf`.

An independent verifier confirmed all four items were created on 2026-10-31 and
that nothing on that box reads them: no unit, cron entry, container mount or
process. Similar names there belong to live services (`comfyui-tsws`,
`tqo-hf-bridge`, `/root/whisper`), so the cleanup names four exact paths. Tee
ruled on a card to have the session remove them. The removal was refused by the
outward gate because his answer was 292 minutes old when the session came back
to it, and it waits for a fresh word.

## The build no commit held

Read through Desktop Commander on 2026-10-31, read only. The worker on the n8n
box is active, runs `/usr/bin/node` 18.19.1 as `tsws`, and its `/health` lists 22
jobs. The 22nd is `tsws_repair`. Its `jobs.js`, `server.js` and `package.json`
are dated 2026-10-17, with a new `tsws-repair.js` beside them and a systemd
drop-in `repair-v01.conf` setting five `TSWS_REPAIR_` variables. The service last
restarted 2026-10-28T06:31:23Z.

Rebuilding the three files from d75114d, the last deploy recorded as byte
identical, plus three changes reproduced the live sha256 of each exactly. The
changes are the `tsws_repair` entry in `jobs.js`, a claim hook in `server.js`
that runs before a job is queued and passes a 409 or 503 through instead of a
500, and a `tsws-repair.test.js` line in the test script. A second independent
verifier confirmed the hashes, the rebuild and that no ref of the repository
holds `tsws-repair.js`, `TSWS_REPAIR_` or `spec.claim`. No status doc records the
deploy; the 2026-10-14 doc on the repair arc still said the job did not exist.

The cost had it gone unseen: `DEPLOY.md`'s install step copies the repository's
`jobs.js` and `server.js` over the live ones, which deletes `tsws_repair`, and
copies the committed unit file, which rebinds the worker to loopback where the
n8n container cannot reach it.

## What this PR does

It brings the live build home. `tsws-repair.js` is byte identical to the live
file (sha256 `4af32fea...`, 11,656 bytes). The same three changes are applied on
top of `main`, so `server.js` hashes exactly as the live one and `jobs.js` is
`main`'s plus the one entry. `tsws-repair.test.js`, which the box's own
`package.json` named and nobody had written, pins the bridge as a stand-in
package sees it and the claim hook in 21 tests, and each of fifteen deliberate
breaks to the job, the hook or the `jobs.js` entry turns it red. A fresh critic
found seven of those fifteen surviving the first version's 15 tests (the cache
symlink refusal, the job path rewrite, the byte count, the output symlink
refusal, `abort()`, the log cap and the claim running before the queue-full
check); the six tests that catch them were added and each break re-run. The
same critic found that `DEPLOY.md` overstated the bridge's path checks: in the
staged job file only three keys are checked, and the doc now says so. It runs
in the render worker CI. `DEPLOY.md` gains
the job, its drop-in with the bridge address as a placeholder, which host the
ACX steps belong on, and an upgrade procedure for the live box that never copies
the unit file. The repair skill's sentence saying the job does not exist is
corrected.

Nothing is deployed by this PR. The ACX deploy to the n8n box follows it, through
Desktop Commander, and needs Tee present for the outward gate.

## DEVON RECEIPT

AREA: Systems, Podcast
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_render-worker-drift-and-the-wrong-box_v1_2026-10-31-0921.md
DATE: 2026-10-31
DECISIONS: Tee ruled on a card to have the session remove the four stray paths from the EditForge box, and to bring the live repair build into the repository first and deploy the ACX build after, through Desktop Commander. The removal waits for a fresh word because the outward gate refused it at 292 minutes.
FINDINGS: The render worker runs on the n8n box; two ACX steps ran on the EditForge box after the session named the wrong host from memory, leaving four stray items that nothing reads. The live worker has carried tsws_repair since 2026-10-17 with no commit or status doc, proven by rebuilding its three files from d75114d to the live sha256 and confirmed by two independent verifiers. The DEPLOY.md install steps would have deleted that job and rebound the worker away from n8n.
OPEN: The four stray paths on the EditForge box; the ACX deploy to the n8n box, with the whisper venv, HF_HOME and fonts made there; who deployed tsws_repair on 2026-10-17 (the box holds three envelopes claimed that day and none since, by the claim folder's 2026-10-17T11:19:50Z mtime) and whether an n8n workflow is wired to call it; GET /status on the n8n box before any restart; whether to tighten the staged job checks, which would break byte identity with the box; Tee's watch of the Proof 0 master.
STATUS: Live build reproduced byte for byte and brought into the repository with tests and the deploy procedure corrected; nothing deployed and nothing removed yet.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
