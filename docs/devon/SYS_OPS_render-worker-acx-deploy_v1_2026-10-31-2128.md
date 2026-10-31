# The ACX Node build is live on the n8n box

Written 2026-10-31. It closes the deploy that
`SYS_OPS_render-worker-drift-and-the-wrong-box_v1_2026-10-31-0921.md` left open,
and supersedes that doc's OPEN line on it.

## What ran

Tee ruled the deploy on a card, then ruled it again when the outward gate
closed after two hours, choosing the version where an independent workflow
checks the result. All of it ran through Desktop Commander on the n8n box, the
host the worker runs on. The EditForge box was not touched.

`GET /status` read idle at 18:30:50Z: nothing running, nothing queued. The
render worker directory from merge commit ac691aa was fetched into `/tmp` on the
box, and its six deploy files hashed the same as the repository's. The five
suites ran there on the box's own Node 18.19.1. jobs.test.js passed 115,
acx_node.test.js 35, server.test.js 47 and tsws-repair.test.js 22. The negative
control failed 110 of 115 against the unfixed engine, which is the pass
condition. Each exited 0.

At 18:41Z the six files went into `/opt/tsws-render-worker`. The four that
replaced something were kept as `.bak-20261031`. The unit and its repair
drop-in were not touched. Next came the whisper venv, three Chakra Petch faces
under the work root fetched from the same Google Fonts files as Proof 0, and
`/data/tsws/hf` owned by `tsws`. The env file got two appended lines,
`WHISPER_PYTHON` and `HF_HOME`, through the guarded block in `DEPLOY.md`. No
value from the token line was printed: the two new lines were echoed, and the
other keys by name only. `/status` read idle again at 18:51:32Z. The
service restarted at 18:51:45Z, drained with 0 jobs running, and came back with
24 job types.

## What the verifiers found

Seven read-only verifiers and a critic ran first. Three claims came back
confirmed: the six live files match ac691aa, the env holds exactly four keys,
and the running process carries the two new values. The unit was confirmed
unchanged, though that verifier stopped at the gate before its last
supplementary read.

One claim was false, and it was the session's. It reported that `/health`
answered on loopback as well as on the bridge. On the n8n box `127.0.0.1:8080`
is the Temporal UI's docker proxy, and its `/health` returns HTTP 200 with an
HTML page. The worker binds only the bridge address, as `DEPLOY.md` says it
should. The 24 jobs were real; the second address was not the worker.

The run took 151 minutes. Most of it was two verifiers each held on one
Desktop Commander call from 18:56Z to 21:14Z, about 138 minutes, and the cause
was not found. The gate's two hour window closed partway through, so four
verifiers and the critic were refused and stopped there without rephrasing. Tee ruled a shorter
re-run on a fresh card. Two verifiers finished in 55 seconds and confirmed
everything that had been left open. The fonts match Proof 0, and the deployed
parser reads their three names. The venv imports faster-whisper 1.1.1, av
13.1.0 and requests 2.34.2 as `tsws`. The model cache is writable by `tsws` and
sits inside the unit's write paths. `tsws` reaches Hugging Face. ffmpeg
6.1.1-3ubuntu5 lists every filter and encoder the ACX job calls; the one no
verifier read, `pcm_s16le`, the session read itself after the record's critic
found the gap. Every suite
log predates the copy, by 21 seconds for the last one. The journal shows both
idle reads, no job submitted in the window and no 401. The backups load the old
22 job build.

The critic also found that `DEPLOY.md`'s new-host Caddy block proxies
`render.editforge.online` to `127.0.0.1:8080`. That name has no DNS record
(NXDOMAIN from dns.google), so nothing reaches it by that name today; no host
was read for whether it carries the block. On the n8n box,
though, that block would publish the Temporal UI under the worker's name.
`DEPLOY.md` now says so beside it.

## What this PR changes

`DEPLOY.md` records the deploy, 24 read on the bridge, the loopback trap in
four places, and what the verifiers read on the box. `CLAUDE.md` replaces an
"unverified" line about the gate and subagents with the measurement. The ledger
holds 52 allow rows from subagents and workflow agents, 43 of them gated calls
naming the age of the parent's card or message, and 6 deny rows after that word
passed two hours. A long workflow
that makes gated calls therefore outlives the window, and the file now says to
keep such runs short.

## Not done

The Node 01 acceptance render has not run on the box. That is a separate step:
it is the first `word_timings` run with its model download inside the unit's
sandbox, and the first ACX master from the box's own ffmpeg. Its `build.json`
gets compared against the sandbox record before any Node from this path goes to
Tee's watch.

The deploy's leftovers in `/tmp` on the box were the staged copy with its suite
and venv logs, and three capture files two verifiers wrote outside the directory
they were allowed. Tee ruled on a card to remove all four. They were removed by
exact path and read back gone, and the worker still answered 24 afterwards.

## DEVON RECEIPT

AREA: Systems, Podcast
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_render-worker-acx-deploy_v1_2026-10-31-2128.md
DATE: 2026-10-31
DECISIONS: Tee ruled on a card to deploy the ACX Node build to the n8n box with an independent workflow verifying it, after the gate closed on his first card at 123 minutes. When the first verify run outlived the gate window, he ruled on a second card to re-run the cut off checks shorter.
FINDINGS: The render worker on the n8n box runs merge commit ac691aa with 24 job types, read on the bridge address. The six live files are byte identical to the commit, the ACX runtime (venv, fonts, model cache, env) is in place, and the unit is unchanged. Independent verifiers confirmed every claim but one. The session's report that loopback 8080 answered for the worker was false: that port is the Temporal UI. The DEPLOY.md Caddy block for render.editforge.online would front the Temporal UI on that box, and the name has no DNS record today. The outward gate reads the parent's card or message for a workflow agent, so a 151 minute workflow outlived its 120 minute window, most of it two Desktop Commander calls held about 138 minutes each for a cause not found.
OPEN: The Node 01 acceptance render on the box, the first word_timings model download inside the unit, and the build.json comparison against the sandbox record. Tee's watch of the Proof 0 master. Who deployed tsws_repair on 2026-10-17 and whether an n8n workflow calls it.
STATUS: Deployed and independently verified on the box; the acceptance render has not run. The deploy's leftovers in /tmp on the box were removed on Tee's card and read back gone, with the worker still active at 24 jobs.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
