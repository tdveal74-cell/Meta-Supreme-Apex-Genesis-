# TSWS render worker

The service that every ffmpeg, ffprobe and filesystem operation in the five TSWS
pipelines goes through. n8n has no `executeCommand` on the plan in use, so this
box is the only thing that can touch media.

**It ran for the first time on 2026-09-12.** Until then it had never run on any
host, because there was no server to run and the engine on Drive carried five
measured defects. What follows is what was wrong, what was fixed, what is proved
on the live box, and what is still unproved.

## Deployed

Host identifiers in this file are placeholders. `N8N-HOST`, `N8N-HOST-IP`,
`EDITFORGE-HOST`, `EDITFORGE-HOST-IP` and `BRIDGE-GATEWAY` stand in for real
values that are deliberately not recorded here, because this repository is
public. The real values live in the private DEVON log. Substitute them before
running anything below.

| | |
|---|---|
| host | `N8N-HOST`, `N8N-HOST-IP`, Ubuntu 24.04.4 LTS |
| resources | 2 cores, 7.8 GiB RAM, 96 GB disk |
| bound to | `BRIDGE-GATEWAY:8080`, the `n8n_backend` docker bridge gateway |
| node | 18.19.1, the Ubuntu 24.04 distro package |

Proved on that box, by execution:

* The Voice Lab build, deployed 2026-10-16 from merge commit d75114d through
  Desktop Commander. Staged in `/tmp` first and run there on the box's own
  Node 18.19.1 and ffmpeg 6.1.1: jobs.test.js 115, server.test.js 47, the
  negative control failing 110 of 115, and `voice-lab-acceptance.js` 19, each
  exit 0. The swap ran only with nothing running or queued on `/status`, kept
  the old files as `jobs.js.bak-20261016`, `server.js.bak-20261016` and
  `package.json.bak-20261016`, and the live files read back byte identical to
  the merge commit. Rolling back is copying those three over and restarting.
* All three suites: 27, 19, and the negative control failing 22 of 27 against
  the committed Drive original. After the 2026-09-15 presenter work, in the
  container and not yet on the box: jobs.test.js 51, server.test.js 46, both
  exit 0, counted from the harness line on the day. The negative control was
  last run at 36 of 41 before the stacked and the critic tests were added and
  has not been re-run since; that denominator is stale until someone runs it
  against the Drive original again. Exit code 0 on each, checked individually
  rather than inferred from a chain.
* `/health` reports 24 job types, read on the bridge address on 2026-10-31 at
  18:51:47Z, two seconds after the restart that loaded merge commit ac691aa.
  The 24 names equal the `JOBS` keys of that commit's `jobs.js` one for one,
  `tsws_repair`, `word_timings` and `acx_node_assemble` among them, as an
  independent verifier compared them. It read 18 before the 2026-09-15 build,
  19 after it, 21 after the 2026-10-16 restart and 22 from the 2026-10-17
  drift build (below) until this one.
* Read `/health` on the bridge address only. On N8N-HOST `127.0.0.1:8080` is
  the `docker-proxy` of the `temporal-ui` container (`temporalio/ui:2.34.0`),
  and its `/health` answers HTTP 200 with an HTML page. On 2026-10-31 a
  session took that 200 for the worker and reported it, and a verifier caught
  it. A 200 from loopback on this box says the Temporal
  UI is up and nothing about the render worker.
* The ACX Node build, deployed 2026-10-31 from merge commit ac691aa through
  Desktop Commander, by "Upgrading the live box" below. `/status` read idle
  (0 running, 0 queued) at 18:30:50Z and again at 18:51:32Z. Staged in `/tmp`
  and run on the box's own `/usr/bin/node` 18.19.1: jobs.test.js 115,
  acx_node.test.js 35, server.test.js 47, tsws-repair.test.js 22, and the
  negative control failing 110 of 115 against the unfixed engine, each exit 0.
  Copied at 18:41Z, keeping `jobs.js`, `server.js`, `package.json` and
  `tsws-repair.js` as `.bak-20261031`; `acx_node.js` and `words.py` were new
  there and have no backup. The unit and its drop-in were not touched and hash
  as they did before. The env file gained `WHISPER_PYTHON` and `HF_HOME` by
  append, the whisper venv and the three Chakra Petch faces were made, and the
  service restarted at 18:51:45Z with the journal reading `job types 24`. An
  independent verifier hashed the six live files and found each byte identical
  to ac691aa. Others read the suite logs (all dated before the 18:41:06Z copy),
  the two idle `/status` lines and the clean drain in the journal (no job
  submitted in the window, no 401 at all), and the backups: the four
  `.bak-20261031` files hash to the pre-deploy live files and load 22 jobs with
  no `acx_node.js`. Rolling back is copying those four over, removing
  `acx_node.js` and `words.py`, and restarting. The `.bak-20261016` set holds no
  `tsws-repair.js`, because that file did not exist then.
* **The box ran a build no commit held, from 2026-10-17 to 2026-10-31.** Read
  through Desktop Commander on 2026-10-31, read only, and confirmed by two
  independent verifiers the same day: `jobs.js`, `server.js` and
  `package.json` were d75114d's plus three changes, the `tsws_repair` entry,
  a claim hook in `server.js` and a test line, and a new `tsws-repair.js` sat
  beside them, with a systemd drop-in `repair-v01.conf` setting five
  `TSWS_REPAIR_` variables. Rebuilding the three files from d75114d plus those
  changes reproduced the live sha256 of each exactly
  (`6e779a98...`, `99946226...`, `6725d4d2...`). No branch, commit or status doc
  recorded the deploy, and the newest doc on the repair arc still said the job
  did not exist. Copying `main`'s files onto the box, as "Deploying it" below
  says, would have deleted `tsws_repair` from production. The repository now
  carries it byte for byte (`tsws-repair.js`, sha256 `4af32fea...`), with the
  same three changes, and with the test the box's own `package.json` named and
  nobody had written.
* Public IPv4 and IPv6 both refuse. The n8n container reaches the worker on the
  bridge address. Between those two facts the bind is proved by behaviour: it
  cannot be loopback, because the container reached it, and it cannot be
  `0.0.0.0`, because the public address refused.
* `exists` returned `ok:true`, which is the smoke test the sticky note on TSWS 00
  records as having never once succeeded.
* `probe` spawned a real **ffprobe**, captured stdout, parsed it, and returned a
  duration of exactly 1.0 on a generated one second file.
* `silence_detect` spawned a real **ffmpeg**, captured **stderr**, and its regex
  returned `count: 1` spanning 0 to 1 second. A non-empty result on purpose: an
  empty list would not distinguish "worked and found nothing" from "did not
  work".

* `TSWS 00` returned `ok:true` end to end from n8n itself on 2026-09-12 at
  03:29Z. Execution 11, 15.1 seconds, job id
  `0b93daa1-e758-4498-b445-5d8be73c4d63`, result
  `{"hit":false,"reason":"not a file"}`. Two defects had to be cleared before it
  would run and both are recorded in
  `docs/devon/SYS_OPS_the-wire-the-tab-and-the-wrapped-token_v1_2026-09-12.md`:
  a `Submit Job` wire looping back into its own input, and a bearer token
  carrying a space where a terminal had wrapped the line during a copy.

Still unproved on the live box: every one of the five defect fixes at the sample
and pixel level. The acceptance suite below is what settles that, and nobody has
run it.

### Two deviations from the committed defaults, both required on this box

```
Environment=HOST=127.0.0.1  ->  BRIDGE-GATEWAY
MemoryMax=8G                ->  5G
```

The first is the docker problem described under Deploying it. The second is a
defect in the committed unit file: `8G` is above this machine's 7.8 GiB total, so
the ceiling never binds and under pressure the kernel picks a victim, which could
be n8n rather than the render. Set `MemoryMax` below total RAM on any host.

## Provenance

The engine was recovered from Drive on 2026-09-11.

| | |
|---|---|
| Drive file | `jobs.js`, id `1LhJi3m8vYPTpRmgeYvnDjPYBHZF1H5ts` |
| size | 42,848 bytes, matching Drive's own metadata |
| sha256 | `6ed3109ab220cb986e7c33040e90fda4c103cf8afa5ee48137c7185ca55ecdae` |
| last modified on Drive | 2026-08-07T18:53:12Z |

