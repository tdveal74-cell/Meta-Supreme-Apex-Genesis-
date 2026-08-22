# DEVON

Tee's second brain, running inside Meta Supreme Apex Genesis.

DEVON already existed as a knowledge system spread across Google Drive, Notion,
Airtable, n8n and GitHub, governed by doctrine documents in the vault's
`_Devon Core` folder. The assistant surface was rebuilt from the Jarvis voice
assistant at `github.com/Vannu07/jarvis` (commit `21b9d63`) and hardened against
the Flagship Bar. This document says what exists here, what it will not do, and
how to use it.

## The one thing to understand first

**DEVON parses, plans, validates and gates. He never executes.**

A capture returns a filing plan. An effect returns an approval request. Nothing
in `services/devon/` opens a socket, spawns a process, or writes to Drive,
Notion, Airtable or n8n. A test walks the import graph of every module in the
package and fails if a network or subprocess capability appears
(`test_devon_integrity.py::test_the_package_cannot_reach_the_network_or_spawn_a_process`).

That split is not decoration. A component that cannot execute cannot be argued
into executing, and it means importing DEVON is free of consequences.

## Why the doctrine is code

The vault's governing documents kept being violated by threads that had read
them. The naming convention forked twice in one day, sixty seconds apart. The
filing laws forked fourteen seconds apart. Both times inside the document whose
job was preventing forks, by threads following the rules correctly.

Discipline was never the missing piece. Prose does not enforce. A function that
refuses does. Every module here compiles one doctrine document into checks that
run, and each declares the Drive id it came from so a reader can go and check
the original rather than trusting the copy.

## Layout

| Module | Compiles | From |
|---|---|---|
| `areas.py` | the nine Areas and the trust ladder | `AREAS.md` |
| `naming.py` | `AREA_TYPE_slug_vN_DATE` | naming convention v4 |
| `precedence.py` | which draft is current, and when nothing wins | precedence doctrine v2 |
| `filing.py` | the eight filing laws | filing laws v3 |
| `receipts.py` | the DEVON RECEIPT, both formats | capture protocol, standing instructions v3 |
| `vault.py` | the Drive, Notion, Airtable and n8n map | master directory v6, context pill v16 |
| `flagship.py` | the ship gate | flagship bar v01 |
| `persona.py` | who DEVON is and the ten hard rules | Devon Persona, standing instructions v3 |
| `commands.py` | the command language and the device intents | Devon Command Language, upstream Jarvis |
| `approval.py` | the gate every high impact action passes | n8n Approval Queue `syRVj0G47mA1b0Xn` |
| `assistant.py` | DEVON himself | all of the above |

## The command language

Say these in any surface. The wake word is optional and stripped once, leading
only, so "Devon, remember Devon owes me a callback" captures the sentence rather
than eating the name out of it.

| Say this | What happens | Lands in |
|---|---|---|
| `Devon, remember...` | captures, tagged and filed | Notion Inbox, Notes and Ideas |
| `Devon, add a task...` | creates a task | Notion Tasks |
| `Devon, what's on my plate?` | reads back tasks, deadlines, status | reads |
| `Devon, start a project called...` | creates a project record | Notion Projects and Goals |
| `Devon, status report` | project rollup | reads |
| `Devon, new episode idea...` | files into the pipeline | Airtable Podcast HQ, Idea stage |
| `Devon, brief me` | on demand briefing | reads |
| `Devon, log this thread` or `receipt` | emits and files a receipt | Notion Thread Log |
| `Devon, what do we already know about X?` | queries the log before answering | reads |
| `Devon, refresh my dashboard` | regenerates the HUD snapshot | session, not Drive |

Plus the device intents carried over from Jarvis: time, date, weather, news,
search, YouTube, open an app, screenshot, send a message, shutdown, restart.

## The nine Areas

`TQO` `Podcast` `NCO` `ACX` `Health` `Money` `Family` `Learning` `Systems`

ACX was ruled the ninth on 2026-08-20. Anything saying eight is stale.

