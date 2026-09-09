# SYS_OPS: four rulings, the review gate and the receipt canon (v1, 2026-09-09)

Date: 2026-09-09
Ruled by Tee on a multiple choice card, 2026-09-09, at the close of the control
plane arc. Every one of the four took the recommended option.
Supersedes: nothing. Closes four of the items
`SYS_OPS_control-plane-foundations_v1_2026-09-08` left open, and leaves three
of them open.

## What was ruled

| Ruling | Chosen | What it changes |
|---|---|---|
| Where the review of record lives for a close-out PR | Chat is the record | Tee's word in the session is the review. A close-out no longer records a phantom gap when GitHub carries no `reviewed` event, and no session waits on a GitHub review that was never going to arrive. |
| Which receipt shape is canon for status docs | The plurality shape, enforced | `AREA`, `TYPE`, `ARTIFACT`, `DATE`, `DECISIONS`, `FINDINGS`, `OPEN`, `STATUS`, `TOKEN`, checked by `test_devon_receipt_shape.py` rather than described in prose. |
| Whether the API and the presence service keep sharing one HS256 key | Asymmetric tokens | The API signs with a private key, the presence service verifies with the public half and can no longer mint a session for anyone. Queued, not built. |
| How a lawful late event after a receipt is handled | A second receipt law | A late event opens a new receipt instead of breaking the one that stands, so growth stops reading the way tampering reads. Queued, not built. |

## What was built for the receipt canon

`test_devon_receipt_shape.py`, 68 tests. It requires a `## DEVON RECEIPT`
block carrying all nine canon keys, the capture token line verbatim, and a
`DATE` that matches the date in the filename, because a receipt dated
differently from the file it closes makes the dated record unorderable, which
is the one thing the record is for. Extra keys are allowed: a doc with more to
say says it, and the nine are a floor rather than a cage.

Enforcement is by an explicit exemption list of filenames, not by a date
cutoff. A date cutoff can be dodged by giving a new doc an old date in its
name; an exact filename cannot. Two tests keep the list honest. One fails if
the list names a doc that no longer exists, so a stale entry cannot silently
exempt a future file that reuses the name. The other fails if a listed doc
already satisfies the canon, so the backlog cannot quietly stop shrinking.

That second test earned itself on its first run: six docs already satisfied
the canon and were still listed as exempt. They came off, so forty five docs
remain in the backlog and eight are bound today.

## Findings

The count of receipt shapes given to Tee before the ruling was wrong, and the
ruling survived it. The card said three shapes were in use. Read from all
fifty two status docs rather than the three that had been opened, the estate
carries seven distinct key sets across the twelve docs that have a receipt at
all, and forty docs with none. This is the failure the first law names, a count
taken from the lane instead of the estate, and it was the third inference error
of that session. The chosen shape turned out to be better supported than
claimed: it is the plurality at six of the twelve.

`services/devon/receipts.py` parses neither the canon nor any status doc. It
reads a `=== DEVON RECEIPT v1 ===` block with `PLATFORM`, `TITLE`, `SUMMARY`,
`DECIDED`, `BUILT`, `NEXT`, `CANON` and `VERIFY` under a 250 word limit.
`detect_format` returns None for every status doc in the estate. The module is
not wrong, it serves the thread log capture path rather than the status record,
but nothing said so and the two were mistaken for one format.

## What stays open

Three items from the control plane arc were not on the card and are not ruled:

1. Whether the fourth gauntlet pass's closure, author verified after the three
   revise cycles were spent, needs a fifth critic before it is trusted.
2. The owned likeness. The avatar stays a procedural placeholder until Tee
   supplies a rigged head with ARKit blendshapes. No recommendation was offered
   and none should be: it is his likeness.
3. The secret vault. Nothing in the repository generates or stores secrets, on
   purpose, and whether that changes is a design decision rather than a file to
   add quietly.

Two ruled items are queued as their own arcs and were deliberately not started
in the session that took the ruling: asymmetric session tokens, and the second
receipt law. Each needs a migration, a critic and its own PR, and starting
either at the tail of a just closed arc would have been the wrong call.

The receipt backlog is forty five docs. Most of them are handover notes from
August that were never written with a receipt at all, so migrating them means
deciding whether a handover is a status doc, which is worth one pass of Tee's
attention rather than forty guesses.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_rulings-review-gate-and-receipt-canon_v1_2026-09-09
DATE: 2026-09-09
DECISIONS: chat is the review of record for a close-out PR, so a missing GitHub reviewed event is no longer recorded as a gap; the plurality receipt shape is canon for status docs and is enforced by a test rather than described; the API and the presence service move to asymmetric session tokens so the verifier can no longer sign; a lawful late event after a receipt opens a second receipt instead of invalidating the first; all four taken as recommended on a card
FINDINGS: the shape count given before the ruling was wrong, three claimed against seven distinct key sets among twelve receipt bearing docs with forty carrying none, a count taken from the lane instead of the estate; the chosen shape is the plurality at six of twelve so the ruling survived the error; services/devon/receipts.py parses a fourth format that no status doc uses and detect_format returns None for all of them; six docs already satisfied the canon while still listed as exempt, caught by the backlog test on its first run
OPEN: the fifth critic on the fourth gauntlet pass closure; the owned likeness; the secret vault; asymmetric tokens and the second receipt law are ruled but unbuilt, each its own arc with a migration and a critic; forty five status docs remain in the receipt backlog and most are August handovers that may not be status docs at all
STATUS: test_devon_receipt_shape.py passing at 68 tests with forty five docs exempt and eight bound; the control plane close-out receipt migrated to canon; CLAUDE.md carries both process rulings; nothing shipped for the two engineering rulings
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
