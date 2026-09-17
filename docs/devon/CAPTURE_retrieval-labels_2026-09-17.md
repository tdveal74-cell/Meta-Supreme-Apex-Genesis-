# Capture: retrieval labels, the questions Tee actually asks DEVON

Interviewed 2026-09-17. Session 1 on this topic.

## Why this session exists

`scripts/measure_retrieval.py` scores retrieval on a real corpus and refuses to
run without labelled questions: a question Tee would really ask, paired with the
note or episode that should answer it. Only he can supply the pairing, and the
script says so in its own docstring rather than scoring itself against its own
guesses.

Every retrieval number this estate has came from a twelve document corpus a
session wrote itself, with queries written to have obvious answers. That is the
bias this capture exists to avoid. The queries that matter are the ones that
share NO vocabulary with the answer, because those are the ones the lexical lane
cannot reach and the only ones an embedding vendor would buy.

Tee ruled on 2026-09-17, on a card, to grill for these rather than write them
cold, on the grounds that a list written from memory skews toward questions with
obvious answers.

## What Tee said

### Q1. Think of the last time you went looking for something you knew you had already written down or said on air, and had to go digging. What were you trying to find, and what did you type to look for it?

REDACTED BY CLAUDE, AND THE REDACTION IS THE POINT.

His answer described an account recovery hunt. He needed the original account
setup email for a service, could not reach it directly, and reached the outcome
by a different route through another record entirely.

The verbatim answer is NOT written here. This repository is public, and an
account recovery path tied to a named vendor and a named person is material that
helps someone social engineer that account. The first draft of this section
quoted him in full and the write was refused by the harness before it landed,
which was the correct call and one this session should have made itself.

What the measurement actually needs from this answer is the QUERY SHAPE, and
that is recordable without any of the rest:

    intent    find the original account setup or signup email for a vendor
    surface   a mail client, searched by vendor name
    corpus    Gmail
    outcome   the direct search did not settle it; he fell back to another
              record entirely

The vendor name, the financial record, the identifier and the recovery step are
deliberately absent. Ask Tee directly if a later session needs them; they do not
belong in a public file.

## Decisions this settles

Both were put to Tee on a card and both came back "what you recommend", so he
delegated rather than picked. Recorded that way rather than as his choice,
because the distinction matters if either turns out wrong.

- **The grill stays on notes and episodes.** Claude's recommendation, taken
  2026-09-17. Ten labels against the corpus that exists, so the embeddings
  funding question gets a real number. The cost is stated and accepted: the
  first answer says Tee's actual searching happens elsewhere, so the number
  will describe a corpus he may not search often. The mail finding stays filed
  for a later arc rather than being chased now.
- **Captures redact by default.** Claude's recommendation, taken 2026-09-17.
  Operational specifics never go into this repository: no service names tied to
  accounts, no financial records, no recovery routes. The capture records the
  shape and says what it withheld. A later session that needs the detail asks
  Tee directly.

## Inferred, not stated

- The first real digging episode Tee produced is one DEVON's retrieval lane
  CANNOT serve at any embedding quality. `knowledge_items` holds notes,
  documents and episode transcripts, and it holds no mail. So the corpus the
  retrieval measurement scores is not the corpus this search needed. Inferred by
  Claude on 2026-09-17 from the answer plus the schema, not confirmed with Tee.
- Falling back to a second, unrelated record is a workaround for a search that
  failed rather than a search that succeeded. That suggests what is worth
  measuring first is whether the lane can answer a question AT ALL, before how
  well it ranks. Inferred by Claude on 2026-09-17, not confirmed.
- The interview question may be aimed at the wrong thing. It asked about notes
  and episodes; the honest answer was about operational recall across mail and
  records. Whether the topic widens is Tee's call, not a reframe a session makes
  on its own. Inferred by Claude on 2026-09-17, not confirmed.

## Open threads

- What did he actually type into the mail search, and did it return the email?
  Not yet asked, because the answer to Q1 raised whether the topic is aimed at
  the right corpus and that is a ruling rather than a follow up.
- Nine more labelled questions to go.
- Whether the capture should hold the redacted specifics at all, in some
  non public place, was offered on the card and not chosen. Redact by default
  won instead, so there is no private destination and the detail lives only in
  Tee's head. That is a deliberate gap rather than an oversight.
- The mail corpus finding is parked, not resolved. `knowledge_items` still
  cannot answer the one real query Tee produced.

## Contradicts

- Nothing in the estate's records yet. The tension is with the SCOPE of
  `scripts/measure_retrieval.py`, which scores `knowledge_items` and nothing
  else, while the first real query Tee named lives in mail. That is a gap in
  what the tool covers rather than a record that disagrees with another record.

## DEVON RECEIPT

AREA: DEVON retrieval
TYPE: capture
ARTIFACT: docs/devon/CAPTURE_retrieval-labels_2026-09-17.md
DATE: 2026-09-17
DECISIONS: pending, session in progress
FINDINGS: the first real digging episode Tee named is operational recall across mail, not the notes and episodes corpus the retrieval measurement scores; his verbatim answer was redacted because this repository is public
OPEN: nine more labelled questions
STATUS: in progress, one answer recorded, two rulings delegated to Claude and taken
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
