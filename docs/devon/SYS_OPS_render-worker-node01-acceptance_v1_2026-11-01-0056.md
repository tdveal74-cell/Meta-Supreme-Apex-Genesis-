# Node 01 rendered on the n8n box, and why its bytes are not Proof 0's

Written 2026-11-01. It follows
`SYS_OPS_render-worker-acx-deploy_v1_2026-10-31-2128.md`, which closed the deploy
and left the Node 01 acceptance render open.

## The inputs

Tee ruled on a card to run the acceptance render that night, and on a second
card to bring the inputs onto the box through a one-off n8n workflow rather
than a public Drive link. No Drive client was found on the box: no rclone,
gdrive, aws or s3cmd, and gcloud present with no credentialed account. The Drive
credential already known to work was n8n's.
`ACX Node 01 one-off Drive pull (archive after use)`, id `omf4lxWLDF5zOQgw`,
never published, ran once in manual mode, execution 5231. It downloaded the 17
input files (five stills and twelve lines) of the Drive folder Node 01 Masters
into the n8n container with the existing Drive credential. They were copied to
`/data/tsws/acx/node01/src` and hashed against the Proof 0 input table of
2026-10-28, 17 of 17. That table is `measurements_inputs.json`, kept with the
Proof 0 report outside this repository, and its hashes are these:

| file | bytes | sha256 |
|---|---|---|
| `L01.mp3` | 77251 | `a2fe2958d4fdc5253de15b73d1d9c04d2dbf90a9e789b426be36302658a5e6ef` |
| `L02.mp3` | 37545 | `b0a255948a61f4ca7cff19eb58e94ce7eba543c89fc7619ebebb8a8d765dd956` |
| `L03.mp3` | 135765 | `9bae9f914582628ad0b71da234061b8fd5c7cb29402b403d2c2d81d598a76d91` |
| `L04.mp3` | 91043 | `4a3d50ac09ccad58fe20d33ea87cbe6bdc8cecccb8bda1535d6d8aef2c0b5091` |
| `L05.mp3` | 49665 | `49b285b829f7e7d2acf8ee81e74e995042a3aad522629e86e7d520e4e82a5f4f` |
| `L06.mp3` | 81012 | `774bd63a6015e323b0bd888cdef40d516458ff58ebcba0ad897c65745b65bac9` |
| `L07.mp3` | 34619 | `fd74134fb6e824a8f7a36ee10ee1c1070c04ab9216bbfc7eaad09b67efcae404` |
| `L08.mp3` | 127824 | `a8ae99f598b1be0314831de4a47335b725b861964ed0f533248280964572977f` |
| `L08_alt.mp3` | 129078 | `44d8f55018b9c19e4ff1865d119e4f8b9fac7c679babe9d87950625ce6d39708` |
| `L09.mp3` | 81012 | `60d7d6dcee79cdc9ac50f0045db7ec8d389768e6d8d3580da72ccce797d1d19c` |
| `L10.mp3` | 90625 | `cf841138789292b5952bfc78928cf117402d92b7ef397841808fbb5e84a15c61` |
| `L11.mp3` | 101492 | `05567fcca996d3cc56202941054736e66d2a980749d7711f9d67d30c656c766b` |
| `ACX_NODE01_R1_ARCHIVIST_BOOK.png` | 1559129 | `fdbcc90a73963400d44df2fbe8ee8d4ebacece0aee4d18cc65f0d391f4d6381c` |
| `ACX_NODE01_R2_COPY_ASSEMBLING.png` | 1870758 | `3dcb30dbf8dcbd5ec666c35daaa04b35bd215ad68b53aa77063c4f9038cc4e21` |
| `ACX_NODE01_R3_COPY_CLOSEUP.png` | 2177906 | `bd530e561a624fc7e429623c46e403bcef3561cf4830283c7c258adaa9622be9` |
| `ACX_NODE01_R4_CONFRONTATION_FINAL.png` | 1682375 | `cdbf0a3474540a2e30aca3880a57bc9a87c90e581594e15544418936fde6fc22` |
| `ACX_NODE01_R5_DISSOLUTION_FINAL.png` | 1937918 | `796368d4f61cef1d0cb233ef46a2e9a16eebfd6317c2fb44319211dbb5437841` |

 The workflow was then archived
and the container copies removed. The execution's own final status was not read
before the archive, and an archived workflow's executions cannot be read through
the connector; the 17 matching hashes are the evidence that it worked.

The five 1080x1920 masters were made on the box. The Proof 0 report says they
came from a Lanczos upscale to 1082x1923 and a centre crop, and that recipe
reproduces nothing. A search over sizes, filters and crop offsets found the one
that does, `scale=1082:1922:flags=lanczos,crop=1080:1920:1:1`, and on the box it
gave all five sandbox masters byte for byte, file and pixels.

## The run

`word_timings` finished in 21.89 s with 11 lines and 130 words, and it
downloaded base.en into `/data/tsws/hf` from inside the unit. That was the one
part of the deploy no earlier check could prove. `acx_node_assemble` then ran
for about 7.7 minutes; the box reads `nproc` 2. Runtime, picture against
sound, loudness, gain, limiter, shot frame counts, caption count, red frames
and red breaches came out as the sandbox record has them. Two lint verdict
windows end 20 ms later than the sandbox's, and the box counted 84 dense cyan
frames in the platform zone against 85; the control run below, on the
sandbox's word timings, gave the sandbox's numbers on both. The master's sha256
did not match: `c2562dd5...` against Proof 0's `9e2802af...`.

