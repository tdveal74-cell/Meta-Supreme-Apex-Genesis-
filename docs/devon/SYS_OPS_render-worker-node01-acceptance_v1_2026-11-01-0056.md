# Node 01 rendered on the n8n box, and why its bytes are not Proof 0's

Written 2026-11-01. It follows
`SYS_OPS_render-worker-acx-deploy_v1_2026-10-31-2128.md`, which closed the deploy
and left the Node 01 acceptance render open.

## The inputs

Tee ruled on a card to run the acceptance render that night, and on a second
card to bring the inputs onto the box through a one-off n8n workflow rather
than a public Drive link. Nothing on the box could read Drive except n8n.
`ACX Node 01 one-off Drive pull (archive after use)`, id `omf4lxWLDF5zOQgw`,
never published, ran once in manual mode, execution 5231. It downloaded the 17
input files (five stills and twelve lines) of the Drive folder Node 01 Masters
into the n8n container with the existing Drive credential. They were copied to `/data/tsws/acx/node01/src` and
hashed against the table of 2026-10-28, 17 of 17. The workflow was then archived
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
for about 7.7 minutes on the box's 2 cores. Runtime, picture against sound,
loudness, gain, limiter, shot frame counts, caption count and the canon lint
all came out exactly as the sandbox record has them. The master's sha256 did
not: `c2562dd5...` against Proof 0's `9e2802af...`.

## Why the bytes differ

Two causes, both measured. The box's own speech model run placed some word
edges one 20 ms step from where the sandbox run placed them, so ten of the 31
caption cues sit 20 ms apart. Why the two model runs differ was not measured.

That is not the whole difference. A control run on the box used the sandbox's
own word timings. It matched the sandbox byte for byte in both narration WAVs,
both caption files and the caption chunks, and first differed at the five shot
segments, which are the first output of libx264. The encoder picks its thread
count from the cores it sees, and its bitstream depends on that count. In a 4
core container, shot 0 reproduced the sandbox's `5418cb7a...`. The same command
pinned to 2 cores with `taskset` reproduced the box's `840abf06...`. With
`-threads 6` it gave `5418cb7a...` on 2 cores and on 4.

So the pipeline on the box is correct, and a master is only reproducible
across hosts if the encoder's thread count is fixed. `acx_node.js` does not fix
it today. The Node 01 master on the box is a valid render for Tee's watch, but
it is not the Proof 0 file.

## DEVON RECEIPT

AREA: Systems, Podcast
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_render-worker-node01-acceptance_v1_2026-11-01-0056.md
DATE: 2026-11-01
DECISIONS: Tee ruled on a card to run the Node 01 acceptance render on the n8n box that night, and on a second card to move the inputs with a one-off n8n Drive pull, which was archived after use, rather than a temporary public Drive link.
FINDINGS: The ACX Node path runs end to end on the box. word_timings downloaded base.en inside the unit and the assembly matched the sandbox record on runtime, sync, loudness, limiter, shots, captions and lint. The master is not byte identical to Proof 0, for two measured causes: the box's speech model run placed some word edges 20 ms from the sandbox run's, and libx264's bitstream follows its automatic thread count, which follows the host's cores; pinning -threads 6 reproduced the sandbox shot on 2 cores. The Proof 0 report's master recipe of 1082x1923 is one row off; 1082x1922 with a crop at 1,1 reproduces the masters.
OPEN: Whether to pin the encoder thread count in acx_node.js so any host reproduces a master byte for byte, which is a code change and a redeploy. Why the two base.en runs differ by a 20 ms step. Tee's watch of the Node 01 master. Clearing the control run's output, the sandbox words file and three small files in /tmp on the box.
STATUS: Acceptance render done on the box and measured against the sandbox; byte identity not reached, with the cause found and a one flag fix shown on one shot.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
