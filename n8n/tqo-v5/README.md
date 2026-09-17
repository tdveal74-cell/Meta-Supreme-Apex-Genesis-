# TQO FINAL V5 Code node sources

`TQO FINAL V5` is `qEkGOUsNyVaRAmm6` on n8n.editforge.online, 240 nodes, and it
is the workflow that decides what publishes. Until 2026-09-16 none of it was in
this repository. The DEVON organs next door have been mirrored and diffed since
2026-09-06; the content gate had no copy anywhere, so a change to the rule that
holds or ships an episode left no diff and no review.

This directory starts closing that. It is not complete and does not pretend to
be: three nodes of 240 are here, the one that was changed and the two that hold
the canon.

| File | Node | What it decides |
|---|---|---|
| `build_qc_prompt.js` | `Build QC Prompt` | The whole QC rubric, both verdicts, and the hard blockers that hold an episode regardless of score |
| `build_script_prompt.js` | `Build Script Prompt` | The show canon: the whole system prompt that writes every episode of both shows |
| `show_context_script.js` | `Show Context: Script` | The identity board the prompt reads: channel, taglines, positioning, table ids and the per run limits |

The second and third arrived on 2026-09-17, read from the live public API at
workflow `updatedAt` 2026-09-16T14:02:48.875Z, 240 nodes, active. Measured from
that read rather than described: the TQO block is 805 words and 4,822
characters, the NCO block is 550 words and 3,543 characters, and the node source
is 1,608 words in total.

`services/devon/tqo_canon.py` is the same canon expressed as rules that know
whether they bend, and `test_devon_tqo_canon.py` fails when a rule's text stops
appearing in `build_script_prompt.js`. That is the mechanism that keeps the copy
honest, so a live edit that is not carried back turns the build red instead of
sitting undetected. Edit either one and run
`python3 -m pytest -q test_devon_tqo_canon.py`.

That mirror immediately found a contradiction, and it is now fixed. The NCO
branch instructed the model to emit a description line carrying a banned mark,
as "this exact line", while hard rule 1 bans that mark studio wide and
`Build QC Prompt` caps the voice dimension at 3 for any occurrence. Seventeen
banned marks were in the node, across sixteen lines. Tee ruled on a card to fix
all of them, and the live node was edited on 2026-09-17 at 16:40:13Z: every one
restructured into sentences rather than given a substitute mark. The node was
read back byte identical to this mirror, exactly one node of 240 changed, the
connections untouched and the workflow still active. The mandated line now reads
`NCO Forge. ${ctx.tagline}`, which renders as "NCO Forge. Leaders aren't born.
They're forged."

Whether the mandated mark ever reached a published description was never
established: `nco_content` holds 25 rows and none of them has a description
written, so there was nothing to check. Recorded as unproven rather than clean.

The rest of the QC chain is live only and worth mirroring next: `Token Budget:
QC` converts the Anthropic shape this node emits into the Cerebras
`gpt-oss-120b` shape and appends the dash ban, `Run QC (Cerebras)` posts it,
and `Parse QC + Set Verdict` turns the reply into the verdict, the score and the
findings written onto the row.

Nothing here executes. n8n holds the graph, the credentials and the schedule.
A change made here has to be applied to the live node, and a change made live
has to be copied back, or this file is a lie about what gates the channel.
