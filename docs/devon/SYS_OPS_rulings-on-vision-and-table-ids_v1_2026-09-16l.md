# Rulings: the vision root, the spend ratio, the lane door, table ids, OpenRouter

Tee ruled on four open items from the vision arc, on inline cards, on
2026-09-16, then picked the vision backend in the same session. Three were
work and are done here. One was a decision to change nothing, which is
recorded so nobody reopens it. One is scheduled rather than started.

The filename carries no count on purpose. This doc was named for four rulings
and a fifth arrived twenty minutes later.

## Ruling 1: a dedicated inbox, not the working tree

`vision.describe` refused every image because `VISION_IMAGE_ROOT` was unset.
The three candidates put to Tee were a dedicated inbox directory, the render
worker's output so DEVON could grade his own frames, and leaving it unset.

He took the inbox. `var/vision-inbox/` is now in the checkout, tracked through
its README so a fresh clone has somewhere for the root to point, with the
frames inside it ignored by git. The reason for the choice is in the README
rather than only here: the root guard, the traversal guard and the extension
guard all still apply inside that directory, and pointing them at a directory
that holds nothing but frames means a bug which slips all three has nothing
interesting to reach.

The code default stays `None`. A deployment that has not set the variable still
refuses every call and says so, because what writes into that directory on a
Railway container is a deployment decision and not something a default should
assume.

## Ruling 2: fix the spend ratio now

`MeteredVisionProvider` recorded whatever token counts the vendor reported. The
017 ledger has no column for cost, model, provider or modality, so a frame and
a paragraph of the same token count spent the same against the daily cap. That
was not a missing feature, it was a silent assumption that a vendor prices an
image token like a text one.

It is now a named ratio. `VISION_INPUT_TOKEN_WEIGHT` multiplies the input
recorded against the cap and defaults to 1.0, which records exactly what
shipped, so no existing account is re-priced by this change. A vendor that
prices image input above text takes its real ratio.

Four properties, each with a test that was proven to fail when the property was
removed from the source:

- The weight prices image INPUT only. Output is text and is charged as text,
  because weighting it too would be a second unearned multiplier.
- Rounding is up, so rounding never moves in the account's favour.
- A weight below parity is refused twice: the config validator raises at start
  up, and the recorder floors at the vendor's own number for a value set after
  start up or patched in a test.
- The response still reports the vendor's number. The weight is an accounting
  ratio and not a claim about what the vendor said, so a receipt carrying an
  inflated figure would be a lie about the call.

No number was invented for the default. 1.0 is parity and is honest about being
parity; the real ratio is vendor specific and belongs to whoever reads that
vendor's price list.

## Ruling 3: the lane keeps its raw webhook

The vision lane is reached by posting to `devon-vision`. The alternative was a
DEVON command so it was callable from the console. Tee left it a webhook: it is
proven on six rows, registered in `vault.py`, and matches how every other organ
in the estate is reached. A command would have cost a registration, a byte
identical mirror into `deploy/soul`, and a new description that has to stay
honest about what approving it does. Recorded so it is not reopened as an
oversight.

## Ruling 4: table ids get their own arc

73 Data Table nodes across 106 workflows resolve a table by name. That is what
silently redirected the TQO lane for four and a half hours on 2026-09-15, when
a concurrent session created mirror tables whose names contained `tqo_content`.
The durable fix is resolving by id.

Tee ruled it a scheduled arc rather than work bolted onto this one, and rather
than the smaller "active workflows first" cut. 73 nodes is too large to carry
alongside other work and every one of them is a live workflow that can break on
a careless edit. The arc should carry a check that counts name mode nodes from
the estate, so the count cannot drift the way this one did and so a new name
mode node cannot be added quietly.

Nothing is broken today: the mirrors are renamed and the hazard set across all
51 tables is empty. The naming rule in the Context Pill is what holds until the
arc runs.

## Ruling 5: OpenRouter is the vision backend