Two vocabularies name the same nine and they are not identical. The Podcast Area
files as `TSWS`. The Systems Area files as `SYS`. Code that assumes one
vocabulary silently misfiles those two, so both are held and `normalize_label`
and `normalize_code` convert between them.

**A supplied Area is never trusted.** Whatever a model returns is validated
against the nine and discarded if it is not one of them, falling back to keyword
matching. Declining is a correct answer. A confident wrong tag is worse than no
tag, because a wrong tag is permanent and silent while an absent tag is visible
in the triage queue.

Never add an Area without Tee's ruling. The cost is not the label, it is the
four place update (Notion, Airtable, the thread log skill, Drive) and the
permanent risk that one surface gets missed and the index quietly fractures.

## Effects and the approval gate

These intents cannot run without a human ruling: `shutdown`, `restart`,
`send_message`, `open_app`, `take_screenshot`.

Asking for one raises a request and returns its id. Nothing runs. The request
carries a mandatory `what_happens`, because an approver cannot consent to an
effect nobody described, and a request without one is refused at the door.

The gate is modelled on the live n8n Approval Queue and keeps its properties:

- Single use token, 72 hour expiry, compared in constant time
- Only a hash of the token is stored, so a store dump holds nothing usable
- Fails closed by data shape: every refusal resolves to the sentinel `NO_MATCH`,
  which matches no record, so a mis-wired caller writes nothing rather than
  writing something
- Every refusal names its reason. A refusal nobody hears is an approval

## Cerebras enrichment

Optional. Cerebras is already live in the studio's capture lane (credential
`Cerebras Cloud YTVk8Dq2gYPAmUim`, model `gpt-oss-120b`, measured at 42ms), and
the same lane is available here through the platform's provider abstraction.

```
CEREBRAS_API_KEY=...
ENRICHMENT_PROVIDER=cerebras     # tag captures with an Area and a summary
DEFAULT_AI_PROVIDER=cerebras     # optional: run the whole Council on it too
```

The two settings are separate on purpose. Enrichment is high volume, latency
sensitive and mechanical, so it belongs on the cheapest model that can do it,
while the Council keeps whichever model was chosen for judgement. Routing
mechanical work downward is most of the volume in a studio this size. Setting
only `ENRICHMENT_PROVIDER` is the common case.

`services/intelligence/enrichment.py` asks the model for an Area and a one line
summary, then puts the answer through the same trust ladder: validated against
the nine, discarded otherwise, keywords as fallback. The model is allowed to
decline, and a decline is recorded as a decline rather than as an absence.

Enrichment lives in `services/intelligence`, not `services/devon`, because it
needs a provider and DEVON must stay network free. The dependency runs
intelligence to devon, never the reverse.

The recorded free tier allowance is tight: 5 requests per minute, 150 per hour,
2400 per day, 1,000,000 tokens per day. A local limiter refuses before the call
and names which window is exhausted, because a vendor 429 arrives as a retryable
error and the base class would retry it into the same wall.

Cerebras is a text model and cannot tag images. That is a stated limit, and
`refuse_image_enrichment` says so rather than passing an identifier to a text
model and accepting whatever comes back.

## Running it

The zero key path, which is the supported runtime:

```bash
pip install fastapi uvicorn pydantic pytest
python3 -m pytest test_devon_*.py -q
uvicorn standalone_api:app --reload --port 8000
```

| Route | Purpose |
|---|---|
| `GET /devon` | identity, hard rules, and what the surface will not do |
| `POST /devon/command` | route one utterance |
| `GET /devon/areas` | the nine, with both vocabularies |
| `GET /devon/approvals` | what is awaiting a ruling |
| `POST /devon/approvals/decide` | rule on a pending request |
| `POST /devon/receipt/parse` | read and validate either receipt format |
| `POST /devon/naming/validate` | check a filename |
| `POST /devon/naming/build` | build a conforming filename |
| `POST /devon/precedence/resolve` | decide which draft is current |
| `POST /devon/filing/check` | run the filing laws against a proposed write |
| `GET /devon/vault` | the second brain map |
| `GET /devon/flagship` | the ship gate |

