---
title: TQO FINAL V5, seven unauthenticated webhooks closed before publish
type: SYS_OPS
version: 1
date: 2026-09-07
area: TQO
status: doors-closed-workflow-still-dark-publish-blocked-on-callers
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
FINDINGS: seven webhooks had no auth at all, including GET system-pause and system-resume; all seven now require x-devon-key; key rotation checklist moved from sixteen paths to twenty-three
OPEN: Gumroad and phone bookmarks cannot send headers, so publishing needs Tee's ruling on a secret path or a payload signature
STATUS: workflow still dark, activeVersionId null
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