That exact file is committed at `reference/jobs.drive-2026-08-07.js`, byte for
byte, and `negative-control.js` verifies its sha256 before using it. It is there
so the claim "these tests detect the defects" can be RUN by anyone with the
repository rather than taken on trust.

`jobs.js` here is that file with the fixes below applied. Its inherited comments
are left byte faithful, em and en dashes included (27 em, 1 en at line 692), so
the diff against the Drive copy stays auditable line by line. Every line added by
the fixes is dash free, checked mechanically against the diff. If you would
rather the whole file follow the house rule, say so and it gets one mechanical
pass; it was not done unasked because it would bury the real diff.

`server.js` has no Drive ancestor. It did not exist.

## What was wrong

Two Drive documents describe this engine and they contradict each other.
`WORKER_jobs.js_rev2_AUDIT_7AUG2026` says three defects were found **and fixed,
all measured**. `EP01_AUDIO_DEFECT_8AUG2026`, written the next day, says
`jobs.js` rev 2 still carries two original defects.

The file settles it. **The copy on Drive is the pre-audit one**, and it carries
every defect both documents describe. The audited and fixed copy was measured on
7 August and then never written back; a Drive full text search for
`normalizeChain` and `assemble_cut` returns exactly one `.js` file, this one.

| | defect | what it did | source |
|---|---|---|---|
| F1 | `assemble_cut` had no still handling at all | The image demuxer emits ONE frame and `trim=start=0:end=6` kept exactly that one. 37 of 37 EP01 shots are stills, so a 14 minute episode renders as a 1.5 second slideshow. | 7 Aug audit |
| F2 | no geometry, SAR or fps normalisation before `xfade` | QC measured *minimum* width 3840, not uniform 3840. On mixed sizes xfade fails to configure the output pad and ffmpeg writes a **0 byte file**. | 7 Aug audit |
| F4 | `scan_drop` hard coded a two level walk | `drop/EP01/manifest.json` sits one level down and was never seen, so the job returned `count:0`, which reads as "nothing to do" rather than "I looked in the wrong place". | 7 Aug audit |
| A1 | `duck_mix` built its guards from an `afade` pair | `afade=t=out` ramps to zero and then **holds zero forever**; the following `afade=t=in` multiplies everything before its own start by zero. Composed, they never reopen. On EP01 the bed died at 544.000s of an 880.907s episode and the final 53 seconds were digital silence under picture. | 8 Aug defect record |
| A2 | `amix=duration=first` was unpinned | It does not produce the first input's length. Measured: an 880.906757s stem came out at 880.849000s, 58 ms short, leaving the last frame and a half with no audio. `duration=longest` returned the identical value, so it is not a `duration=` problem. | 8 Aug defect record |
| A3 | no `-nostdin` on any ffmpeg call | `q` on a keyboard quits a render. A forty minute job should not be one keystroke from death. Low severity under systemd, which gives the process no terminal, and fixed anyway because it costs nothing. | 8 Aug defect record |

A1 is the one that decides whether you can ship. The 8 August record is blunt
about it: deployed as it stood, **all eleven remaining episodes ship with a dead
sound bed**, and the only automated gate in the lane measures length, which a
silent file passes exactly as well as a loud one.

## What was fixed, and how it is checked

- **F1** Decode once, normalise that single frame, then hold it with the `loop`
  filter. `-loop 1` also works and is what the v1 script did, but it re-reads and
  re-decodes the file for every output frame; a 63 second shot decodes a 4K JPEG
  1,512 times. The v3 measurement on 2 cores was 62.04s to 6.26s for a
  bit identical result, PSNR infinity. A still is declared per shot via
  `shots[i].still` and inferred from the extension only when nothing is declared.
- **F2** `normalizeChain()` puts
  `scale=...:force_original_aspect_ratio=decrease, pad=..., setsar=1,
  format=yuv420p` ahead of every shot. Decrease and pad, never increase and crop:
  a black bar is a bug report, a crop is a lie that discards a framed edge.
- **F4** `scan_drop` walks to `max_depth` (3 by default) and returns `root`,
  `scanned_depth` and `skipped_done`, so a zero is diagnosable rather than silent.
- **A1** The guards became one gain envelope,
  `volume=eval=frame:volume='...'`, which returns to unity because the
  expression says so. Overlapping guard windows are now refused rather than
  silently summed.
- **A2** When the caller passes `duration`, the mix gets `apad` plus `-t`. When
  it does not, `apad` is deliberately **omitted**, because `apad` without `-t`
  never terminates, and the result reports `pinned: false` so an unpinned mix
  says so instead of being quietly 58 ms short.
- **A3** `-nostdin` on `QUIET` and `MEASURE`, which reach ffmpeg only. It is not
  a valid ffprobe flag and the one ffprobe job builds its own argv; there is a
  test pinning that.

`assemble_cut` also now returns `stills`, `clips`, `fps`, `normalized_to`,
`expected_duration` and `exact`, so the assembly can be checked against the
manifest rather than trusted.

**`expected_duration * fps` equals the reported frame count only when `exact` is
true**, which means every shot was a still. That is the EP01 case, 37 of 37. A
still emits `round(d * fps)` frames, so its real length is quantised; the xfade
offsets are accumulated from those quantised lengths rather than from the
requested ones, because a manifest whose durations are not frame aligned
otherwise drifts, measured at up to 0.130s, which is 3.1 frames at 24fps, and an
offset that runs past the end of its own input is a broken join. A clip's emitted
length depends on its source rate and cannot be known without probing, so with
`exact: false` treat `expected_duration` as the requested length and let ffprobe
settle the rest.

### One thing deliberately NOT changed

The v3 script treats a manifest's `in` and `out` as **timeline positions** and
computes the xfade offset for join k as `shots[k].in`. `assemble_cut` treats them
as **source trims** and accumulates `sum(d) - k * xf`. Both are internally
consistent; they are different models, and which one the TSWS manifest actually
speaks has not been established. Changing it on a guess could silently move every
cut in the episode, so it was left alone and is recorded here instead. Settle it
against a real manifest before the first full episode.

## What is proved here, and what is not

Proved, by execution, in this repository:

`npm test` runs all three. The counts in this section are from the first
build and are kept as its record; as of 2026-10-16, after the Voice Lab work,
jobs.test.js reads 99 passed, server.test.js 47 passed, and the negative control
fails 94 of 99 against the Drive original, all in the session container.

- `node jobs.test.js` pins what the builders emit: **27 tests**. Includes a
  numeric comparison of the new gain envelope against the EP01 reference
  expression over 540s to 552s at 0.5 ms steps, worst divergence `5.7e-14`; the
  exact xfade offsets; and the protected-silence provision.
- `node server.test.js` makes real HTTP requests against a real listening
  server: **35 tests**. It runs `{"type":"exists","params":{"path":"."}}`, the
  exact smoke test the sticky note on TSWS 00 prescribes and records as having
  "never once succeeded", and gets `ok:true`.
- `node negative-control.js` runs the same `jobs.test.js` against
  `reference/jobs.drive-2026-08-07.js`, the engine byte for byte as recovered,
  and **requires that it fail**. It currently fails 22 of 27. It verifies the
  fixture's sha256 and its absence of the audit markers first, so it cannot
  quietly drift into testing the fixed file.

Every guard added here was mutation tested: the fix was reverted one at a time
and the suite was required to go red. Six for six on the critic round, and six
for six again on the logging added 2026-09-12. That matters because two of
them were only added after a critic reverted them and the suite stayed green,
and because one test in the first round was asserting nothing at all.

**Not proved, and it matters:** no ffmpeg exists in the container these fixes
were written in. Every test above pins the argv and the filter graph. **None of
them ran ffmpeg, so none of them prove a pixel or a sample.** Two filter-level
claims in particular rest on ffmpeg's documented semantics and not on a run: that
`loop=loop=F-1:size=1:start=0` holds a single decoded frame for F frames, and
that `apad` with a zero `pad_dur` and no `-t` pads indefinitely. The frame counts,
the levels and the silences have to be measured on the box. That is the
acceptance suite below, and until it passes, this worker is unproven regardless
of how green the unit tests are.

