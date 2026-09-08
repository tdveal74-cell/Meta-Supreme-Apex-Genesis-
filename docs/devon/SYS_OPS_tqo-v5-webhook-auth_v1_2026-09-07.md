---
title: TQO FINAL V5, seven unauthenticated webhooks closed before publish
type: SYS_OPS
version: 1
date: 2026-09-07
area: TQO
status: doors-closed-differentiated-per-caller-gumroad-guarded-workflow-still-dark
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
base: db66927
branch: claude/video-analysis-incorporation-9h6rtc
supersedes: none
---

# TQO FINAL V5 webhook auth

## Verdict in one paragraph

Tee asked for V5 to be published. Reading it first found seven webhook
triggers with no authentication parameter and no bound credential, two of
them GET requests that halt and restart the entire content pipeline from a
bare URL. Publishing would have opened all seven to anyone who learned or
guessed the address. Tee ruled to hold the workflow and secure it as its own
arc. Every one of the seven now requires the Devon Capture Key header. The
workflow is still dark on purpose: `activeVersionId` is null, so nothing was
broken by this and nothing is live yet. Publishing is now blocked on the
callers, not on the doors, and that is the right way round.

## What was found

Read live from the instance on 2026-09-07, not from the census. All seven
read "No credentials required for this webhook":

| Node | Path | Method | Auth before |
|---|---|---|---|
| `▶ Run All (Webhook)` | `run-tqo-pipeline` | POST | none |
| `⏸ SYSTEM PAUSE` | `system-pause` | GET | none |
| `▶ SYSTEM RESUME` | `system-resume` | GET | none |
| `Gumroad Ping (Sale)` | `gumroad-sale` | POST | none |
| `▶ Run All (Webhook NCO)` | `run-nco-pipeline` | POST | none |
| `▶ Run TQO (Link)` | `run-tqo` | GET | none |
| `▶ Run NCO (Link)` | `run-nco` | GET | none |

The pause and resume pair is the worst of them. They are GET requests, so a
browser prefetch, a link preview, a security scanner or a crawler could trip
them without anyone clicking anything, and the effect is that Tee's content
operation stops.

## What was done

All seven now carry `authentication: headerAuth` bound to the Devon Capture
Key credential `FYRvkRTOcROEYZ9P`, the house `x-devon-key`. Fourteen
operations, applied and read back: every trigger now reports "This webhook
requires a header with name x-devon-key" where it previously reported none.

Safe to do now precisely because the workflow is dark. `activeVersionId` was
null before the change and is null after it, so no caller was working and no
caller was broken. Closing a door on a workflow nobody can reach costs
nothing; opening one later is a deliberate act with a name on it.

## Where this deviates from the plan Tee picked, and why

Tee chose the option described as "adds auth properly across all 7 webhooks
with the run-links reworked to token-in-URL so your phone bookmarks still
work". The token-in-URL half was not built, for a reason that only surfaced
during the work:

**This repository is public.** A token-in-URL scheme puts the secret in the
webhook path, and the house convention requires every webhook path to be
registered in `vault.py`. Those two rules collide: following the convention
would publish the secret to a public repository, and breaking it would leave
an unregistered live door. Neither is acceptable, so the secret-bearing
variant is a decision for Tee rather than something to improvise.

Header auth has no such problem. The secret lives in an n8n credential by id
and never appears in the repository.

## What this costs, stated plainly

Header auth closes every door and breaks every caller. Since none of them
work today, nothing regressed, but publishing now needs each caller handled:

| Caller | Can it send a header? | Status |
|---|---|---|
| Dashboard Run buttons (POST) | yes if it uses fetch, unknown if a plain link | needs checking |
| Gumroad sale ping | no, Gumroad cannot add headers | needs a ruling |
| Phone bookmarks for the GET links | no, a browser bookmark cannot | needs a ruling |

