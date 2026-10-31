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
| #448 | `wavespeed` on the outward gate's server list, with a pass for a call that only asks for a price, its tests, the gated list in `CLAUDE.md`, the skill and job record brought up to the v2 stills, and the skill count after #443 and #444 crossed | pending at the time of writing |

#443 merged under the standing approval of 2026-10-11, with every check on its head `855749f` green and the merge with `main` at `05a9a9c` run locally first (`test_estate_reconcile.py` and `test_vendored_skills.py`, 100 passed). There is nothing to read back from a deployed surface: the skill is files in this repository, and it loads in the next session that checks out `main`. CI on the merge commit `fad84de` was still running when this doc was written.

## The SH020 stills

Three paid runs on 2026-10-30, all `google/nano-banana-pro/edit` at 2K, $0.126 each and $0.378 in all, with the spend approved by Tee on cards. The end still came first, from native frame 191 and the SH100 start composite. The start still's first attempt copied the end still's layout, and its retry with a head sheet held the layout and lost two masks.

Both defects were then fixed on 2026-10-31 with no paid run. The end still's seam repair had cut the walker with the shoulder bag in two; the seam was re-cut along the edited backpack man's edge, and the walker is whole. The start still took the beige-coat pedestrian's and the briefcase man's masks from the end still by a local warp. Measured v1 against v2, the end still changed only in rows 420 to 899 and columns 1639 to 1722, and the start still only in x 744 to 1091 and y 488 to 522. Tee accepted both as v2, on a card that named the cost: the two carried masks are hand composites on faces about 30 px wide, soft when zoomed. The same-mask check on them was by eye only. The hashes, the bounds and that check are in the job record, `.claude/skills/tsws-shot-prompt/references/SH020_job_2026-10-30.md`, and the hashes are in the manifest on Drive too.

Filing to Drive is half done. Folder `SH020_VENETIAN_STILLS_v2_2026-10-31_DRAFT` (`1lHwRHyrHzdw4rGHpD1LEpxvnmqPTgWna`) holds the manifest, `SH020_v2_SHA256SUMS_and_provenance.txt` (`1-M-bi-r7INAx7ip2AiIVIM-p8quATE7O`), and at the time of writing nothing else. Uploading the PNGs through the connector was not attempted, because it takes a file inline as base64 and these come to 1.2 to 5.1 million characters each, so the three PNGs go in by Tee's hand.

## How it was checked

Three critic cycles ran on the skill. Cycle 1 confirmed ten findings and cycle 2 confirmed thirteen, each by a separate verifier. Cycle 3's verifiers could not run because the subagent limit was reached, and resets 2026-11-03T05:00Z; the session re-ran each of its checks itself before applying it, and the skill's description says so. The cycles found three measurement defects in `align_still.py`: static regions that held people, a phase correlation bias of up to about 0.32 px, and an ECC that read a 30 px body move as 0.6 px. All three are fixed and recorded in the skill.

The follow-up had a cold re-read before its first push, which found two wording defects, and then a fresh critic after it, once agents could run again: a workflow of three attackers, on the gate, the records and this doc, each in its own worktree at `506586c`, with an independent refuter for each of the six most severe findings. The gate attacker found nothing. Nine findings came back, all low. Five were confirmed and one refuted; the other three hit the cap of six, and one of them duplicated a confirmed finding. The confirmed five and the two unverified non-duplicates were each checked again in this session and fixed:

- the seam limits of x 1640 and x 1655 were the intended cut, while the changed pixels reach as far left as x 1639 at head height and x 1645 to x 1655 below it, band by band; the record now gives only the measured bounds;
- "the Drive connector cannot carry files of this size" was reasoned from base64 sizes and never tried, and now says so;
- "fixed SH020" for the carried masks overstated a check that was by eye only, and zoomed in the briefcase man's mask is a soft bronze shape whose cat-eye outline does not read; the skill now says so and lists it as unverified;
- the v1 PNGs were sent at 23:00:22Z, with the head sheet earlier at 22:56:46Z, not both together;
- this doc said the stills "live in" the Drive folder, said "he is whole" of the wrong man, and did not link the job record.

While it ran, `main` went red at `164497a`. PR #443 and PR #444 had each raised the skill count to twenty on its own branch, and they merged eight minutes apart, so the directory holds 21 while `CLAUDE.md` said twenty. The pin could not read the right answer either: its regex stopped at a hyphen and its number words ended at twenty. This PR merges `main`, sets the count to twenty-one with seventeen ours, and teaches the pin compound number words. Against the old `CLAUDE.md` the pin still fails, on `assert 20 == 21`.

On the merged tree, the standalone job's 53 files plus the other readers of `CLAUDE.md` gave 6793 passed with no `PYTHONPATH` and no database, and `ruff check .` is clean.

## Open

- Whether the distant man facing the camera at about (1750, 530) in the v2 end still, which is also SH070's first frame, counts as a visible street face under the mask rule. About 12 px of native face with no half-mask. Tee's call.
- The SH020 motion run. Kling 4.0 at 8 s and 1080p was quoted at $1.504 on 2026-10-30; it is a paid run and needs its own card and a fresh quote.
- Whether Cinema Studio's composer has a last-frame slot, and whether its "prompt sent to the model" view shows the expanded text.
- Whether Visual Bible v2.11's QC gate 2, one gold thread, applies to the long-form street plates.
- Whether the briefcase man's carried mask holds as the same bronze baroque cat-eye in motion.

## DEVON RECEIPT

AREA: Podcast, Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_tsws-shot-prompt-skill-and-sh020-v2_v1_2026-10-31-0431.md
DATE: 2026-10-31
DECISIONS: Tee ruled on cards that Cinema Studio shots go through WaveSpeed with camera terms (2026-10-30), that the SH020 method becomes the tsws-shot-prompt skill (2026-10-30), and on 2026-10-31 to merge it when green, re-cut the seam and transplant the two masks locally, put WaveSpeed on the outward gate, accept both v2 stills and file them to Drive.
FINDINGS: A head sheet fixed the start still's layout but did not carry two masks. The first seam repair cut a walker in two. align_still.py had three measurement defects, now fixed. Before the gate change, only a written rule stopped an unasked paid WaveSpeed run. The follow-up's critic confirmed five low wording and evidence defects, all fixed. Two PRs that each counted twenty skills turned main red at 164497a, fixed in the follow-up.
OPEN: The distant unmasked face in the SH020 end still, the briefcase man's soft carried mask in motion, the paid SH020 motion run, Cinema Studio's last-frame slot, gold thread on street plates, and the three PNGs into the Drive folder.
STATUS: #443 merged as fad84de; #448 carries the gate, the v2 records and the skill count fix for main.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