## Reading the log

The worker writes one line per request and two per job to stdout, which systemd
hands to journald. It did not do this until 2026-09-12, and the absence is the
direct reason a single 401 took four rounds and a packet capture to diagnose.

```bash
journalctl -u tsws-render-worker -f            # live
journalctl -u tsws-render-worker --since -1h   # the last hour
```

An accepted job looks like this, and the `id` joins the three lines:

```
2026-09-12T03:29:09.677Z method=POST path=/jobs status=202 ms=2.1 type=exists id=0b93daa1
2026-09-12T03:29:09.679Z job=start id=0b93daa1 type=exists queued_ms=2
2026-09-12T03:29:09.681Z job=end id=0b93daa1 type=exists status=done seconds=0.001
```

**A 401 says why.** This is the field worth knowing about, because every one of
these used to look identical from the outside:

| `auth=` | what to fix |
|---|---|
| `no-authorization-header` | the credential is not attached to the node |
| `no-authorization-header-but-saw-x-api-key` | the header Name field is wrong. It must be `Authorization` |
| `authorization-header-has-no-scheme-just-a-value` | the Value field is missing the `Bearer ` prefix |
| `scheme-is-not-capitalised-Bearer` | `bearer` for `Bearer` |
| `more-than-one-space-after-Bearer` | two spaces where there should be one |
| `token-is-65-chars-expected-64` | **a stray character in the token.** This is what a wrapped terminal copy looks like: the line break became a space |
| `token-is-the-right-length-but-does-not-match` | genuinely the wrong token, or the service is running an older one than the env file holds |

The reason string never contains the token or any slice of it, and neither does
any other line. That is asserted by a test which also checks every eight
character window of the real token against every reason the function can
produce, and it caught the first draft echoing 24 characters of a bare
credential back into the log.

The token length pair is deliberate and is not a disclosure: anyone who can read
this process's journal can already read `WORKER_TOKEN` out of the unit's
`EnvironmentFile`.

Set `LOG_REQUESTS=0` in the environment file to silence all of it.

## Deploying it

**This section is for a new host only. On N8N-HOST, where the worker already
runs, follow "Upgrading the live box" below instead.** The steps here generate
a new token and overwrite `/etc/tsws-render-worker.env`, which cuts n8n's
credential off, and copy the committed unit file, which binds to loopback where
the n8n container cannot reach the worker.

Node 18 or newer, and ffmpeg with libx264 and libx265. A TLS terminator only if
the worker faces the internet, which on the deployment above it does not.

**IF n8n RUNS IN DOCKER, LOOPBACK WILL NOT WORK, AND THE FAILURE LOOKS LIKE A
WIRING MISTAKE.** A container's `127.0.0.1` is the container, not the host. Point
n8n at `http://127.0.0.1:8080` while the worker sits on the host's loopback and
every call returns connection refused, which reads as a bad URL or a bad token
rather than as a network namespace boundary. This cost nothing here only because
it was caught before the install rather than after.

Find the right address before installing:

```bash
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'
docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}  gateway={{$v.Gateway}}{{"\n"}}{{end}}' $(docker ps --filter name=n8n -q)
```

If n8n uses `network_mode: host` it shares the host stack and loopback is fine.
Otherwise bind the worker to the gateway of the network n8n's **application**
container sits on, and set the same address in TSWS 00. On N8N-HOST that was
`BRIDGE-GATEWAY` (`n8n_backend`).

Do not bind to a task runner or sandbox network's gateway even though it would
work. Binding only to the application network means sandboxed code routes to a
different gateway, finds nothing listening, and is refused. That isolation is
free and worth keeping.

A docker bridge address is RFC1918 and is not routable from the internet, so this
keeps the property that matters: the token never crosses a network.

**Node.** A host running n8n in docker will usually have no Node at all, because
n8n never needed it there. Ubuntu 24.04's own `nodejs` package is 18.19.1, which
satisfies this worker, so no third party repository is required. Skip the `npm`
package; the worker has zero dependencies and the five suites run directly with
`node jobs.test.js`, `node acx_node.test.js`, `node server.test.js`,
`node tsws-repair.test.js` and `node negative-control.js`.

The autonomy driver recorded the intended home as EDITFORGE-HOST, the EditForge box,
or its own host. It went to N8N-HOST instead, the n8n box, so that the call
never leaves the machine.

```bash
# 1. user, directories, code
sudo useradd --system --home /opt/tsws-render-worker --shell /usr/sbin/nologin tsws
sudo mkdir -p /opt/tsws-render-worker /data/tsws
sudo chown -R tsws:tsws /data/tsws

# copy jobs.js server.js package.json tsws-repair.js acx_node.js words.py into /opt/tsws-render-worker
sudo chown -R root:root /opt/tsws-render-worker

# 2. ffmpeg
sudo apt-get update && sudo apt-get install -y ffmpeg
ffmpeg -hide_banner -encoders | grep -E 'libx264|libx265'   # both must appear

# 3. the token. Generate it here, and nowhere else.
TOKEN=$(openssl rand -hex 32)
printf 'WORKER_TOKEN=%s\nWORK_ROOT=/data/tsws\n' "$TOKEN" \
  | sudo tee /etc/tsws-render-worker.env >/dev/null
sudo chmod 600 /etc/tsws-render-worker.env
echo "$TOKEN"     # paste into the n8n credential, then clear your scrollback

# 4. service
sudo cp tsws-render-worker.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now tsws-render-worker
systemctl status tsws-render-worker --no-pager

# 5. it must refuse to start without a token. Confirm that rather than assume it.
sudo env WORKER_TOKEN= node /opt/tsws-render-worker/server.js ; echo "exit $?"
#    expect: refusal text and exit 2
```

The unit binds to `127.0.0.1:8080` on purpose. Put TLS in front of it; the
worker speaks plain HTTP and a bearer token on a bare IP over plain HTTP is a
token on the wire in the clear. With Caddy:

```
render.editforge.online {
    reverse_proxy 127.0.0.1:8080
}
```

Point an A record for that name at the host first, or the certificate will not
issue.

This block is for a new host. `render.editforge.online` has no A, AAAA or
CNAME record (NXDOMAIN from dns.google on 2026-10-31), so the name resolves
nowhere; no host was read for whether it carries this block. Do not
put it on N8N-HOST: `127.0.0.1:8080` there is the Temporal UI, so this block
would publish the Temporal UI under the worker's name.

```bash
curl -s https://render.editforge.online/health | python3 -m json.tool
```

`/health` is the only unauthenticated route and it returns the job names and
nothing else. Operational detail (`work_root`, queue depth, concurrency) is on
`/status`, behind the token, because the first version put a filesystem path and
a load signal in front of anyone who could reach the TLS terminator.

`job_count` must read **24** from the 2026-10-31 build onward, which carries
`tsws_repair` and the two ACX Node jobs; 22 on the live box from 2026-10-17 to
the next upgrade (`tsws_repair` without the ACX jobs), 23 in this repository
only from 2026-10-28 to 2026-10-31, 21 from the 2026-10-15 Voice Lab build, 19
from the 2026-09-15 build, 18 before it.
Fewer means an older `jobs.js` is loaded, and the sticky note's warning applies:
a still plate renders as one frame, not a held one.

## The acceptance suite. Run these; do not skip to the episode.

`/health` proving reachable is not the same as proving correct. These are the
four checks that ffmpeg has to answer, in order. `$T` is the token.

```bash
B=https://render.editforge.online
A="Authorization: Bearer $T"
sub(){ curl -s -o /dev/stderr -w '%{http_code}' -X POST "$B/jobs" -H "$A" \
       -H 'content-type: application/json' -d "$1"; }
poll(){ curl -s "$B/jobs/$1" -H "$A" | python3 -m json.tool; }
```

**1. Reachability.** The smoke test from the sticky note. Expect `202` on submit
and `"ok": true` on the poll. This proves the URL resolved, the token is right
and the box answered. Nothing more.

```bash
sub '{"type":"exists","params":{"path":"."}}'
```