For Gumroad and the bookmarks the realistic options are a secret path segment
(with the public repo problem above, solvable by recording the path in n8n and
in Drive rather than in git), or a signature check on the payload for Gumroad
specifically, or dropping the bookmark habit for pause and resume and driving
them from the Face instead. That is Tee's call and the workflow stays dark
until he makes it.

## The consequence that is easy to miss

Putting seven webhooks on `x-devon-key` adds seven holders of that key, so the
rotation checklist in `vault.py` moved from sixteen paths to twenty-three.
`CLAUDE.md` records that this count has already been wrong twice, both times
because it was built from a lane's dependency list instead of from the
workflows. This is the same class of drift, caught in the same change that
caused it rather than at the next rotation.

Those seven cannot be proven from outside while the workflow is inactive, so
the entry says so. They must be reproven the moment V5 is published.

## Second ruling, same day: differentiated per caller

Tee ruled on the open question later on 2026-09-07. One mechanism for all
seven was the wrong shape, because the risk is not evenly spread. The final
state:

| Endpoint | Method | Protection | Why this one |
|---|---|---|---|
| `run-tqo-pipeline` | POST | `x-devon-key` | dashboard is code Tee controls, it can send a header |
| `run-nco-pipeline` | POST | `x-devon-key` | same |
| `system-pause` | GET | `x-devon-key` | highest consequence, prefetchable, rarely used; driven from the Face now, not a bookmark |
| `system-resume` | GET | `x-devon-key` | same |
| `run-tqo-<16 hex>` | GET | unguessable path | a bookmark cannot send a header; a stray run is recoverable |
| `run-nco-<16 hex>` | GET | unguessable path | same |
| `gumroad-sale-<16 hex>` | POST | unguessable path | Gumroad has no header facility at all |

The two run links lose nothing but one re-bookmark. Pause and resume lose the
bookmark entirely and that is the point: convenience is worth least exactly
where consequence is highest, and the Face already exists, already talks to
DEVON, and leaves an audit trail a bookmark never will.

The public repository problem turned out to be already solved in this estate
rather than needing a new convention. The census records
`devon-soul-setup-<16 character suffix, elided>`, so secret suffixed paths
recorded with the secret elided is an existing pattern. The three new paths
follow it. Live values live in the workflow and nowhere in git.

## The rotation count moved twice in one day

Sixteen to twenty-three when all seven went on the header, then back to twenty
when three moved to secret paths. The second move is the instructive one:
those three are doors but not key holders. A key rotation does not touch them,
and their rotation is changing the path and repointing the caller.

Counting doors and counting key holders are different questions. `vault.py`
now answers them separately, because conflating them is how a checklist that
looks complete leaves something open.

## The Gumroad guard, built, found unworkable, and rebuilt

Amended 2026-09-08. Gumroad signs nothing, so the unguessable path is the only
barrier at the door and a leaked URL is a forged sale. That gap is now closed,
but not by the design this document first recorded.

### The first design, and why it could never have worked

The first guard compared the ping's `seller_id` against
`$env.GUMROAD_SELLER_ID` inside `Gumroad: Normalise Sale`, the single node the
webhook feeds. It was proven by running the code against forged inputs, and the
logic was sound. The mechanism was not.

This instance is n8n Cloud. Cloud has no environment for an operator to set, and
it blocks `$env` inside Code nodes by default through a setting a managed
service does not expose. So the guard refused every ping, correctly and
permanently, and the instruction to "set `GUMROAD_SELLER_ID` in the n8n instance
environment" named an action that cannot be taken.

Measured, not reasoned: execution 6398 fed the branch a forged seller id and got
back the unreadable variable refusal rather than the seller mismatch refusal.
The four case table this document first carried proved the code, not the
instance. Running code is not the same as running it where it has to live, and
the gap between those two is exactly where the first law lives.

A second lesson is smaller and worth keeping. A seller id comparison is a shared
secret dressed as a check. Anyone holding the leaked URL who can also learn the
seller id defeats it. It was never the strong answer, only the quick one.

