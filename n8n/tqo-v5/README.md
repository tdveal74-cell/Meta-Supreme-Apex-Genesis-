# TQO FINAL V5 Code node sources

`TQO FINAL V5` is `qEkGOUsNyVaRAmm6` on n8n.editforge.online, 240 nodes, and it
is the workflow that decides what publishes. Until 2026-09-16 none of it was in
this repository. The DEVON organs next door have been mirrored and diffed since
2026-09-06; the content gate had no copy anywhere, so a change to the rule that
holds or ships an episode left no diff and no review.

This directory starts closing that. It is not complete and does not pretend to
be: two nodes are mirrored here, the one that was changed and the one that holds
the canon, and the identity board that `Show Context: Script` returns now lives
as data in `services/devon/show_registry.py`, traced into the export below by
`test_devon_show_registry.py`.

| File | Node | What it decides |
|---|---|---|
| `build_qc_prompt.js` | `Build QC Prompt` | The whole QC rubric, both verdicts, and the hard blockers that hold an episode regardless of score |
| `build_script_prompt.js` | `Build Script Prompt` | The show canon: the whole system prompt that writes every episode of both shows |

The second arrived on 2026-09-17 beside a `show_context_script.js` mirror of
`Show Context: Script`, both read from the live public API at workflow
`updatedAt` 2026-09-16T14:02:48.875Z, 240 nodes, active. That mirror was
retired on 2026-10-06: no test read it, and by then it lacked the
`packageLimit` the live node carries, so the file the README called the
identity board was wrong and nothing could say so. The registry module and
its test replaced it. Measured from
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
inside each file. Regenerate them with that script, never by hand, and copy the
table below from its output. `test_tqo_v5_exports.py` reads the table row by
row and fails when either row drifts from the export of the same role.

| version | id | nodes |
|---|---|---|
| active | `12266aff` | 274 nodes |
| draft | `12266aff` | 274 nodes |

