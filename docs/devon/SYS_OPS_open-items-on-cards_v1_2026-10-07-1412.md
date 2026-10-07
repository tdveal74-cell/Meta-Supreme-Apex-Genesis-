# Every open item on a card, and what each ruling did

This follows `SYS_OPS_carousels-and-the-second-critic_v1_2026-10-07-1344.md`.
PR #314 merged as `7c124a7` on Tee's earlier ruling once all seven checks were
green on `483fcd1`. Tee then asked for every open item and ruling on inline
cards. Sixteen cards went out in four rounds; this is what each answer did.

## Rows, written to the live tables and read back

Row 46 has Human Review ticked on Tee's "Tick it now". My objection is logged
once on the row: that box is the publish gate, so a rendered video of this
script would clear OS 28 without anyone watching it.

Row 4 lost the sentence pointing to the retired free job security audit, from
`script` and from `manifest`. The video already rendered for the row still
speaks it, so the row needs a re-render, which is a paid job and needs his go.

Row 5 moved from Ready to Idea with `package_locked` set to `tee`, which is the
only state TQO Research reads, so the 09:40Z run on 2026-10-08 looks for its
sources and the writer rewrites it from them. The old script is kept in the
row's `notes`. Taking it off Ready is a step the card did not spell out.

NCO row 26 read `tee: How AI Screening Can Change Veteran Hiring Outcomes
(locked from package_options rank 3, 2026-09-30)`, which the resolver reads as
a title of his own with an empty `video_title`. It now reads `3`, the same pick
in the form the resolver takes. The card proposed the topic title instead; his
earlier pick was kept.

## V5 `12266aff`

Four rulings, built offline, run on an inactive copy, then put live and read
back byte for byte.

- The doctor can trim a script under the 1,200 word floor after both
  expansion checks have passed, which is what failed test 2357. A check now
  runs on the doctored text and expands it once more when it is short,
  keeping the hook and the close verbatim and refusing any added number.
- The Sources Gate treats form numbers, 24 hour times and unit ordinals as
  names, never percentages or dollar figures, and still fails MOS codes closed.
- It refuses a sentence about the future that carries a figure and names no
  approved source.
- Both show blocks ask for a mechanism, a step or a sourced figure where they
  asked for "a concrete example or number".

The copy run found a defect older than any of this. `Fetch Prior Episodes`
returned nothing for NCO, which had no prior script, and execution 2361 ended
there as a success with nothing saved. Every NCO script would have died there
silently. It now always outputs, and execution 2362 wrote row 26's first
script, 1,494 words, held as Error on an invented "50 person team". It speaks
to camera. It also restates the World Economic Forum's 2030 figure as "in a
decade" and advises estimating numbers on a resume, neither of which a gate
can see; both are Tee's to judge on the row.

## The presenter lane

A read only audit found that neither show can render a presenter episode
today. Live V5 has no avatar step and refuses every render at `Presenter:
Attach Clips` for want of valid clips. The avatar build lives in unpublished
version `206299ba`, built on `e04868cf`, and publishing it would roll back a
week of fixes. The render worker refused HeyGen's file host in execution 2221
with `media_host_not_allowed`. Tee confirmed HeyGen v3 itself works, which
2221 also shows, and said he has found a cheaper option, so the lane and a
spending cap are held for that.

Tee confirmed the six landscape looks marked approved in
`at_tqo_avatar_looks` are approved. That supersedes the line in
`SYS_OPS_six-rulings-on-cards_v1_2026-10-06-2043.md` saying nothing moves
until he approves two.

The D9-B consent PDF reads his printed name twice and the date 8/19/2026. Its
header placeholder for the date was never filled, and the signature mark
cannot be read from the text.

## Drive

No audio file on Drive is named for NCO. The nearest are about nineteen copies
of `tqo-voice-27.mp3` from 30 Sep and 1 Oct, the days of the Two-Minute
Standard test, which is unverified as the NCO episode. The v9 vertical cut is
still 22 bytes and waits on Tee's re-export. The v2 brand packages wait on
style guide PDFs from him, and the NCO logo on an image he generates from the
prompt he was given.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_open-items-on-cards_v1_2026-10-07-1412.md
DATE: 2026-10-07
DECISIONS: Tee ruled on cards: tick row 46 now; fix row 26's lock with a presenter pitch; NCO logo by a prompt and reference he generates from; v2 brand by style guide PDFs; re-check length after the doctor; allow named military terms; gate future claims; reword the show blocks to sourced figures; research and re-gate row 5; clear row 4's audit pointer; he re-exports the v9 file; the six landscape looks are approved; check the consent PDF. Avatar lane and spend cap held for a cheaper option he has found.
FINDINGS: PR #314 merged as 7c124a7. Fetch Prior Episodes stopped every first NCO script silently; fixed. V5 12266aff published and read back. Execution 2362 wrote NCO row 26's first script, held as Error on one invented figure. Neither show can render a presenter episode on live V5. The consent PDF is dated 8/19/2026 with the header placeholder unfilled.
OPEN: The avatar lane and a HeyGen spend cap, waiting on Tee's cheaper option. Row 4's re-render. Row 26's review. Row 5's research run at 09:40Z on 2026-10-08. The expansion branch after the doctor has not run live. The v2 style guides, the NCO logo and the v9 re-export are Tee's. Row 46 is ticked without a watched video.
STATUS: V5 active and draft 12266aff, read back; test copy bNNR1v39mtUktl5D archived; this doc's PR not yet opened at the time of writing.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