**2. F1, the one that mattered.** Put one 4K JPEG at `/data/tsws/t/a.jpg` and a
second at `t/b.jpg`, then assemble six seconds of each at 24fps and count frames.

```bash
sub '{"type":"assemble_cut","params":{"shots":[
  {"path":"t/a.jpg","in":0,"out":6},{"path":"t/b.jpg","in":0,"out":6}],
  "output":"t/cut.mp4","crossfade":1.0,"width":1920,"height":1080,"fps":24}}'
# then, on the box:
ffprobe -v error -count_frames -select_streams v:0 \
  -show_entries stream=nb_read_frames -of csv=p=0 /data/tsws/t/cut.mp4
```

The job reports `expected_duration` 11.0 and `stills` 2. `11.0 * 24 = 264`.
**Expect 264 frames.** The old code returned 1 frame for the whole thing. Feed it
two stills of different pixel sizes and it also exercises F2; before the fix that
combination produced a 0 byte file.

**3. A1, the defect that would have shipped.** This is the one that cost an
episode. Take a bed of at least 900 seconds, a narration, and one guard.

```bash
sub '{"type":"duck_mix","params":{"narration":"t/nar.wav","bed":"t/bed.wav",
  "output":"t/mix.flac","codec":"flac",
  "guards":[{"start":544,"end":548}],"duration":880.907}}'
```

Then three measurements, not one:

```bash
# a. the gap is silent
ffmpeg -nostdin -hide_banner -ss 545 -t 2 -i /data/tsws/t/mix.flac \
  -af volumedetect -f null - 2>&1 | grep mean_volume      # expect -inf or near

# b. the bed CAME BACK. This is the whole defect.
for t in 600 700 830 870; do
  ffmpeg -nostdin -hide_banner -ss $t -t 10 -i /data/tsws/t/mix.flac \
    -af volumedetect -f null - 2>&1 | grep mean_volume
done
# expect a real level at every one. Any -inf here means the bed is dead and
# the fix did not take. The old chain read -inf at 700, 830 and 870.

# c. nothing is silent for 3 seconds anywhere
sub '{"type":"silence_detect","params":{"input":"t/mix.flac","min_duration":3}}'
# expect count 1: the 4 second guard, and nothing else.
```

`codec` matters and was missing until 2026-09-11. `duck_mix` defaults to
`pcm_s24le`, and PCM does not mux into a FLAC container, so an earlier version of
this runbook sent the operator into a muxer error on the one check that decides
the show. Pass `"codec":"flac"` with a `.flac` output, or write `.wav` and leave
the default.

**4. A2, the length pin.**

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 /data/tsws/t/mix.flac
```

Expect `880.907000`, not `880.849`. Confirm the poll result also says
`"pinned": true`; if it says false, the caller did not send `duration` and the
58 ms defect is still live on that call.

**What these four do NOT cover, so you know what is still untested on the box:**
F2 is only exercised incidentally (step 2 suggests two stills of different pixel
sizes but asserts nothing about it); `scan_drop` (F4) is not exercised at all,
and one `{"type":"scan_drop","params":{"drop_dir":"drop"}}` against a real drop
tree closes it; `-nostdin` (A3) is not exercised and only matters if you run a
render from an interactive shell. Add those two if the lane will lean on them.

Only after all four pass is it worth wiring the real lane.

## The TQO presenter build (added 2026-09-15)

Two additions, both for the TQO and NCO Forge presenter lane, where a HeyGen
avatar render of Tee is the base track and our own worker does the composite.

**`GET /files/<path>`** is the return path. Every job writes inside `WORK_ROOT`
and until this route nothing could read a binary result back out. Token gated
like every route but `/health`, confined by the same `safePath` the jobs use
(symlinks included), regular files only, no directory listing, no Range. n8n
reads it with an HTTP Request node set to respond as a file, then hands the
binary to the existing Upload Video node. Percent-encoded paths are decoded
before they are confined, so a filename with a space survives n8n's URL field.

**`presenter_composite`** takes the avatar MP4 as the base, lays Pexels
cutaways over it full frame inside planned episode-timeline windows (a clip
shorter than its window holds its last frame), burns an SRT in with libass,
and ducks a looped music bed under the avatar's own audio with the duck_mix
sidechain chain. One ffmpeg pass. Windows must be disjoint and inside the
planned duration; the captions path and style are refused rather than escaped
when they carry a character the filter string cannot take verbatim.

Measured in the container on 2026-09-15 with imageio's static ffmpeg 7.0.2,
on synthetic media (a 12 s testsrc avatar with a pulsed 440 Hz tone, a 3 s red
clip over a 5 s window, a 6 s blue clip, a 4 s 220 Hz bed, one caption):

| check | result |
|---|---|
| pinned duration | 12.000 s on both renders |
| frame at 1.0 s and 7.5 s | testsrc, the base passes through outside the windows |
| frame at 5.0 s | red, held two seconds past the end of the 3 s clip |
| frame at 6.9 s | red fading out on alpha |
| frame at 9.0 s | blue, a 1280x720 clip normalised to the 640x360 canvas |
| caption | burned in on every sampled frame inside its cue |
| bed in a speech gap | -53.3 dBFS RMS with the bed, silence without it |
| bed under speech, 220 Hz band | about 7 dB below the gap level: ducked |
| bed past its own 4 s length | still present at 9.2 s: the loop works |
| narration level | 2.6 dB under the input, which is amix normalising 1 + 0.35 |

That last row is a property, not a defect, and duck_mix carries the same one.
Set `bed_gain` knowing the voice comes down by 20 log10(1 / (1 + bed_gain)).

Not measured: the same render on the box's own ffmpeg, a real HeyGen file, a
real Pexels clip, and libass with the fonts the box actually has. Run the
synthetic case above on the box before the first episode.

**The stacked layout** (`layout: stacked`, portrait canvas only) is the Anchor
Desk Short from the flagship canon: the payload zone on top, the presenter
chest up in the bottom zone, split at 1250 of 1920 and scaled with the canvas.
Three states alternate, as the canon asks: split (the default), full-frame
head for each `emphasis: [{start, end}]` window, and full-frame payload for a
cutaway carrying `full: true`; a cutaway without it sits in the payload zone.
`plate_color` paints the plate behind the zones (`#0A1628` by default). The
caption sits on the seam between the zones at `MarginV=92` in libass script
units, which Tee ruled on 2026-09-15 after the first cut at 45 put the line
across the presenter's chest. Measured the same day, same synthetic media on a
1080x1920 canvas, 12 s, a red clip in the zone over 2 to 5 s, an emphasis
window 6 to 7.5 s, a blue full cutaway 8 to 11 s, one caption over 0.5 to 3 s:

| check | result |
|---|---|
| frame at 1.0 s | plate above, presenter in the bottom zone from y 1250, caption on the seam at roughly y 1235 to 1305, above the face |
| frame at 3.5 s | red clip inside the payload zone, presenter untouched below the split |
| frame at 6.8 s | presenter full frame on the emphasis window |
| frame at 9.5 s | blue clip full frame on `full: true` |
| pinned duration | 12.000 s |

Refused rather than defaulted: `cutaways` or `emphasis` present and not an
array, `full` as anything but a boolean, `emphasis` on the full layout, and a
window past the planned duration when one is given.

## Voice Lab (added 2026-10-15)

This is the TQO ship lane that does not need an avatar.

1. Tee records the approved script on his iPhone.
2. A speech-to-text pass times every word.
3. `align_script` keeps the readings that say a line **verbatim** and marks the
   rest.
4. The voice clone re-reads ONLY the marked lines, from the script, word for
   word.
5. `take_patch` splices the real take and the clone audio into one base track.
6. `presenter_composite` lays a cutaway over every clone window. Through
   `must_cover` it refuses to render if one is bare, and it puts an opaque
   plate under each window so that an empty cutaway shows black, never his face.

| job | kind | what it returns |
|---|---|---|
| `align_script` | native | `verdict` clean, patch or rerecord; the edl; a line by line report |
| `take_patch` | native, one ffmpeg per segment, then a stream copy join | base video, optional narration wav, `patch_windows` on the new timeline |
| `presenter_composite` `must_cover` | param | refusal at submit when a window is not inside one opaque cutaway, plus a black plate under it |
| `probe` | ffprobe | now also `pix_fmt`, `color_transfer` and `hdr`, read from the first video stream |

