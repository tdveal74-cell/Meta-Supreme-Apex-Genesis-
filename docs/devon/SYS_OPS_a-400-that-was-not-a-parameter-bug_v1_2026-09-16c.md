# A 400 that was not a parameter bug

2026-09-16. OS 29, the platform policy sensor, has been detecting policy changes
on the VPS and failing to assess any of them. This closes that, and records the
error shape that cost the time, because it will happen again on another node.

## What was broken

`Assess Materiality (Claude)` returned `Bad request - please check your
parameters` on every run. That sentence is n8n's, not Anthropic's. n8n prints it
for any HTTP 400 the vendor returns, whatever the vendor said, and it reads like
a malformed request. Three things were suspected on the strength of it: the
prompt, the token ceiling, and the model id. None of them were the cause.

The node carried `onError: continueRegularOutput`, which is correct for a sensor
and also why the vendor's own message never reached a log. Removing it on a
throwaway copy made the real body visible on the first run.

## The sequence, and what each step ruled out

A minimal probe workflow, three nodes, a manual trigger and a seed emitting the
trivial prompt `Reply with exactly {"ok":true}`, then the exact model node copied
from OS 29 on the same credential.

Execution 214 returned the same error on that trivial prompt, which ruled out the
prompt and the token ceiling. Execution 215 swapped the model id to
`claude-haiku-4-5-20251001` and returned the identical error, which ruled out the
model string. Execution 216, with `onError` removed, returned the answer:

```
"type": "invalid_request_error",
"message": "Your credit balance is too low to access the Anthropic API.
            Please go to Plans & Billing to upgrade or purchase credits."
```

request `req_011Cf6L2vyK6pRVWS2LtvRJC`.

The credential was never the problem. A key that does not authenticate returns
401 and an authentication error; a billing message means the key resolved to a
real account. The account had no credits.

Why it worked on Cloud and not here: the Cloud node ran on
`__aiGatewayManaged: true`, an n8n Gateway managed credential billed through the
n8n subscription. Gateway credits are a Cloud only feature. Self hosted n8n has
no gateway, so after the 2026-09-15 cutover the same node hit Anthropic directly
on an own key for the first time.

## The ruling

Tee ruled to point the node at Cerebras rather than fund a second vendor for one
call. `TQO FINAL V5` already runs nine model calls on Cerebras `gpt-oss-120b` and
the credential `Cerebras Cloud` (`ENoUSqySnkK0NVsl`) was already on the instance.
OS 29 has exactly one model node, so this is a single swap.

The swap follows the V5 pattern rather than inventing one. `Build Assessment
Prompt` still emits the Anthropic shape. A new Code node, `Token Budget:
Assessment`, converts it to the Cerebras shape, sets `max_completion_tokens` to
8000 and asks for `response_format: json_object`. `Assess Materiality
(Cerebras)` is an HTTP Request node posting that body, carrying the same
`onError: continueRegularOutput` the node it replaced carried. `Parse
Assessment` now reads either the OpenAI chat shape or the Anthropic content
blocks, so a swap back needs no further edit.

The generous ceiling is not carelessness. `max_completion_tokens` on Cerebras
includes the model's reasoning tokens, and a truncated response fails closed to
a held row a human has to read.

## The proof

A second throwaway workflow ran the four real nodes, pulled from the live
workflow rather than retyped, against two seeded diffs. Both probes are
archived.

Execution 218, seeded with a synthetic media disclosure rule carrying a 90 day
monetisation penalty: `material: true`, gate `disclosure`, confidence high, and
all three shows named, which is the correct read because all three publish with
an owned likeness and an owned cloned voice.

Execution 219, seeded with a link to a creator support hub: `material: false`,
gate `none`, no shows, confidence high.

Both directions of the gate, not a 200 and a shrug. A sensor that answers
material to everything is as useless as one that answers nothing.

## What the probe caught that nobody was looking for

Execution 217 wrote `non-compliance` into the headline with a U+2011
NON-BREAKING HYPHEN, not an ASCII hyphen. That field goes to Airtable and into
an email Tee reads.

`Parse Assessment` now folds U+2010, U+2011 and U+2212 to an ASCII hyphen on
every string it writes. Those three are the same character as a hyphen
typographically, so the fold is lossless.

Em and en dashes are deliberately not folded. This repository already learned
that lesson the expensive way: `120 [en dash] 30% above my last one` became
`120-30%`, a number nobody wrote. The system prompt asks the model not to emit
them, and if one lands it lands visible in a line a human reads rather than
silently rewritten into a different figure.

## What did not change

`Parse Assessment` fails closed and did before. If the model does not answer, or
answers something unparseable, or the answer is truncated, the change is still
written, as `CHANGE DETECTED, ASSESSMENT FAILED` with the reason attached and
`Changed, unreviewed`. Truncation is now named explicitly instead of arriving as
a mangled brace, which changes the message and not the direction.

Firecrawl is untouched. The credential `Nld2jqeJyTfv8jNh` still holds the key
Tee rotated, and updating it is a UI job, not a chat job.

## The lesson worth keeping

An HTTP 400 relayed by a tool is the tool's sentence, not the vendor's. Before
believing the words, make the vendor's own body visible. Here that was one
setting removed on a copy, and it answered in one run a question three runs of
parameter guessing had not.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_a-400-that-was-not-a-parameter-bug_v1_2026-09-16c.md
DATE: 2026-09-16
DECISIONS: Tee ruled to point the OS 29 assessment call at Cerebras gpt-oss-120b rather than fund the Anthropic account for one node, on the reading that the V5 lane is already paid for and this workflow has exactly one model node. The swap follows the V5 pattern: the prompt builder keeps emitting the Anthropic shape, one shim converts it, one extraction line in the parser reads either shape. The unambiguous typographic hyphens are folded to ASCII deterministically; em and en dashes are left alone because folding a dash between digits invents a number.
FINDINGS: The error n8n reported as "Bad request - please check your parameters" was an Anthropic 400 whose body read "Your credit balance is too low to access the Anthropic API", request req_011Cf6L2vyK6pRVWS2LtvRJC, visible only after onError continueRegularOutput was removed on a throwaway copy, execution 216. The credential authenticates; the account behind it is empty. A different model id returned the identical error on execution 215, which ruled out the model string before the credential was touched. The node worked on Cloud because it ran on n8n Gateway managed credits, a Cloud only feature that self hosted n8n does not have, so the 2026-09-15 cutover was what exposed it. Probe 217 also showed the model writing a U+2011 NON-BREAKING HYPHEN into a field that reaches Airtable and email.
OPEN: The Anthropic account is still unfunded, which is fine while nothing on the VPS calls it and a trap for the next node that does. The Firecrawl credential Nld2jqeJyTfv8jNh still holds the rotated key and is Tee's to update in the n8n UI. Only the three Code nodes of the assessment chain are mirrored; the other nineteen OS 29 nodes are live only.
STATUS: OS 29 runs the materiality assessment on Cerebras, live and active as activeVersionId b37bfd16, proven in both directions on the real credential by executions 218 material and 219 not material, with both throwaway probes archived and the changed chain versioned in the repository for the first time.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