The approval queue is process local. A request raised on one worker is not
visible to another. That is correct for a single operator and is stated here
rather than discovered later. Swap in a shared store through the
`ApprovalStore` protocol before running more than one worker.

## What is not here

Stated plainly so nobody assumes otherwise.

- **No live reads.** DEVON does not open Drive, Notion, Airtable or n8n. Asked
  for a briefing he names the lane that owns the data and says he has not read
  it, rather than inventing your own numbers back at you.
- **No voice loop.** The upstream speech recognition, text to speech, face auth
  and hotword detection were not carried over. They need a microphone, a camera
  and a desktop session, and none of them survived the audit unchanged. See
  `FLAGSHIP_AUDIT.md`.
- **No writes.** Every capture is a plan. The caller executes.

## The ruled word list, and an objection logged once

Voice standard v2 rules a word list binding everywhere. The list includes the
function words `it`, `that`, `can` and `could`, which no English prose can
satisfy, and it lists `realm` twice. Enforcing it literally rejects every draft
including the standard's own text.

So this package enforces the punctuation bans, which are unambiguous and
checkable, and carries the word list for advisory use rather than as a gate. The
em dash ban is enforced on every source file and every document in this folder
by a test.

Per hard rule 5, the objection is logged once and the ruling stands. The list
travels unedited in `SYS_SPEC_voice-standard_v2` for the `tee-voice` skill to
apply with its own exempt categories.

## The console

`docs/devon/assets/SYS_OPS_devon-console_v2_2026-08-22.html`

A single file HUD over everything above: the vault rail, doctrine versions, the
nine Areas as a brain map, the Council's nine seats, the eight filing laws, the
approval gate, the automations, and what is currently blocked. It opens in any
browser with no server and no keys.

The command bar is the useful part rather than the decorative one. Type a
command and it parses against the same intent set and the same confidence floors
as `commands.py`, then shows what DEVON would do: a capture resolves an Area and
builds a conforming filename, a gated effect raises an approval and runs
nothing, and a half heard sentence is declined rather than guessed at.

**It is a snapshot and it says so at the top.** The panels are rendered from the
DEVON modules at build time. Drive, Notion, Airtable and n8n were not read to
draw it, so a number here is only as current as the build. That warning is not
decoration: the vault's own rule is that a regenerated HUD lives where it was
generated and the vault stays stale until someone saves it back.

Regenerate by rebuilding the state and re-injecting it. The filename follows the
convention and was built by `naming.build_filename` rather than typed.

### Voice

v2 makes the console talk. It uses the browser's own Web Speech API, so there is
no key, no service and no audio leaving the machine.

**Speaking.** DEVON answers aloud through speech synthesis. The voice, pace and a
mute toggle sit under the transcript. Browsers refuse to speak before a user
gesture, so the greeting is written immediately and voiced on the first click
rather than failing silently.

**Listening.** The orb starts speech recognition. Interim words appear as he
hears them, and the final phrase goes through the same router as the typed line.
Recognition exists in Chrome, Edge and Safari and does not in Firefox, and a
sandboxed frame may refuse microphone permission. Both cases say so plainly and
leave the typed line working, because a console that silently stops listening is
worse than one that never offered.

**The gate is live.** A gated command raises a real request with an id, a stated
consequence, a single use token, a 72 hour countdown and APPROVE or REFUSE
buttons. Ruling on it moves the record to the history strip. Every refusal path
resolves to `NO_MATCH`, the same sentinel the Python queue uses.

**The register.** Lines are drawn from a small set per outcome so repeated
commands do not read as a recording. All of them hold the persona's boundary:
the warmth is in courtesy and in unhurried sentence rhythm, never in phonetic
dialect spelling. If a line would read as a stereotype rather than a person it
is wrong, and that constraint is load bearing rather than decorative.

He also stays inside the hard rules while talking. He never says a thing ran when
it did not, he hands every ruling back, and asked for state he has not read he
says so rather than inventing a number in a friendly voice.