Things to know before wiring it:

* **A take is kept only when it says the line exactly.** Case and punctuation
  are folded away; nothing else is. A filler inside a line, a changed number or
  a dropped word sends the line to the clone. The first cut kept anything that
  scored 0.9 on a word overlap ratio, and a fresh critic got "forty percent"
  kept for a script that says thirty. The old `threshold` parameter is now
  refused rather than ignored.
* **A reading starts and ends on a whole spoken word.** "this is our year" no
  longer matches the front half of a spoken "year-end".
* **Only a fixed set of punctuation is dropped.** That set is . , ; : ! ?
  quotes, brackets, the em dash and the ellipsis. Case, accents and curly
  quotes fold. Every other character becomes a token that matches only itself:
  % $ euro yen the plus-minus sign, the times sign, kanji, emoji and the rest.
  So "rose 30%" read as "rose 30%" is kept, while "rose 30" never matches a
  spoken "rose 30%".
  * A minus or an en dash before a digit is a token, and a hyphen minus equals
    a true minus.
  * A comma drops only as a thousands separator: one to three digits, then
    groups of exactly three. "1,000" is "1000". Anywhere else a comma before a
    digit is a token, so a decimal "1,5" is not "15" and "3,4" is not "34".
  * A point before a digit is a token, so "3.5" never equals "3 5", ".5" is
    not "5" and "$.99" is not "$99".
  * A character that folds to a digit without being one, such as a superscript,
    a fraction, or a circled or full width digit, is a token of its own. So
    "10²" is not "102".

  The first cut dropped symbols, the second blocked a list of them, and the
  third critic walked "¥500" and whole Japanese words through that list. The
  fourth had all five of the number cases above kept as clean readings of a
  different number.
* **The work is bounded by what the text folds to, not by its length.** One
  ligature character folds to eighteen, and a fourth critic held the worker's
  loop 20.2 s and grew it to 3.3 GiB with a transcript of them sent through
  the worker's own `fs_ops`. A transcript word is now refused over 64
  characters or over 16 tokens, the transcript over 100,000 tokens, and the
  script over 100,000 tokens. The same file is refused in 155 ms at 71 MiB.
* **A kept word is never trimmed.** When the vendor's timestamps overlap, the
  edge stops at the word instead of the midpoint, which cut 50 ms off "done".
* **Digits and number words do not match each other.** Whether ElevenLabs
  speech to text writes a spoken number as digits or as words is unverified
  here. Either way the safe direction holds: a mismatch sends the line to the
  clone.
* **Readings are chosen by a dynamic program.** It keeps the most script words
  in order, and on a tie the later reading wins. A critic checked it against an
  exhaustive search on 60,000 random cases: 0 mismatches.
* **Over 30 percent of lines patched, or more than 64 patches, is a
  re-record.** `align_script` returns `verdict: rerecord` with `edl: null`, and
  `take_patch` refuses a null edl. 64 is the most cutaways one
  `presenter_composite` lays.
* **`take_patch` has no default for `hdr`.** An iPhone 15 Pro records HLG by
  default. Call `probe` on the take and pass `tonemap` when it reports
  `hdr: true`. A file tagged with an HLG transfer but no primaries or matrix is
  refused by zscale ("no path between colorspaces"), loudly; a real iPhone file
  carries all three tags.
* **`take_patch` reads its own inputs before it renders.**
  * It probes the take's picture and refuses a span that ends past the last
    frame. An iPhone file's sound can outlast its picture, and a critic
    rendered a clone line into nothing that way, with the job returning ok.
  * It probes every clone file and refuses one longer than its stated
    `duration`, so a line is never cut short.
  * `take_duration` is still required, and spans must run in time order without
    overlapping.
* **It checks its own output against the plan, and removes it on a mismatch.**
  The check covers the frame count and the length of the sound and of the
  narration.
* **It deletes the previous run's output and narration first**, so a failed
  run never leaves stale files that look current.
* **An output that is also an input is refused.** That covers the take, a
  clone file, and the narration landing on the output or inside its working
  directory.
* **When the server abandons the job at `JOB_TIMEOUT`, it calls the job's
  `abort()`**, which kills the ffmpeg that job started.
* **Outputs must be `.mp4` or `.mov`, and the take must record the picture's
  own length.** An mkv records neither the frame count nor a per-stream
  length, so both are refused rather than half checked.
* **Collisions are judged by real path**, so a symlinked take cannot be
  overwritten through its link.
* **A failed join removes its partial output.**
* **Stacked emphasis must stay one output frame clear of a covered window.**
* **The clone windows ride inside the base track's own metadata.** They sit
  in the container's `comment` tag as `voicelab-must-cover:` plus JSON, and the
  job reads the tag back before it reports success. `presenter_composite` reads
  it with ffprobe at submit and enforces those windows whether or not the
  caller sends `must_cover`.
  * A window sent as `must_cover` and also carried in the file counts once.
  * A base track whose tags cannot be read is refused.
  * The first fix used a sidecar file instead, and a third critic copied the
    base with `fs_ops` and rendered 46 frames of face under the clone. A copy
    or a symlink keeps the tag.
  * The base must be `.mp4`, `.mov`, `.m4v`, `.mkv` or `.webm`, and must read
    as one of those containers. A `.ts` drops the tag, and an mkv keeps it
    under the key `COMMENT`, which the first reader never looked for; both
    composited 37 face frames under the clone in the fourth critic's run. The
    tag is now read under any key case.
  * The tag records the length it was written for, and a base whose picture is
    more than 1.5 frames off that length is refused. A job that re-times the
    file copies the tag unchanged, and a critic cut one second from a base
    and got 30 face frames from the stale windows.
  * A window that rounds up past the end of the file is clamped to it, so a
    patched last line is not refused against the duration pin.
  * The finished master does not carry the tag. Tee ruled on 2026-10-16 that
    the list of where his clone speaks does not travel inside the delivered
    file. It stays in the job result.
  * Stripping the tag on purpose, with `-map_metadata -1` or an outside tool,
    still removes the protection: a file with no tag reads as a file that never
    had one. Only send `take_patch` output, or a copy of it, as the base.
* **`must_cover` asks for each window to sit inside one scheduled cutaway.**
  Under every window it lays a black plate that reaches one output frame past
  each edge. A fade, an empty cutaway or a window edge between two frames
  therefore shows black, never the face, and a first or last line can be
  patched at the default fade.
* **Pass `width` and `height`, the presenter canvas.** Segments are then cut at
  that size, scaled BEFORE the tonemap so the float maths runs on a quarter of
  the pixels. Carrying 4K through cost 214 s for 24.5 s of picture at preset
  ultrafast.
* **`fps` must be 24, 25, 30, 48, 50 or 60.** Those rates divide 48 kHz, so
  every segment's sound is a whole number of samples. This line said "a whole
  number" until a critic pointed out that 29 is one and does not divide.
* **A portrait take on a landscape canvas is pillarboxed.** The result reports
  it as `letterboxed`, with the source and canvas sizes after the iPhone's
  rotation flag is applied.
* **Lay cutaways at least one frame wider than the window on each side.** A
  hard cut laid exactly on `patch_windows` starts on the frame grid's floor,
  so two or three frames at its edges show the black plate. That is safe, but
  it is a visible flash.
* **The held frame under a patch sits two frames inside the take's end.** With
  the picture on the audio's clock, that is usually the last frame shown, so
  the still can begin one frame before the window.
* **Each join is a 20 ms fade out and a 20 ms fade in**, a short dip and not
  a crossfade.

### Memory, measured, and why take_patch is native

The first `take_patch` made every edl item its own seeked input in one ffmpeg
run. On a 40 s 4K HEVC HLG take, 64 items (96 inputs) **peaked at 13.6 GiB
and died**, and this box has 7.8 GiB. Each input is a live decoder.

