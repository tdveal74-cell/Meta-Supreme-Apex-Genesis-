# TSWS render worker

The service that every ffmpeg, ffprobe and filesystem operation in the five TSWS
pipelines goes through. n8n has no `executeCommand` on the plan in use, so this
box is the only thing that can touch media.

**It has never run.** Not once, on any host. What follows is what was wrong,
what was fixed, what is proved, and what is still yours to prove.

## Provenance

The engine was recovered from Drive on 2026-09-11.

| | |
|---|---|
| Drive file | `jobs.js`, id `1LhJi3m8vYPTpRmgeYvnDjPYBHZF1H5ts` |
| size | 42,848 bytes, matching Drive's own metadata |
| sha256 | `6ed3109ab220cb986e7c33040e90fda4c103cf8afa5ee48137c7185ca55ecdae` |
| last modified on Drive | 2026-08-07T18:53:12Z |

`jobs.js` here is that file with the fixes below applied. Its inherited comments
are left byte faithful, em dashes included, so the diff against the Drive copy
stays auditable line by line. Every line added by the fixes is dash free. If you
would rather the whole file follow the house rule, say so and it gets one
mechanical pass; it was not done unasked because it would bury the real diff.

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

`assemble_cut` also now returns `stills`, `clips`, `fps`, `normalized_to` and
`expected_duration`, so the assembly can be checked against the manifest rather
than trusted. `expected_duration * fps` should equal the frame count ffprobe
reports on the output.

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

- `node jobs.test.js` pins what the builders emit: 16 tests, all passing.
  Includes a numeric comparison of the new gain envelope against the EP01
  reference expression over 540s to 552s at 0.5 ms steps, worst divergence
  `5.7e-14`.
- `node server.test.js` makes real HTTP requests against a real listening
  server: 16 tests, all passing. It runs
  `{"type":"exists","params":{"path":"."}}`, the exact smoke test the sticky note
  on TSWS 00 prescribes and records as having "never once succeeded", and gets
  `ok:true`.
- Negative control: the same `jobs.test.js` run against the unfixed Drive copy
  fails 15 of 16. The one that passes is the ffprobe guard, correctly true in
  both. The tests detect the defects rather than merely agreeing with the fix.

**Not proved, and it matters:** no ffmpeg exists in the container these fixes
were written in. Every test above pins the argv and the filter graph. **None of
them ran ffmpeg, so none of them prove a pixel or a sample.** The frame counts,
the levels and the silences have to be measured on the box. That is the
acceptance suite below, and until it passes, this worker is unproven regardless
of how green the unit tests are.

## Deploying it

Node 18 or newer, ffmpeg with libx264 and libx265, and a TLS terminator. The
autonomy driver recorded the intended home as srv1936199, the EditForge box, or
its own host. srv1936199's public address is not recorded in this repository and
was not invented here; take it from Hostinger.

```bash
# 1. user, directories, code
sudo useradd --system --home /opt/tsws-render-worker --shell /usr/sbin/nologin tsws
sudo mkdir -p /opt/tsws-render-worker /data/tsws
sudo chown -R tsws:tsws /data/tsws

# copy jobs.js server.js package.json into /opt/tsws-render-worker
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

```bash
curl -s https://render.editforge.online/health | python3 -m json.tool
```

`job_count` must read **18**. Fewer means an older `jobs.js` is loaded, and the
sticky note's warning applies: a still plate renders as one frame, not a held one.

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
  "output":"t/mix.flac","guards":[{"start":544,"end":548}],"duration":880.907}}'
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

**4. A2, the length pin.**

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 /data/tsws/t/mix.flac
```

Expect `880.907000`, not `880.849`. Confirm the poll result also says
`"pinned": true`; if it says false, the caller did not send `duration` and the
58 ms defect is still live on that call.

Only after all four pass is it worth wiring the real lane.

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