Asked what to put on Railway, Tee picked an OpenRouter model. That answered a
question ruling 1 had left open: the repo side path had a directory to read
from and no funded vendor to send a frame to. The `api` service carries no
Anthropic or OpenAI key, and the Anthropic account behind this estate is the
empty one that made OS 29 fail with a credit balance 400.

It could have shipped with no code at all. `OpenAIVisionProvider` already takes
an `api_url` override and already sends `Authorization: Bearer`, and OpenRouter
speaks the OpenAI Chat Completions dialect, so `VISION_PROVIDER=openai` with
`VISION_API_URL` pointed at OpenRouter works today. That shortcut was refused
for two reasons that are not style.

`OPENAI_API_KEY` is read in five places: the vision factory, the text provider,
the embedding provider twice, and the knowledge pipeline. An OpenRouter key
parked there authenticates all of them against the wrong vendor the day any one
is switched to `openai`. `OPENROUTER_API_KEY` is its own setting and nothing
else reads it.

And a receipt has to name who was actually paid. `_read` returns
`provider=self.name`, so borrowing the openai slot would have written
`provider: "openai"` into the same metadata the approval gate records, for a
call that never reached OpenAI.

So `OpenRouterVisionProvider` subclasses the OpenAI one: same dialect, own
name, own vendor string, own URL, own key. Three variables turn it on, and none
of them is a funded vendor account.

`OPENROUTER_DEFAULT_VISION_MODEL` is `inclusionai/ling-3.0-flash-vl:free`, the
endpoint the n8n lane measured at 200 and cost 0 under this account's Zero Data
Retention enforcement. A test pins it, and the docstring says why: ZDR
eligibility is per endpoint and not per price tier, which this session got
wrong once already. `gemma-4-31b-it:free` returned `zdr-violation-by-account`
on the same account the same day at the same price. Changing that default means
measuring the new endpoint, not reasoning that free implies free.

## What was measured

Both mutations and the suite were run on this branch, not on a handover's word.

- `test_devon_vision_spend.py`: 9 passed, up from 4.
- Four mutations of the real source, each failing the intended test with a
  named assertion: the weight dropped from the recorder, `ceil` swapped for
  `floor`, the below parity floor removed, and the config validator deleted.
- Standalone job reproduced with `PYTHONPATH` unset, which is stricter than
  CI: 733 passed.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_rulings-on-vision-and-table-ids_v1_2026-09-16l.md
DATE: 2026-09-16
DECISIONS: VISION_IMAGE_ROOT points at a dedicated inbox, var/vision-inbox/, tracked through its README with frames gitignored; the code default stays None so an unconfigured deployment still refuses. VISION_INPUT_TOKEN_WEIGHT names the image to text pricing ratio, defaults to 1.0 for parity with what shipped, prices input only, rounds up, and is refused below parity by both a config validator and a floor in the recorder. The vision lane keeps its raw devon-vision webhook rather than gaining a DEVON command. Resolving Data Tables by id becomes its own scheduled arc rather than being bolted onto this one or cut down to active workflows only. OpenRouter is the vision backend, as a first class provider with its own OPENROUTER_API_KEY rather than borrowing the openai slot, because OPENAI_API_KEY is read by four other lanes and because a receipt has to name who was actually paid.
FINDINGS: The vision spend under count was not a missing ledger column but an unnamed assumption that a vendor prices an image token like a text one. Naming it as a configurable ratio removes the silence without inventing a vendor's price.
OPEN: Nothing writes a frame into var/vision-inbox and a Railway container's disk is wiped each deploy, so the repo side path has a backend but still no way for an image to arrive. The real image to text price ratio for each configured vendor is unset, so the weight sits at parity until someone reads a price list. The table id arc is scheduled and unstarted, 73 name mode nodes across 106 workflows. No deployment has VISION_IMAGE_ROOT set yet, so vision.describe still refuses everywhere.
STATUS: Rulings 1, 2 and 5 shipped and measured. Ruling 3 is a decision to change nothing. Ruling 4 is scheduled.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
