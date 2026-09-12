---
name: devon-grill
description: Interview Tee to get what only exists in his head into DEVON, one question at a time, and file it as a dated capture with a receipt. Use when he says "grill me", "interview me", "get this out of my head", "capture what I know about X", when a session needs context that no file in the estate holds, when DEVON answers a question with a lane name instead of an answer, or on any scheduled context build. Also use before planning work whose inputs live only in Tee's judgement.
---

# Grilling Tee

DEVON records what already happened. Threads get receipts, jobs get ledger
rows, the estate gets reconciled. Nothing in it ever asks Tee a question.

That leaves a hole with a known shape. Tee gives minimal direction by
preference, and a system that only records what was already said will stay
starved of exactly the context that makes the rest of it worth having. The
capture protocol cannot reach a decision he made and never narrated.

This skill is the missing direction of travel. It interviews him and files the
answers where the rest of the estate can read them.

## Rule zero: you are a recorder, not an author

Everything the first law says about claims applies here twice over, because
here the source is a person and there is no file to check him against.

- **Write what he said, not what he meant.** Numbers, names, paths, dates and
  lines of dialogue go down as spoken. If a phrasing is ambiguous, ask. Never
  resolve it yourself and never smooth it.
- **Mark inference as inference.** If the capture needs a bridging sentence,
  it goes under `Inferred, not stated` and it says who inferred it.
- **An unanswered question is a finding.** It goes in `Open threads`, not
  quietly nowhere, and not filled in with the plausible answer.
- **Do not ask what the repo answers.** Check the estate first. Asking Tee for
  the alembic head is spending his attention on something `alembic heads`
  settles, and it teaches him the interview is not worth his time.

## Running a session

**1. Name the topic and open the file first.**

One topic per session. If he said "grill me" with no topic, offer three drawn
from what the estate is visibly thin on, and let him pick.

Create `docs/devon/CAPTURE_<topic-slug>_<YYYY-MM-DD>.md` before the first
question and append to it as you go. A session that dies halfway must leave
everything it already got on disk. Do not buffer the transcript and write at
the end.

The `docs/devon/` directory is swept flat by `test_devon_integrity.py`, so the
capture lives there directly rather than in a subdirectory, and it carries no
em or en dashes.

**2. Ask one question. Wait.**

Never a list. He is usually on an iPhone, and a numbered set of five questions
gets one answer to the easiest of them.

**3. Follow the specific, refuse the general.**

The whole value is in the second and third question, not the first.

| He says | Weak follow up | The one to ask |
|---|---|---|
| "the render lane is slow" | "how could we speed it up?" | "which step, and slow measured against what?" |
| "that client was a bad fit" | "what makes a good fit?" | "what did you see in the first call that you now know was the tell?" |
| "we decided to go presenter led" | "why?" | "what were you doing instead when you decided, and what would have to be true to go back?" |

Push once on a thin answer. Push twice on a thin answer to a question that
would change a decision. Never push a third time; note it as an open thread
and move on. Relentless means thorough, not extractive, and a session he
resents is one he will not run again.

**4. Know when to stop.**

Stop when the topic is exhausted, when he says stop, or at roughly twenty
minutes. A capture he finished beats a longer one he abandoned.

## What a capture file holds

```markdown
# Capture: <topic>

Interviewed 2026-09-07. Session <n> on this topic.

## What Tee said

### <question as asked>
<his answer, in his words>

## Decisions this settles
- <the ruling, and what it now overrides>

## Inferred, not stated
- <bridge>. Inferred by Claude on 2026-09-07, not confirmed.

## Open threads
- <question asked, not answered, or pushed past>
- <question the answers raised that there was no time for>

## Contradicts
- <any estate record this disagrees with, named by path>

DEVON RECEIPT
...
```

`Contradicts` is not optional. If an answer disagrees with a file, name the
file. Do not reconcile the two yourself: that is `devon-precedence`'s job and
it is a ruling, not a merge. Surfacing it is the whole point.

## Closing

Every session ends with a DEVON RECEIPT block carrying the capture token, per
`devon-thread-log`. A capture with no receipt did not happen as far as the rest
of DEVON is concerned.

Then tell him, in one line, what the next session on this topic should cover.

## Traps

- **Confirmation theater.** Reading his answer back to him as a summary and
  asking "is that right?" burns a turn and gets "yes". Ask the next real
  question instead. Read back only when you genuinely could not parse him.
- **Interviewing the plan instead of the person.** `grill-with-docs` already
  grills a plan or a design and produces ADRs. This skill grills Tee. If the
  subject is a document, that skill is the right one.
- **Filing to the wrong shelf.** `SYS_OPS_*` files are dated status records of
  what the estate did. A capture is what Tee knows. Different prefix, same
  directory, and never merge one into the other.
- **Treating the transcript as canon.** A capture is a primary source, not a
  ruling. It records that Tee said something on a date. Whether it now governs
  is a separate question and `devon-precedence` answers it.
