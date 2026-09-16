# OS 29 Platform Policy Sensor, assessment chain

`OS 29 - Platform Policy Sensor` is `vpe8TglGmFwz4YRu` on n8n.editforge.online.
It wakes at 06:00, fetches every watched policy page, diffs the normalised text
against the last scan, and when the text has moved it asks a model whether the
change is material to the three shows. A material change is written to Airtable
and emailed. This directory holds the three Code nodes in that assessment
chain. The fourth node between them, `Assess Materiality (Cerebras)`, is an
HTTP Request node with no body worth mirroring: it posts `$json.claudeBody` to
`https://api.cerebras.ai/v1/chat/completions` on the `Cerebras Cloud`
credential (`ENoUSqySnkK0NVsl`), and it carries `onError:
continueRegularOutput` so a failed call reaches `Parse Assessment` instead of
throwing.

| File | Node | What it decides |
|---|---|---|
| `build_assessment_prompt.js` | `Build Assessment Prompt` | The definition of material, the three show descriptions, and the instruction never to invent a removed line |
| `token_budget_assessment.js` | `Token Budget: Assessment` | The output ceiling, and the conversion from the Anthropic shape to the Cerebras shape |
| `parse_assessment.js` | `Parse Assessment` | What is written to Airtable, including what happens when the model does not answer |

## Why it runs on Cerebras

Until 2026-09-16 the model call was an Anthropic node. On the Cloud instance it
ran on n8n Gateway credits, a managed credential billed through the n8n
subscription. The VPS is self hosted and has no gateway, so after the cutover
the node hit Anthropic directly on an own key and failed on every run.

n8n reported that failure as `Bad request - please check your parameters`,
which is n8n's wording for any HTTP 400 from the vendor and reads like a
parameter bug. It was not one. With `onError` removed so the vendor body
surfaced, probe execution 216 returned:

```
"type": "invalid_request_error",
"message": "Your credit balance is too low to access the Anthropic API."
```

request `req_011Cf6L2vyK6pRVWS2LtvRJC`. The key authenticated; the account
behind it had no credits. A different model id returned the identical error
(execution 215, `claude-haiku-4-5-20251001`), which is what ruled the model
string out before the credential was touched.

Tee ruled on 2026-09-16 to move the call to Cerebras `gpt-oss-120b`, the lane
the nine model calls in `TQO FINAL V5` already run on, rather than fund a
second vendor for one node. The swap follows the V5 pattern exactly: the prompt
builder still emits the Anthropic shape, one shim converts it, and one
extraction line in the parser reads either shape.

## The failure direction

`Parse Assessment` fails closed and always has. If the model does not answer,
or answers something unparseable, or the answer is truncated, the row is still
written, as `CHANGE DETECTED, ASSESSMENT FAILED` with the reason attached and
`Changed, unreviewed`. Swallowing it would turn a detected policy change into
silence, which is the one outcome this module exists to prevent.

## Proof

Two throwaway probes ran the four real nodes against seeded diffs, then were
archived. Execution 218, a seeded synthetic media disclosure rule with a
90 day monetisation penalty: `material: true`, gate `disclosure`, all three
shows named. Execution 219, a seeded support hub link: `material: false`, gate
`none`, no shows. Both directions of the gate, not just a 200.

Probe 217 also caught the model writing `non-compliance` with a U+2011
NON-BREAKING HYPHEN into a field Tee reads. `Parse Assessment` now folds
U+2010, U+2011 and U+2212 to an ASCII hyphen on the way out. It deliberately
does not fold em or en dashes: a dash between digits can be a range, and
rewriting one invents a number nobody wrote.

Nothing here executes. n8n holds the graph, the credentials and the schedule.
A change made here has to be applied to the live node, and a change made live
has to be copied back, or this file is a lie about what watches the platforms.