Every webhook path and webhook id in the exports reads `redacted`. The Gumroad
sale ping carries no authentication, so its random path suffix is the only
barrier on that door and the repository is not the place for it; the exporter
strips every path and id rather than deciding which ones are secrets, and the
test proves the Gumroad path is absent. The first export of 2026-10-06 carried
the path before this was understood, so on Tee's ruling the live path was
rotated to a fresh suffix the same day and published as `22519c20`, with the
new ping URL handed to him for the Gumroad side and kept out of this repository.

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
difference, and published as `3123aef0` at 2026-10-06T12:22Z, and the
allowlist in the test is empty. The committed exports have carried three
versions on 2026-10-06: `e04868cf` and the draft `206299ba` in the morning,
`b99b38ab` from 12:32Z (the close rule publish, which PR #303 merged), and
`3befd7a5` from 16:10Z. `3123aef0` and the Gumroad rotation `22519c20` were
published between those reads and never exported on their own. The Avatar lane and the
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

The exports were regenerated once more on 2026-10-06 at 16:10Z from
`3befd7a5`, the publish that gave `Show Context: Promote` and `Show Context:
Publish` the NCO tagline that `Show Context: Script` and `Show Context: Render`
already carried. Those are the only two: `Show Context: Brief`, the fifth node,
has no tagline key at all in this export, so four nodes carry the line and the
fifth never did.
The show registry lift (`services/devon/show_registry.py`) found that drift,
Tee ruled the two nodes fixed, and `test_devon_show_registry.py` now traces
the registry against this export with an empty drift map.

They were regenerated again at 20:42Z from `36013f35`, published at 20:36Z on
Tee's card ruling to disable the Gemini chat agent lane now rather than wait
for the split. That lane is seven nodes, `When chat message received`, `AI
Agent`, `Google Gemini Chat Model`, `Simple Memory` and three HTTP tools,
`READER`, `CREATOR` and `UPDATER`, the last two able to POST or PUT any
workflow on the instance. No other node connects to it. The draft was diffed
against the live version before publishing: the seven `disabled` flags were
the only difference and the connections were identical. The read back shows
`versionId` equal to `activeVersionId` and all seven disabled in the active
version. The nodes stay in the graph, disabled, until the split removes them.

They were regenerated again on 2026-10-07 from `99e32b37`, the Brief lane fix
Tee ruled on a card that morning. `Build Brief Prompt` had read
`$('Get Latest Content')`, the raw data table row, whose keys are lowercase,
and then looked for `f.Script`, so the writer was handed an empty script every
time. Manual execution 2295 put a Reach draft headed "No script provided" into
the account and reported success. The node now reads `DT Shim: Latest Content`
and throws when the script is empty, and the signature line in `Assemble Email
HTML` no longer opens with `&mdash;`. Only those two nodes differ from
`36013f35`; the connections are identical. Manual execution 2337 ran the fixed
lane from a temporary trigger that was added to the draft and removed before
publishing: the prompt carried 8,291 characters and the Brief came back with
zero dashes. The Brief lane only creates Reach drafts and never sends.

And again on 2026-10-07 from `54fbda3d`, the evidence fix Tee ruled after row
46. That script, written by this pipeline and passed by the doctor, the scan
and the gate, put eight unsupported lines in his mouth: advice he never gave,
conversations with HR leaders and unnamed firms and case studies. Three nodes
changed and nothing else. `Build Script Prompt` gains an EVIDENCE block for
both shows, outside the two measured show blocks, and `build_script_prompt.js`
mirrors it. `Build Doctor Prompt` gains a rule against invented experience and
now receives the DEVON recall as TEE'S RECORD, so his real material can stand.
`Script Gate: Quality` refuses ten patterns of invented first person
experience and unnamed sources. Measured on the gate code itself: row 46's old
script went from Scripted to Error on 8 hits, row 4 (his real seven day log)
scored 0. Manual execution 2344 rewrote row 46 on the draft: 0 invented first
person lines, but the writer then invented a named attribution and unsourced
figures, which no pattern can catch, and the gate held it as Error on length
and the close. That is why the next step is real sources on the row.

`6d67e0a8` was published the same day and never exported on its own. It
changed one node, `Package: Plan Batch`, on Tee's ruling that real sources go
on the row: a locked TQO row whose new `sources` column carries no entry with
both a `url` and a `quote` is left out of the pass with no writer call, stays
Idea, and is named in the plan note as waiting for approved sources. NCO is not
held, because NCO was not ruled. Row 46 was reset to Idea under it with its
script cleared.

The exports were regenerated on 2026-10-07 at 12:37Z from `61d4aeeb`, which
adds three Code nodes on existing wires and edits no existing node, so the
measured show blocks in `Build Script Prompt` and the canon traced to them do
not move. The diff against `6d67e0a8` was read before publishing: three nodes
added, none changed, and three edges each split around a new node.

- `Sources Rule`, between `Build Script Prompt` and `Series Addendum`, appends
  the row's approved sources to the writer's system prompt with the rule that
  every number, percentage, dollar amount and dated finding comes from them,
  named by origin in the sentence that uses it. A row with no sources is told
  to state no figures at all. `sources_rule.js` mirrors it.
- `Doctor Sources`, between `Build Doctor Prompt` and `Token Budget: Doctor`,
  hands the doctor the same list as APPROVED SOURCES. `doctor_sources.js`.
- `Sources Gate`, between `Script Gate: Quality` and `Save Script to Airtable`,
  refuses any numeral not found in a source quote or claim, except counts of
  ten or under and a year the episode idea names, any "according to" that does
  not name an approved origin or publisher, and any unnamed person cited as a
  source. A failure lands as Error with the reason in `qc_findings`, like every
  other gate failure. `sources_gate.js`.

All three are TQO only. The sources come from TQO Research
(`0zLNB34UOOTq6mck`, recorded under `n8n/tqo-research/`), which runs daily at
09:40Z. Manual execution 2351 on the draft wrote row 46 with its four approved
sources: the script cited all four with the origin named, then carried a 150
person division, an interview with an unnamed HR director and a 300 person
plant. The gate held the row as Error on those six figures
and on a close with no question. The unnamed person check was added to the
gate after that run, replayed on its script, and published with the rest.
Live and draft were read back equal, with all three bodies byte for byte in
the active version.

That paragraph first said the writer invented those three. A fresh critic
traced execution 2351 node by node and found otherwise: the first pass wrote
769 words using only sourced numbers, and the expansion step added all of
them, because `Script: Needs Expansion?`, `Script: Still Short?` and the length
line in `Token Budget: Script` asked it to lengthen each section "with a
concrete example ... or a number". The same critic found the gate reading
numbers out of markdown link URLs inside raw quotes, which let "30 minutes"
through in 2351, and found the 2023 figure narrowed to tech and moved to "last
year" in that script, so "the year kept" was not true either.

The exports were regenerated on 2026-10-07 at 13:16Z from `d7f4d56f`. It came
by way of `a6a2295a` the same hour, and every change below was ruled on a card.

- NCO Forge is held to the same sources standard. The three sources nodes drop
  their NCO bypass and `Package: Plan Batch` holds a locked row of either show
  that has no sources. `nco_content` gained `sources` and `research_note`.
- `NCO Presenter Rule`, between `Sources Rule` and `Series Addendum`, tells the
  NCO writer that Terrance Veal presents every episode on camera in his own
  likeness and cloned voice. The NCO block in `Build Script Prompt` still says
  single narrator and is measured by the canon, so the line is appended rather
  than edited in. `nco_presenter_rule.js` mirrors it.
- The two expansion prompts and the length line now say to lengthen with a
  mechanism, a step or a closer reading of a figure already in the draft, and
  never to add a number, company, person, study, interview or case.
- `Sources Gate` reads numbers from each source's `quote_text` and claim, never
  a raw quote with a link in it. It also refuses spelled out figures the sources
  do not carry, an unnamed firm or study that reported something, a name
  followed by found or predicts that is not an approved origin, and a unit that
  does not match, so `$41` is not `41%`.
- `Save Doctor Verdict` reads `last_feedback` and the gate status from
  `Sources Gate`, so a row that fails only that gate no longer says Cleared for
  Promote.
- `Token Budget: Script` tells the TQO writer to end on one question for the
  comments that ends with a question mark. Runs 2269, 2351 and 2356 had all
  closed on an instruction and failed the 23 Sep close rule.
- `Save Script to Airtable` and `Save QC to Airtable` are renamed `Save Script
  to Data Table` and `Save QC to Data Table`, which is what they always were.
  Fifteen nodes still call the Airtable API directly; Tee ruled they move as
  their stages are rebuilt in the split.

Two manual runs on row 46 proved the fixes. Execution 2356 on `a6a2295a`
expanded 936 words to 1,656 with no new figure and passed the Sources Gate with
0 unsourced; it failed only the close. Execution 2357 on `d7f4d56f` passed the
close and the Sources Gate and failed the floor at 1,124 words, because the
expansion reached 1,292 and the doctor then trimmed it, and the second
expansion is checked before the doctor runs. That gap is older than this change
and is open. Row 46 holds the 2356 script, with the close made a question and
four unsupported sentences cut by hand on Tee's ruling, as Scripted for his
review; `script_machine` keeps the machine text.

The exports were regenerated again at 13:58Z from `c2d51b46`, which changes
`Sources Gate` and nothing else, on a second critic's findings that Tee ruled
fixed. The attribution checks now run one sentence at a time: "according to
Gallup. Microsoft found that" had let Microsoft through on Gallup's approval.
A nameless group cited as a source, as in "managers who applied this report
that", is refused unless an approved origin is named in the same sentence.
Row 46 carried exactly that sentence past both gates; it was cut by hand under
Tee's earlier ruling, and the gate replayed on the row refuses the old text and
passes the new. No live run could exercise it, because no locked Idea row was
left to write.

The exports were regenerated at `12266aff` on four more rulings Tee made on
cards the same afternoon. `83ec66d9` carried them and `12266aff` shortened one
line of it so the TQO canon stays under a thousand words.

- `Script: Short After Doctor?`, `Expand After Doctor?`, `Expand After Doctor
  (Cerebras)`, `Parse Expanded After Doctor` and `Script: Final Text` sit
  between `Parse Doctor Verdict` and `Fetch Prior Episodes`. A script the
  doctor left under 1,200 words gets one more expansion of the final text. The
  parse keeps it only if it is longer, keeps the first two sentences and the
  last sentence verbatim, and adds no number; otherwise the doctored text goes
  on and the gate fails it on the floor as before. `Originality Scan` and `DT
  Shim: Prior REST` now read `Script: Final Text` by name.
- `Fetch Prior Episodes` always outputs. The first episode of a show has no
  prior script, the node returned nothing and the run stopped there without
  an error, which test 2361 on NCO row 26 found. Every NCO script would have
  died at that node until one existed.
- `Sources Gate` blanks military identifiers before it reads numerals: form
  numbers such as DD-214, 24 hour times such as 0600 or 1800 hours, and unit
  ordinals such as the 101st. An ordinal after ranked or before percentile is
  still a figure, and MOS codes are left out because 11B reads the same as
  eleven billion. It also refuses a sentence about the future that carries a
  figure and names no approved source.
- `Build Script Prompt`: the section line in both show blocks asks for a
  mechanism, a step or a sourced figure where it asked for "a concrete example
  or number". The canon measurement in `tqo_canon.py` is re-counted.

All of it ran first on an inactive copy, `bNNR1v39mtUktl5D`, then went to the
live workflow by PUT and the copy was archived. Execution 2362 on the copy
wrote NCO row 26's first script: 934 words, 1,501 after the second expansion,
1,494 after the doctor, so the new check passed it through, and the Sources
Gate held it as Error on one invented figure, a "50 person team". The NCO
Presenter Rule held: the script speaks to camera and has no narrator line. The
expansion branch after the doctor has not yet run live; its parse is proven by
`length_after_doctor.test.mjs`. The `12266aff` wording change went live by PUT
without its own copy run, because it is one phrase inside a template literal;
the mirror parses and the canon test counts it.
