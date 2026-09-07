---
title: TQO FINAL V5, seven unauthenticated webhooks closed before publish
type: SYS_OPS
version: 1
date: 2026-09-07
area: TQO
status: doors-closed-differentiated-per-caller-workflow-still-dark
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

## Still owed, and deliberately not done

**A payload guard on the Gumroad ping.** Gumroad signs nothing, so an
unguessable URL is the only barrier, and a leaked URL is a forged sale. The
guard is a Code node after `Gumroad Ping (Sale)` refusing any body whose
seller id is not Tee's.

It was not built. Inserting a node means rewiring connections inside a 220
node workflow whose graph has not been read, and a blind structural edit is
the exact failure this estate's first law exists to prevent. It is a bounded
piece of work once someone reads that branch, and it is safe to defer because
the workflow is dark. It is named here so it is owed rather than forgotten.

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
FINDINGS: seven webhooks had no auth at all, including GET system-pause and system-resume; four now require x-devon-key and three that cannot send a header sit on unguessable paths; key rotation checklist moved sixteen to twenty-three to twenty, because secret path doors are not key holders
OPEN: a payload guard on the Gumroad ping is still owed; Gumroad signs nothing so a leaked URL is a forged sale
STATUS: workflow still dark, activeVersionId null
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