## Why the bytes differ

Two causes, both measured. The box's own speech model run placed 33 of 260
word edges away from the sandbox run's, 32 of them by 20 ms and one, the end of
"everything." in L06, by 40 ms. Ten of the 31 caption cues differ at an edge:
nine by 20 ms, and cue 14 by 20 ms at its start and 40 ms at its end. The
caption text is the same. The two word files also differ by a trailing "Mhm."
in the sandbox's L08 and in the punctuation or case of six words. Why the two
model runs differ was not measured.

That is not the whole difference. A control run on the box used the sandbox's
own word timings. It matched the sandbox byte for byte in both narration WAVs,
both caption files and the caption chunks, and first differed at the five shot
segments, which are the first output of libx264. The encoder picks its thread
count from the cores it sees, and its bitstream depends on that count. In a 4
core container, shot 0 reproduced the sandbox's `5418cb7a...`. The same command
pinned to 2 cores with `taskset` reproduced the box's `840abf06...`. With
`-threads 6` it gave `5418cb7a...` on 2 cores and on 4.

At the time only shot 0 had been encoded that way. That showed the thread count
moves the bytes, not that it is the only cause; the full pinned run in the next
section shows that. The Node 01 master on the box is a valid render for Tee's
watch, but it is not the Proof 0 file.

## The thread pin

Tee ruled on a card to pin the thread count, prove it, merge it and then
redeploy. Commit `020295c` adds `-threads 6` to the three libx264 encodes in
`acx_node.js`: the shot segments, the overlay pass and the master mux. Six is
what a 4 core host picks on its own. A new test in `acx_node.test.js` fails when
any libx264 encode in the file lacks the pin; with one pin removed the suite
read 35 passed and 1 failed.

The proof ran end to end in a 4 core container, with the worker held to two
cores by `taskset -c 0,1`, on the sandbox masters, the sandbox lines and the
sandbox word timings. The pinned code wrote the master at `9e2802af...`, the
Proof 0 master byte for byte. The five shot segments, the silent picture, the
overlay picture, the narration mix and the three caption files matched the
sandbox on the way. Before the pin, the shot segments were the first files to
differ on a 2 core host.

The box still runs the unpinned file until the redeploy, which follows the merge.

## The box changed under this record

Read on the box at 01:33Z: the six worker files in `/opt/tsws-render-worker`
match `122bc70`, the merge of PR #467 (face-on Shorts), byte for byte. They were
copied at 00:59:18Z, the service restarted at 00:59:38Z, and `/health` reads 25
job types with `caption_srt` among them. A `word_timings` job, `03365f03`, ran
at 01:05:44Z. This session did none of that; when this was written nothing
identified who had, and Tee confirmed later the same day, on a card, that it was
a session he started. No open pull request records the
upgrade, and `DEPLOY.md` on main still says the box reads 24.

Before reading the box, this session put a card to Tee that said #467 was not on
the box and asked whether the redeploy should carry it. That premise was taken
from `DEPLOY.md` and was false. Tee ruled to copy only `acx_node.js`. With the
box already on `122bc70`, which is also current main for all six files, that
copy leaves the box on one commit, the merge of this PR.

Because that session was using the box, the restart waits for `/status`
to read nothing running and nothing queued, immediately before it, as the
upgrade steps require. A restart still drops the job table, so a finished job
whose result has not been read yet loses its record; its output files stay.

## DEVON RECEIPT

AREA: Systems, Podcast
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_render-worker-node01-acceptance_v1_2026-11-01-0056.md
DATE: 2026-11-01
DECISIONS: Tee ruled on a card to run the Node 01 acceptance render on the n8n box that night, and on a second card to move the inputs with a one-off n8n Drive pull, which was archived after use, rather than a temporary public Drive link. On later cards he ruled to pin the encoder thread count, prove it on the full master, merge it and then redeploy; to remove the control run's output, the sandbox words file and the /tmp job files while keeping the acceptance render (the words file is held until the pinned rerun on the box, which needs it, and removed after); and to redeploy only acx_node.js rather than a whole build.
FINDINGS: The ACX Node path runs end to end on the box. word_timings downloaded base.en inside the unit and the assembly matched the sandbox record on runtime, sync, loudness, limiter, shot frame counts, caption count and the red-frame lint. The master is not byte identical to Proof 0, for two measured causes: the box's speech model run placed 33 of 260 word edges 20 or 40 ms from the sandbox run's, and libx264's bitstream follows its automatic thread count, which follows the host's cores. With -threads 6 pinned in acx_node.js, a 2 core run on the sandbox inputs and word timings rebuilt the Proof 0 master byte for byte. The Proof 0 report's master recipe of 1082x1923 is one row off; 1082x1922 with a crop at 1,1 reproduces the masters. The box was upgraded to 122bc70 (25 jobs) at 00:59Z by a session Tee started, unrecorded, and this session's card to Tee wrongly said it was not.
OPEN: The redeploy of the pinned acx_node.js to the box after this merges, and a rerun there on the sandbox word timings expecting 9e2802af, after which the sandbox words file comes off the box. Why the two base.en runs differ. Tee's watch of the Node 01 master. A record of the 00:59Z upgrade to 122bc70 by whichever session made it.
STATUS: Acceptance render done on the box and measured against the sandbox. Byte identity not reached on the box; the cause is found, and the pinned code reproduces the Proof 0 master on 2 cores in a container. The redeploy follows the merge.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
