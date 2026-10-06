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
is 1,608 words in total. Re-measured on 2026-09-23 after the episode promises change
(Learning Objective, 3 to 5 step checklist, one question close, no audit
pointer): the TQO block is 973 words and 5,790 characters, the NCO block is
unchanged at 543 and 3,558, and the node source is 1,764 words.

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

## The two versions, exported

The workflow carries two graphs at once, and every count above was taken from
the wrong one. The public API returns the draft at the top level and the
published version under `activeVersion`; the editor shows the draft, the
schedule runs the published version. Read on 2026-10-06, the published version
`e04868cf` (activated 2026-10-05T22:40:30Z) is 265 nodes, 22 roots and 17
trigger type nodes, while the draft `206299ba` (saved 2026-10-06T01:25:46Z) is
290 nodes: it adds the 24 node HeyGen Avatar lane and the manual trigger
`TEST Render Only (Claude 5 Oct)`, removes nothing, and modifies `Build Movie`
and `Presenter: Attach Clips`. The 240 at the top of this file was measured on
2026-09-16 and no version from that day survives on the instance, so it is a
sentence rather than a count.

`exports/qEkGOUsNyVaRAmm6_active.json` and `exports/qEkGOUsNyVaRAmm6_draft.json`
are the two graphs as `scripts/tqo_v5_export.py` wrote them, with the read time
inside each file. Regenerate them with that script, never by hand, and read the
counts out of its output. `test_tqo_v5_exports.py` computes both counts from
the files and fails when this paragraph drifts from them.

The same test records one defect by name, and the name is now gone from its
allowlist because the fix is published. `Script: Already Written?` was an IF
node at typeVersion 1 carrying a typeVersion 2 condition shape. The engine copy
in the executions read `{"conditions": {}, "combineOperation": "all"}`, and IF
v1 sends an item with nothing to test to its TRUE output, which is wired to
`Script: Hydrate from Row`, which throws on an empty script. Measured on
scheduled execution 2257, 2026-10-06T10:20Z: row 46, the first locked TQO row
ever to reach a pass, went TRUE out of that node and died at line 12 of the
next one with no script written. On Tee's ruling the published version
`e04868cf` was restored as the draft, the one node recreated at typeVersion 2
with identical parameters, id, position and edges, read back as the only
difference, and published as `3123aef0` at 2026-10-06T12:22Z. The exports were
regenerated after that publish, so both files now carry 265 nodes and the same
version id, and the allowlist in the test is empty. The Avatar lane and the
`TEST Render Only` trigger stay in version history as `206299ba` for a publish
of their own.

The fix was proven the same hour by one watched pass fired on the published
version: execution 2269, 2026-10-06T12:23Z, took row 46 out of the FALSE edge
of the retyped node into `Package: Context`, wrote the script through
`Write Script (Cerebras)` and one expansion (828 to 1,465 words), ran the
doctor (76, repaired), dash repair (11 sentences restructured, 0 dashes left)
and the originality scan (95), and saved it. The Script Gate then held the row
at status Error on one rule, line 69 of `Script Gate: Quality`: the last 60
words must carry both a question mark and the word comments, and the script
ends on a question that never says comments. That is the gate working as
written against a writer prompt that does not demand the word, and it is a
ruling for Tee rather than a defect in this change.