The job now runs one ffmpeg per item, one or two inputs each, and joins the
segments with the concat demuxer as a stream copy, so the picture is encoded
once. The same 64 items peaked at **1,068 MiB** in the session container, and the
output measured 736 frames against 736 planned. A critic's run in another
container saw a single 4K HLG segment peak at 1,637 MiB, so the figure depends
on the host. Either way it is bounded per segment, not summed over the edl. 256 items peaked at **1,427 MiB**, measured 2,944
frames against 2,944 planned, and took 890 s at preset ultrafast with 4K carried
through. The cap is now 400 items.

### Acceptance, real ffmpeg

`npm test` runs no ffmpeg and neither does render-worker-ci.yml. This does:

```bash
node voice-lab-acceptance.js            # exits non-zero on any failure
```

It builds a synthetic take whose every frame carries its own index in its
pixels, a 440 Hz "voice", and a 1000 Hz mp3 "clone". Then it measures:

* every output frame against the source frame it should be;
* picture against sound length, to the frame;
* where the held frames land;
* that the clone is heard only inside its window, more than 30 dB clear;
* that no join clicks;
* that `must_cover` refuses a cutaway whose fade would show the face;
* that no take pixel shows in the window with a real cutaway, or with an
  empty one;
* that an HLG take tonemaps to BT.709 8 bit, at full size and at the presenter
  canvas.

Measured in the session container on 2026-10-16 with ffmpeg 6.1.1:
**19 passed, exit 0**. Round four added three checks, each of which fails
against the round three commit: the finished master carries no clone windows,
a base re-timed after `take_patch` is refused, and an mkv copy keeps its
windows while a `.ts` copy is refused. Round three added one: a copy and a
symlink of the base track still carry the windows. The additions after the
second critic check five things:

* the in-file windows alone enforce the window;
* a fade over the clone shows the plate;
* a hard cut on a window edge that rounds up shows no face;
* a span past the last frame of picture is refused;
* a clone file longer than its stated duration is refused.