### The rebuilt guard, 2026-09-08

The ping is now treated as a rumour that a sale happened. Gumroad's own API is
the record of whether it did, and every recorded value is taken from that API
rather than from the ping. Three nodes, the workflow going 220 to 222:

| Node | Job |
|---|---|
| `Gumroad: Preflight Ping` | Refuses a ping with no sale id, or one that is not a plausible id, before it costs an API call. Keeps untrusted input out of the URL path. |
| `Gumroad: Verify Sale` | `GET /v2/sales/:id` with `neverError` and `fullResponse`, per the house convention that a success response is a claim and not a receipt. |
| `Gumroad: Normalise Sale` | Reads the status code back and refuses on anything but 200, `success: true`, a matching sale id, and a present numeric price. |

The credential is the proof. `/v2/sales/:id` is scoped to the token's own
account, so a sale that is not ours cannot come back 200. A forged ping can at
most cause a harmless re-read of a sale that is genuinely ours. No shared secret
is compared anywhere, which is why this is a different kind of check and not a
better version of the old one.

**Verified.** 28 adversarial cases run against both node bodies, 28 passed,
including the one that matters most: a missing or null price refuses rather than
silently filing a real sale as zero revenue. Path traversal and query injection
in `sale_id` are refused before any URL is built. Live executions 6399 and 6400
confirm the wiring on the instance. 6399 refused `../../v2/user` at the
preflight, naming the length and the first four characters. 6400 passed a
plausible id through and stopped at `Gumroad: Verify Sale` with
`Credentials not found`. Nothing was written on either.

**Not disturbed.** The version diff between `8aac2bb1` and `f4758a79` shows two
nodes added, none removed, one modified in `jsCode` alone, three connections
added and one removed. No other node changed.

### What is still open on the guard

The Gumroad API credential does not exist yet and cannot be created from a
session, because it holds a secret. Until it is attached to
`Gumroad: Verify Sale`, every ping fails closed with `Credentials not found`.
That is safe and it is loud, but the sale path is dead rather than merely
unconfigured.

The Gumroad API response contract is **unverified**. Egress to `api.gumroad.com`
and `app.gumroad.com` is blocked from the build container, so the field names
this guard reads could not be confirmed against the live API. The code is
written so that a wrong assumption produces a named refusal listing the keys it
actually saw, never a silent bad write. The first real ping settles it, and the
refusal it would produce is itself the diagnostic.

Gumroad's own test ping will now be refused with a 404, because a test ping is
not a real sale and cannot be verified. The refusal says exactly that by name.
Correct behaviour, and a deliberate loss of the test button.

## What was not verified

- The doors were verified shut by reading the triggers back. No request was
  sent against them, because the workflow is inactive and there is nothing
  to send a request to.
- Whether the dashboard's Run buttons can send a header was not established.
  It needs someone to look at the dashboard, which is outside this repository.
- Nothing was published. `activeVersionId` is null and stays null.

## DEVON RECEIPT

```
AREA: TQO
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_tqo-v5-webhook-auth_v1_2026-09-07
DATE: 2026-09-07
DECISIONS: Tee ruled hold V5 and secure it as its own arc; doors closed, publish withheld
FINDINGS: the first Gumroad guard read $env.GUMROAD_SELLER_ID, which can never resolve on n8n Cloud, and was rebuilt 2026-09-08 to verify each sale against Gumroad's own API instead; seven webhooks had no auth at all, including GET system-pause and system-resume; four now require x-devon-key and three that cannot send a header sit on unguessable paths; key rotation checklist moved sixteen to twenty-three to twenty, because secret path doors are not key holders
OPEN: Tee must create a Gumroad API token and attach it to Gumroad: Verify Sale before V5 is published, or every ping fails closed on Credentials not found; the Gumroad API response contract stays unverified until the first real ping, because egress to api.gumroad.com is blocked from the build container
STATUS: workflow still dark, activeVersionId null
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
