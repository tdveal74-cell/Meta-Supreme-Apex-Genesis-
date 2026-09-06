# SYS_OPS: the draft parser, two quarantines and the ruling that ended them

Status record for `n8n/devon/drive-draft-writer/parse_draft.js`, the Code node
that turns the language lane's answer into the text of a Google Doc draft.
Written 2026-09-06. Supersedes section 12 of
`SYS_OPS_devon-autonomy-driver_v1_2026-09-05.md`, which now points here.

## What the node is for

The Drive Draft Writer asks Cerebras for a draft and writes the answer straight
into a Google Doc in a show's `01_SCRIPTS` folder. Nothing renders the text and
nobody reads it before it lands. This node is the only thing between the model's
answer and Tee's Drive.

## What went wrong, twice, in one night

The model writes for a markdown reader even when the system prompt asks for
plain text. The first live draft (job `01M1SN5X4ETKEPPCC4JT61TE5V`, written
2026-09-06T01:58:58Z) carried 25 escaped bullet markers, 9 escaped ordered
markers and 10 non breaking hyphens. It carried zero em or en dashes.

Two versions were written to clean that up. Both were quarantined by a gauntlet
cycle, and both failed the same way: a rule that decided what a dash MEANT.

### v1, shipped in PR #139, quarantined by cycle 6

The dash class used `\s` on both sides, and `\s` matches a newline. A dash
opening a line ate the line break. A block of dialogue collapsed into one run on
line and so did a dash bulleted checklist. Drafts land in a script folder, which
is exactly where a line opening dash lives.

### v2, shipped in PR #141, quarantined by cycle 7

v2 fixed the newline crossing and introduced worse. Nine corruptions were
reproduced against the committed file:

| input | output |
|---|---|
| `The offer was 120 [em dash] 30% above my last one.` | `The offer was 120-30% above my last one.` |
| `We shipped in 2023 [em dash] 12 months of work.` | `We shipped in 2023-12 months of work.` |
| `Revenue grew 40% [em dash] the biggest jump yet.` | `Revenue grew 40% the biggest jump yet.` |
| `The package [em dash] $185,000 base [em dash] was the number.` | `The package $185,000 base, was the number.` |
| `TEE: But I thought[em dash]` | `TEE: But I thought` |
| `The rule is simple: [em dash] never negotiate.` | `The rule is simple:, never negotiate.` |
| `In the end, [em dash] we ship.` | `In the end,, we ship.` |
| `const label = ok ? "pass" : "fail";` | `const label = ok? "pass": "fail";` |
| `Arsenal won 2 : 1 and the show starts at 9 : 30.` | `Arsenal won 2: 1 and the show starts at 9: 30.` |

The first two are the ones that mattered. `DASH_NUM_RANGE` was added in v2 on
the speculation that digits either side of a dash mean a range. In career
strategy content they usually do not, and the rule fabricated a number in a
document nobody reads before it lands.

Three structural defects came with them:

- `TRAILING_SPACE` and `SPACE_BEFORE_PUNCT` were quadratic on a run of spaces:
  10k spaces 272 ms, 20k 924 ms, 40k 3.7 s, 80k 14.9 s, four times the cost per
  doubling, on input the model controls. Reachable without a space run in the
  answer, because `DASH_REST` collapsed a repetition loop into one first: a 200k
  em dash loop cost 52.8 seconds and then wrote the document.
- A 130 line answer of nothing but code fences scored 130 raw words, cleared the
  120 word floor, and wrote a document whose body was the empty string. The
  floor was measured before normalisation and never rechecked after it.
- `draft_words` understated the delivered document by exactly 28 words, the
  length of the header it did not count.

## The ruling, 2026-09-06

Tee ruled: **stop scrubbing, start refusing.**

The node now keeps only transformations that cannot change meaning, and refuses
the whole draft when an em or en dash is present. The lane retries. The system
prompt is what has to earn the pass.

Safe, and why each one cannot alter meaning:

| transformation | why it is safe |
|---|---|
| U+00A0 to a space | an invisible space becomes a visible one |
| U+00AD removed | a soft hyphen is invisible and advisory |
| U+2010 and U+2011 to `-` | these ARE hyphens; only the code point changes |
| a fence line removed | the marker is markup, the code inside is kept |
| a leading backslash before a list marker removed | markdown escaping, not text |
| trailing whitespace trimmed | end of line whitespace carries nothing |

Deliberately untouched: U+2212 (the minus sign, arithmetic), U+2015 and U+2012
(neither an em nor an en dash; v2 folded them on speculation and broke dialogue
and phone numbers), and indentation inside a code sample.

Order is load bearing. Character normalisation runs BEFORE the escape strip,
because the hyphen rule turns `\<U+2010> First point` into `\- First point`,
which is the shape the escape strip is looking for. v2 ran them the other way
and the backslash reached Drive.

## The root cause, and the sentence that was wrong about it

Sections of the earlier record said the system prompt behind these defects "is
not in this repository at all". **That was false**, and it was written three
times before anyone read the workflow. The prompt is version controlled at
`n8n/devon/drive-draft-writer/validate_and_plan.js`, in the `system` array.

It already said "No markdown symbols, no tables, no code fences, no emoji. Never
use an em dash or an en dash; restructure the sentence instead."

So the finding is not that the prompt was unversioned. It is that the prompt
said the right thing and the model honoured one clause of it and ignored three.
The dash rule was obeyed. The markdown rules were not.

That is why refusing on a dash is affordable: the model already does not emit
them, so the refusal is insurance rather than a loop. And it is why the prompt
was restructured in the same change: the four format rules are now numbered, on
their own lines, each naming the exact wrong output observed in the live draft,
and rule 1 states the cost (the whole answer is rejected).

## Verification

Every prior corruption now refuses. Every clean input survives:

- 9 v2 corruption cases and the v1 dialogue collapse: all REFUSE
- code indentation, ternaries, scores and times, Windows paths, a regex written
  in prose, inline backticks, U+2212, U+2015, U+2012: all pass through unchanged
- escaped markers, unicode hyphens and soft hyphens: correctly normalised,
  including the `\<U+2010>` and `\<NBSP>` combinations v2 got wrong
- idempotency: 0 non idempotent out of 2000 mixed cases (v2 had 877 in 200k)
- the quadratic is gone: 640k spaces in 2.3 ms, growth linear. `trimEnd` is a
  native backward scan and cannot backtrack. Rewriting the regex per line does
  NOT fix it, which is what the first attempt at this fix did
- the 200k em dash loop: 1.8 ms, then refused
- the markup only answer: rawWords 130 clears the floor, bodyWords 0, second
  gate refuses
- 50k fuzz cases: 0 exceptions
- `node --check` passes; 0 non-ASCII bytes in both files

## The lesson worth keeping

Both quarantined versions passed every gate the estate had. CI was green for
both. The tests do not touch this file's behaviour, and the parse guard added in
the same arc only proves it is syntactically valid.

What found them was a fresh critic with no build context that executed
adversarial input against the actual code. What they had in common was that the
author widened a rule on a guess about intent. A guess that lands unread in a
script folder is worse than no draft at all.

## Open

- The behavioural proof that refusing is affordable is one live draft. If the
  refusal rate turns out to be high, the answer is the prompt, not a scrub rule.
- `draft_normalised` now reports per rule fire counts on every written draft.
  That is the signal for whether the prompt is being honoured over time, and
  nothing reads it yet.