The hard cut check fails against a copy without the plate widening ("frames 173
of the window 173..241 show the held face").

Its first run found a defect that every builder test missed. Video segments
rounded to the frame while audio did not, so each splice drifted 13 ms. The
same script against a copy with frame snapping removed fails at frame 76 and
exits 1. That is its negative control, run by hand, not wired.

The critic's A/V measurement found the picture up to a frame ahead of the
voice after a seek: +28.4 ms against a -4.0 ms source. It now lands within half
a frame: -5.0, +9.4 and -10.6 ms at 30 fps.

## Wiring TSWS 00

Two nodes carry the URL, hardcoded, because `$vars` is a paid tier feature on
the Cloud plan and `$env` is denied inside Cloud nodes. That is why an earlier
version resolved to `undefined/jobs`.

In `TSWS 00 - Render Job`, VPS id `CX07qa6O1hTSXlpj`, Cloud id `o4ctniOsIq2VSfgm`:

1. **Submit Job** and **Poll Job**: replace `RENDER-WORKER-URL-HERE` with the
   host. No trailing slash.
2. Set the value on the attached Header Auth credential by hand: name
   `Authorization`, value `Bearer <token>`. The word and the single space are
   required; the server strips exactly that before comparing.
3. **Publish after editing.** Draft edits do not affect a scheduled run.

The VPS credential and error workflow ids were repointed on 2026-09-11. The bulk
import had carried Cloud ids into both, and neither resolved on the VPS:

```
credentials.httpHeaderAuth.id   b9FYEfGUlMiYJCCU  ->  WpZNTg9qduOFC5NM
settings.errorWorkflow          rqYmaQh91iCce8DJ  ->  GbeNilHQzjmoWDz3
```

**Give the worker its own key.** `Header Auth account 10` is shared, and the
autonomy driver already calls for splitting it. A worker token and a pipeline
token that are the same string means rotating either one takes down both.

## Security posture, after the 2026-09-11 critic pass

Six things an adversarial pass changed. Named because "hardened" is not a
standard and the specific holes are the useful record:

- **A single authenticated request used to wedge the whole process.** The native
  job path had no timeout and its jobs used synchronous fs, so `read_text`
  against a FIFO blocked the event loop forever. `/health` went dark, the process
  never exited, and `Restart=on-failure` therefore never fired. `read_text` now
  refuses anything that is not a regular file and reads asynchronously,
  `render_mark_full` no longer encodes synchronously, and the native path has a
  timeout backstop.
- **`safePath` was lexical.** `path.resolve` does not follow symlinks, so one
  symlink inside the work root was a full read and write escape; a `media ->
  /etc` link served `/etc/passwd`. It now resolves the real path of the deepest
  existing ancestor before the prefix check.
- **`http_download` checked the scheme and not the destination.** It would fetch
  from `127.0.0.1`, `169.254.169.254` and any RFC1918 address, and `read_text`
  handed the result straight back. Private, loopback, link local, CGNAT and
  multicast destinations are now refused, on redirects too. **Name based SSRF
  through DNS is not closed by this** and cannot be closed at this layer.
- **`conform_grain` emitted `apad` with no ending to pad to**, which with no `-t`
  and no `-shortest` is a render that never ends. Same defect this file had
  already fixed in `duck_mix`, two jobs over.
- **The queue was unbounded.** It now refuses at 64 with a `503` and a
  `Retry-After`.
- **There was no SIGTERM handler**, so the unit file's `TimeoutStopSec` comment
  was describing a drain that did not exist. It drains now.

Still open by design: the token is a single shared secret with no rotation
mechanism, there are no per-job resource ceilings (`MemoryMax`, `CPUQuota`,
`TasksMax` are not set in the unit), and there is no disk quota on the work root,
so `render_mark_full` will accept a request for a great many 4K frames.

## tsws_repair (on the box 2026-10-17, in the repository 2026-10-31)

`tsws-repair.js` is a DRAFT bridge from the worker to the pinned local TSWS
repair package: three workflows (`TSWS_SHOT_COMPOSER`, `TSWS_SHOT_CLEANUP`,
`TSWS_SCENE_BUILDER`), each a fixed script, method and flag in the package. It
takes a repair envelope and refuses one that asks for generation, names a
script or command other than the fixed one, or gives an input role that is not
a plain relative name. The interpreter, package, cache and origin come from the
operator's environment and never from the caller. It reads inputs only from a
pre-staged cache laid out as `CACHE/DRIVE_ID/SHA256`, refuses a cache entry that
is a symlink, and checks every hash and declared byte count; it fetches
nothing. In the staged job file it checks less: only string values under the
keys `path`, `clean_plate` and `protected_mask`, and string entries of
`actor_mattes`, must name a declared input, and those are rewritten to the
staged copies. Any other key, an array or object under `path`, and an array or
object entry of `actor_mattes` reach the Python package unchecked, absolute
paths and URLs included. That is the live code as
carried; tightening it would break byte identity with the box and is a ruling
of its own. The exposure is to holders of the worker token, and the package
runs as `tsws` under the unit's `ProtectSystem=strict`. Its receipt is always `DRAFT` with
`human_review_required: true` and `complete_shot_accepted: false`.

**A repair envelope is claimed durably at submit, before it is queued.** The
server calls the job's `claim(id)`, which creates `WORK_ROOT/repair/<envelope>`
exclusively and fsyncs a `CLAIM.json` reading `retry: REFUSED`. A second submit
of the same envelope is a 409, never a rerun, and a failed claim is never
removed. This is why `server.js` now passes a 409 or a 503 from a build or a
claim through to the caller instead of turning it into a 500. The job alone
does nothing without the server's hook: `native()` refuses to run unclaimed.

It needs the operator's configuration, and answers 503
`BLOCKED_CONFIGURATION` at submit when any of it is missing. On N8N-HOST it is a
drop-in, `/etc/systemd/system/tsws-render-worker.service.d/repair-v01.conf`,
read 2026-10-31:

```
[Service]
Environment=TSWS_REPAIR_PACKAGE_ROOT=/opt/tsws-repair-package-v01
Environment=TSWS_REPAIR_PYTHON=/opt/tsws-repair-runtime-v01/venv/bin/python
Environment=TSWS_REPAIR_PATH=/opt/tsws-repair-runtime-v01/blender-4.5.2-linux-x64:/usr/bin:/bin
Environment=TSWS_REPAIR_CACHE_ROOT=/data/tsws/repair-cache-v01
Environment=TSWS_REPAIR_PUBLIC_ORIGIN=http://BRIDGE-GATEWAY:8080
```

`tsws-repair.test.js` pins, in 22 tests, the submit refusals, the
configuration and origin checks, the claim and its 409, a full run through a
stand-in package (Node as the interpreter, the package's own script names) that
is handed the staged input's path, a cache entry that is a symlink, a wrong
hash, a cache symlink to another file inside the cache, a wrong byte count, an input never staged, a bad exit code, a symlink
left in the output, `abort()` killing the package's process group, the 16 MiB
log cap, and through the real server the 409, the 503 for missing
configuration, and a full queue answering 503 before the claim so the envelope
is not burned. Each of sixteen deliberate breaks to the job, the hook or the
`jobs.js` entry turns it red; eight of them were found surviving earlier
versions of the suite by a critic and a verifier. It covers the bridge as a stand-in package
sees it and nothing about the real Python package, Blender or the box's
runtime, and it does not test the unchecked job keys described above.

Who deployed it on 2026-10-17 is not recorded anywhere this repository can
read. The box shows when it was used: `/data/tsws/repair` holds three claimed
envelopes, `vps-live-cleanup-20261017`, `vps-live-scene-20261017` and
`private-drive-cleanup-20261017-v01`, and the folder was last modified at
2026-10-17T11:19:50Z (read 2026-10-31). Each claim creates an entry there, so
no `tsws_repair` submit has been claimed since. Whether an n8n workflow is wired
to call it is not read.

## Upgrading the live box

N8N-HOST, not the EditForge box. The hostnames are in the private DEVON log;
the EditForge box has no `tsws` user, no unit and no worker. On 2026-10-31 two
of the ACX steps below were pasted on the EditForge box by mistake, because a
session named the wrong host from memory; check the prompt before pasting.

The first install under "Deploying it" is for a new host. On the live box:

1. Read `GET /status` with the token from inside the box (never print it) and
   go on only when nothing is running or queued. A restart drops the job table,
   and every poller loses its job ids.
2. Stage a copy of `deploy/render-worker` from the merge commit in `/tmp` on the
   box: the `.js` files, `words.py`, `package.json` and the `reference/` folder
   the negative control reads. There is no npm on the box, so run the five
   suites one by one with the box's own `/usr/bin/node` and ffmpeg, checking
   each exit code: `jobs.test.js`, `acx_node.test.js`, `server.test.js`,
   `tsws-repair.test.js` and `negative-control.js`. Nothing in `/opt` is
   touched until all five exit 0.
3. Copy `jobs.js`, `server.js`, `package.json`, `tsws-repair.js`,
   `acx_node.js` and `words.py` into `/opt/tsws-render-worker`, keeping each old
   file as `.bak-<date>`. Leaving out `acx_node.js` stops the service, because
   `jobs.js` requires it at load and the unit gives up after five failed starts.
   `tsws-repair.js` is loaded only when a repair job is built, so leaving it out
   on a host that lacks it keeps `tsws_repair` listed in `/health` while every
   submit answers 500; on the live box the byte identical file is already in
   place. Only the sha256 read back in step 6 catches a missing file.
4. **Never copy `tsws-render-worker.service` over the live unit.** The live one
   carries the two deviations above (the bridge bind and `MemoryMax=5G`) and the
   repair drop-in sits beside it. Copying the committed unit rebinds the worker
   to loopback, where the n8n container cannot reach it, and on N8N-HOST
   loopback port 8080 is already held by the Temporal UI (read 2026-10-31).
   What the worker does when it finds the port taken there has not been
   measured.
5. Make the ACX runtime once, from "The ACX Node build" below: the whisper venv,
   the three Chakra Petch faces under the work root, and `/data/tsws/hf` owned by
   `tsws`. Add `WHISPER_PYTHON` and `HF_HOME` to `/etc/tsws-render-worker.env` by
   appending two lines; that file holds `WORKER_TOKEN`, so never rewrite it with
   a redirect and never print it. Without this step the service starts and
   `/health` reads 24, but `word_timings` fails at run time naming the variable
   and `acx_node_assemble` refuses at submit for want of the faces.
6. Read `GET /status` again immediately before the restart, and restart only
   when it is still idle. Then read `/health` on the bridge address, never on
   `127.0.0.1`, which on this box is the Temporal UI: 24, with
   `tsws_repair`, `word_timings` and `acx_node_assemble` among the names. 24
   proves the job table loaded, not that the ACX jobs can run; their proof is the
   Node 01 case below. Read the live files' sha256 back against the merge
   commit's.

## The ACX Node build (added 2026-10-28, ruled R22)

Two native jobs in `acx_node.js`, wired into the table by `jobs.js`, for the
ACX micro drama lane: a Node is 60 to 90 seconds at 9:16, five accepted stills
and the owned narration lines, assembled with picture following voice. Tee
ruled on 2026-10-28 (R22) that this is where the Node picture and cut stages
live, after EditForge's free lanes were measured and found to have no door for
the stills and the lines. The job is the Node 01 Proof 0 pipeline, stage for
stage, as `build.py` ran it in the cloud sandbox that day; the numbers in the
acceptance table below are that same Node 01 run through this worker on
loopback in the sandbox, not on the box.

**`word_timings`** runs one python process over the line files and writes word
timings keyed by each file's stem. It needs `WHISPER_PYTHON` in the unit's
environment, a python that carries `faster-whisper`. Unset, the JOB fails with
a sentence naming the variable; the server starts and the health route is
unchanged, because the job table must not depend on which box this runs on.
The model (`base.en` by default, `tiny.en` and `small.en` allowed) downloads
under `HF_HOME` on the first run, about 145 MB for base.en, so that first run
needs outbound HTTPS to Hugging Face and the ones after it do not.

Two things go into that python beside faster-whisper 1.1.1. PyAV stays below
14, because 1.1.1 breaks on PyAV 19 (measured 2026-10-28). And `requests` is
installed by name: faster-whisper 1.1.1 imports it in `faster_whisper/utils.py`
without declaring it, and huggingface_hub stopped bringing it at 1.0. Read from
each wheel's metadata on 2026-10-31, 0.36.2 requires `requests`, 1.0.0 requires
httpx and 2.0.0 and 2.4.0 require httpx2. So on a fresh venv today the install
line without it succeeds and the first import dies on `No module named
'requests'`, which is what the box did on 2026-10-31 with the step as first
written. A clean venv reproduced it the same day and adding `requests` cleared
it: faster-whisper 1.1.1, av 13.1.0 and huggingface_hub 2.4.0 imported, the
base.en model downloaded under `HF_HOME`, and `words.py` wrote word timings for
two Node 01 lines. An independent verifier then reproduced the failure and the
fix again from its own checkout.

These steps run on N8N-HOST, where the worker runs, as root. Its Python is
3.12.3 with `ensurepip`, so the venv needs no extra package (read 2026-10-31).

```bash
# once, on N8N-HOST, as root: a venv the service user can read
python3 -m venv /opt/tsws-render-worker/whisper
/opt/tsws-render-worker/whisper/bin/pip install faster-whisper==1.1.1 "av<14" requests
# then append WHISPER_PYTHON and HF_HOME to /etc/tsws-render-worker.env. It
# holds WORKER_TOKEN: never rewrite it with a single > redirect and never print
# it. HF_HOME is the model cache: the unit runs ProtectSystem=strict with
# ReadWritePaths only /data/tsws, and the service user's home under /opt is root
# owned, so the default cache at $HOME/.cache/huggingface is not writable and
# the first word_timings job would die downloading base.en.
# This refuses on a box with no worker. On 2026-10-31 an unguarded version of
# these lines ran on the EditForge box and created the env file there.
F=/etc/tsws-render-worker.env
if [ -f "$F" ] && id tsws >/dev/null 2>&1; then
  grep -q '^WHISPER_PYTHON=' "$F" || echo 'WHISPER_PYTHON=/opt/tsws-render-worker/whisper/bin/python' >> "$F"
  grep -q '^HF_HOME=' "$F" || echo 'HF_HOME=/data/tsws/hf' >> "$F"
  mkdir -p /data/tsws/hf && chown tsws:tsws /data/tsws/hf
  cut -d= -f1 "$F"    # key names only: WORKER_TOKEN WORK_ROOT WHISPER_PYTHON HF_HOME
else
  echo "REFUSED: no $F or no tsws user on $(hostname); this is not the worker's box"
fi
# and the three Chakra Petch faces, OFL, under the work root
mkdir -p /data/tsws/fonts/chakra   # ChakraPetch--400.ttf, --600.ttf, --700.ttf
```

**`acx_node_assemble`** takes the beat manifest and does the rest in one job:

```json
{"type": "acx_node_assemble", "params": {
  "output_dir": "acx/node01/out", "node_id": "ACX_NODE01", "node_label": "NODE 01",
  "title": "THE ORCHESTRATOR", "fonts_dir": "fonts/chakra",
  "images": {"R1": "acx/node01/img/R1.png", "R2": "...", "R3": "...", "R4": "...", "R5": "..."},
  "beats": [{"id": "B01", "image": "R1", "line": "acx/node01/lines/L01.mp3",
             "text": "Third dive. Same query. Two empty returns behind me.", "verdict": false}],
  "pauses": {"cold_open": 2.5, "within_image": 0.9, "image_change": 1.8, "end_hold": 5.0, "extra_after": {"B07": 1.1}},
  "copy_treatment": {"lines": ["B10", "B11"]},
  "words_path": "acx/node01/words.json",
  "voice_slot": "t_veal_2 (ElevenLabs clone, owned; prerecorded lines)"}}
```

What it does, in order, every step an argv and none of them a shell: decodes
each line to 48 kHz PCM, the Copy treatment (a 14 ms double at -7 dB with a
2 dB low shelf and a 2.5 dB high shelf cut, every value overridable) on the
beats named; measures the DECODED files and plans the beats from those, so
picture, captions and mix share one clock; lays the lines on a silent timeline
with the pause rule (a gap inside an image, a longer one at an image change,
an extra one where `extra_after` says, an end hold); raises the whole programme
to `target_lufs` (-14) under a sample peak limiter 0.5 dB below `true_peak`
(-1) so the AAC encode still clears the ceiling, and records what the limiter
removed, measured in float inside the filter chain; one slow push shot (1.00 to
1.05) per run of beats on the same image at double resolution, hard cuts; the
title lockup above the book on the cold open and over the end hold, the canon
disclosure line verbatim on both, wrapped to three 30 px lines above the
caption band; captions burned in from an ASS file in the Chakra Petch SemiBold
face, the sheet's own words with timings aligned from the word timings (a word
the model heard that is not in the sheet is dropped, a word it rendered
differently takes the timing of what replaced it), Critic Red on verdict beats
only, bottom margin 560 px above the platform band; the master at H.264 High
CRF 18, 30 fps, AAC 192k, faststart; a thumbnail, ten frames and a contact
sheet; a canon lint that reads the master back at two frames a second and
fails the job on Critic Red outside a verdict caption; and `build.json` with
runtime, loudness, true peak, the picture to sound delta, the lint, every
stage's seconds, the tool versions, and a sha256 of every file read or written.
The result the poll returns is that record.

Refused at submit rather than escaped or defaulted: a reworded disclosure, a
title or label with a character drawtext cannot take verbatim, a caption line
with a brace or a backslash, a beat on an image not sent, a missing font face,
a 16:9 canvas (the long form is a second render under R19 and does not exist
yet), `words` and `words_path` together, a pause or a treatment on a beat that
does not exist, any path outside the work root, a font file that is not an
sfnt or whose name table does not name the face the filename claims (drawtext
and libass both fall back to another face on that, exit 0 and say nothing, so
it can only be caught here; the three full names are recorded in
`build.json` under `fonts`), and word timings that cover some beats but not
all, because a beat spread evenly beside timed beats would be recorded as
timed.

Two things `build.py` did that this job does not. Its `transcript_check`
stage ran `verify_transcript.py` after the mix, a second faster-whisper pass
over the finished narration compared against the sheet, and reported the
mismatches. That stage is not ported: it needs the whisper python at
assembly time, which this job deliberately does not, so the transcript proof
stays a separate `word_timings` run over the master when it is wanted, and the
Proof 0 report's transcript line is from the sandbox run, not from this job.
And the contact sheet samples ten uniform times across the runtime where
`build.py` used ten hand picked ones, so `contact_sheet.png` is the one output
whose hash differs between the two runs; the table below does not claim it.

Nothing in the job is canon. The palette, the type, the disclosure and the
beats come from the caller; the defaults are the values Tee ruled or Proof 0
used. The caller owns the labels: which beats are verdicts, which lines carry
the Copy treatment, and the mapping of lines to images are the manifest's
claims, and the build record carries them as sent.

Measured 2026-10-28 in the cloud sandbox, ffmpeg 6.1.1, the worker on loopback
with a real token, the Node 01 inputs under the work root (five 1080x1920
masters, eleven owned lines, the three faces, word timings from a local
faster-whisper run), job `1809aa54-06b2-4c2c-8e44-2e54f098b860`:

| check | result |
|---|---|
| job | `done` in 204.276 s wall, 27 stages timed, 66 files hashed |
| master against the Proof 0 master built by `build.py` the same day | sha256 identical, `9e2802af97d8a235...` on both; captions.srt identical |
| runtime from the file | 65.8 s, inside the 60 to 90 window |
| picture against sound | 0.24 frames apart |
| integrated loudness, true peak | -14.14 LUFS, -1.40 dBTP |
| gain and limiter | +5.99 dB applied; the limiter removed 2.19 LU and 7.49 dB of peak, recorded |
| canon lint | 132 frames, Critic Red on 9, all inside the two verdict captions, 0 breaches |
| captions | 31 chunks, sheet text verbatim, timed from the word timings |
| rerun after the critic's fixes, job `3f23c6c0-e1f5-4bb6-8603-8e387f19d8b5` | master sha256 `9e2802af97d8a235...` again, captions.srt identical; `build.json` now carries the three font names, the words source, the bit rate and 70 hashes (the two concat lists, `caption_chunks.json` and `words.json` added); a submit with text files as the three faces refused 400 through the route |

A master identical to the sandbox build is the strongest check available here:
the job reproduces the pipeline Tee's watch will judge, byte for byte.

Read on the box on 2026-10-31 after the deploy, each by an independent verifier
except the one encoder noted, no job run: ffmpeg is `7:6.1.1-3ubuntu5` and
lists every filter and encoder `acx_node.js` calls (drawtext, ass, zoompan,
xstack, loudnorm, alimiter, adelay, amix, lowshelf, highshelf, anullsrc,
libx264, aac, and `pcm_s16le`, which the session read itself after a critic
found no verifier had); the three faces under `/data/tsws/fonts/chakra` hash to
the Proof 0 copies and the deployed `fontFullName` reads all three names; the
venv imports faster-whisper 1.1.1, av 13.1.0 and requests 2.34.2 as `tsws`;
`/data/tsws/hf` is owned and writable by `tsws` and inside the unit's
`ReadWritePaths`; and `tsws` reaches `huggingface.co` (HTTP 200 on the base.en
model's API page). The venv import, the write test and the Hugging Face probe
were run with `runuser`, outside the unit's sandbox, so none of them proves the
import or the model download inside the unit.

Not measured: the same run on the box's own ffmpeg, Node and fonts, and the
first `word_timings` run there with its model download. Run the Node 01 case
above on the box before the first Node goes to Tee's watch from this path, and
compare its build.json against the sandbox record.

## Open

- The acceptance suite above has not been run by anyone. Everything in this
  directory is proved at the argv level and unproven at the sample level.
- `render_mark_full` needs `playwright` plus a chromium binary, neither pinned by
  this repository. It throws a named error when they are missing rather than
  failing obscurely. `npm install playwright && npx playwright install chromium`
  on the box if the mark layer is wanted.
- Three encode generations survive from the original design: `assemble_cut`
  8 bit x264, `composite_mux` 8 bit x264, `conform_grain` 10 bit x265. The
  `psnr` job exists; run it and record a number rather than carrying a worry. If
  it reads badly, `assemble_cut` goes 10 bit in one line.
- The timeline versus source trim question above.
