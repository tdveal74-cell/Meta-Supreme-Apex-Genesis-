# TSWS shot prompts: the skill, the SH020 stills and the WaveSpeed gate

Status doc for the arc that set up WaveSpeed, wrote the first TSWS Cinema Studio prompt from the live canon, made the SH020 stills, and turned the method into a repository skill. Written 2026-10-31.

## The asks, in order

1. 2026-10-30, Tee: install the WaveSpeed CLI and MCP, then add the connector and the network secret, which he did himself.
2. 2026-10-30, Tee: "Generate me a TSWS prompt" for Cinema Studio, from the AI realism guide on Drive, after checking the frames.
3. 2026-10-30, Tee: "Rulings on inline cards".
4. 2026-10-30, Tee: "Install it", answered on a card as "Make it a TSWS skill".
5. 2026-10-31, Tee on cards: "Merge when CI is green", "Re-cut seam locally", "Local mask transplant", "Add WaveSpeed to the gate", "Accept both v2" and "File to Drive".

## What shipped

| PR | change | merged as |
|---|---|---|
| #443 | the `tsws-shot-prompt` skill: its `SKILL.md`, `scripts/align_still.py`, the SH020 job record, a pointer from `tsws-repair-workflows`, and the skill count in `CLAUDE.md` | `fad84de` |
| this arc's follow-up | `wavespeed` on the outward gate's server list, with a pass for a call that only asks for a price, its tests, the gated list in `CLAUDE.md`, and the skill and job record brought up to the v2 stills | pending at the time of writing |

#443 merged under the standing approval of 2026-10-11, with every check on its head `855749f` green and the merge with `main` at `05a9a9c` run locally first (`test_estate_reconcile.py` and `test_vendored_skills.py`, 100 passed). There is nothing to read back from a deployed surface: the skill is files in this repository, and it loads in the next session that checks out `main`. CI on the merge commit `fad84de` was still running when this doc was written.

## The SH020 stills

Three paid runs on 2026-10-30, all `google/nano-banana-pro/edit` at 2K, $0.126 each and $0.378 in all, with the spend approved by Tee on cards. The end still came first, from native frame 191 and the SH100 start composite. The start still's first attempt copied the end still's layout, and its retry with a head sheet held the layout and lost two masks.

Both defects were then fixed on 2026-10-31 with no paid run. The end still's seam repair had cut the walker with the shoulder bag in two; the seam was re-cut along the edited backpack man's edge and he is whole. The start still took the beige-coat pedestrian's and the briefcase man's masks from the end still by a local warp. Measured v1 against v2, the end still changed only in rows 420 to 899 and columns 1639 to 1722, and the start still only in x 744 to 1091 and y 488 to 522. Tee accepted both as v2. The hashes are in the job record and in the manifest on Drive.

The stills live in Drive folder `SH020_VENETIAN_STILLS_v2_2026-10-31_DRAFT` (`1lHwRHyrHzdw4rGHpD1LEpxvnmqPTgWna`). The connector could not carry files this size, so the folder holds the manifest, `SH020_v2_SHA256SUMS_and_provenance.txt` (`1-M-bi-r7INAx7ip2AiIVIM-p8quATE7O`), and the three PNGs go in by Tee's hand. At the time of writing it held the manifest alone.

## How it was checked

Three critic cycles ran on the skill. Cycle 1 confirmed ten findings and cycle 2 confirmed thirteen, each by a separate verifier. Cycle 3's verifiers could not run because the subagent limit was reached, and resets 2026-11-03T05:00Z; the session re-ran each of its checks itself before applying it, and the skill's description says so. The cycles found three measurement defects in `align_still.py`: static regions that held people, a phase correlation bias of up to about 0.32 px, and an ECC that read a 30 px body move as 0.6 px. All three are fixed and recorded in the skill.

The follow-up was checked by a cold re-read of its own diff, with no fresh critic, for the same reason. That re-read found two wording defects in it, both fixed before the push. `test_gate_ledger.py`, `test_estate_reconcile.py` and `test_vendored_skills.py` gave 1027 passed with no `PYTHONPATH` and no database, and `ruff check .` is clean.

## Open

- Whether the distant man facing the camera at about (1750, 530) in the v2 end still, which is also SH070's first frame, counts as a visible street face under the mask rule. About 12 px of native face with no half-mask. Tee's call.
- The SH020 motion run. Kling 4.0 at 8 s and 1080p was quoted at $1.504 on 2026-10-30; it is a paid run and needs its own card and a fresh quote.
- Whether Cinema Studio's composer has a last-frame slot, and whether its "prompt sent to the model" view shows the expanded text.
- Whether Visual Bible v2.11's QC gate 2, one gold thread, applies to the long-form street plates.
- An independent critic on the follow-up once the subagent limit resets.

## DEVON RECEIPT

AREA: Podcast, Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_tsws-shot-prompt-skill-and-sh020-v2_v1_2026-10-31-0431.md
DATE: 2026-10-31
DECISIONS: Tee ruled on cards that Cinema Studio shots go through WaveSpeed with camera terms (2026-10-30), that the SH020 method becomes the tsws-shot-prompt skill (2026-10-30), and on 2026-10-31 to merge it when green, re-cut the seam and transplant the two masks locally, put WaveSpeed on the outward gate, accept both v2 stills and file them to Drive.
FINDINGS: A head sheet fixed the start still's layout but did not carry two masks. The first seam repair cut a walker in two. align_still.py had three measurement defects, now fixed. Before the gate change, only a written rule stopped an unasked paid WaveSpeed run.
OPEN: The distant unmasked face in the SH020 end still, the paid SH020 motion run, Cinema Studio's last-frame slot, gold thread on street plates, the three PNGs into the Drive folder, and an independent critic after 2026-11-03T05:00Z.
STATUS: #443 merged as fad84de; the gate and v2 records follow in their own PR.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
