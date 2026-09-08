---
title: Gumroad sale check moved off the phone and behind x-devon-key
type: SYS_OPS
version: 1
date: 2026-09-08
area: TQO
status: live-2026-09-08-proved-from-the-phone-2026-09-08
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
base: 3d68476
branch: claude/video-analysis-incorporation-9h6rtc
supersedes: none
---

# Gumroad sale check through n8n

## Verdict in one paragraph

Tee's Gumroad Sale Check Shortcut, a direct call from his phone to
`api.gumroad.com` with the token in a header, failed twice on 2026-09-08 with
"the network connection was lost" and "the request timed out", with Private
Relay off and no VPN, while n8n reached the same endpoint in half a second
every time it was asked. He ruled on the card about 11:35 UTC to route the
check through n8n. The door is live: `POST /webhook/devon-gumroad-sale-check`
on the house `x-devon-key`, one plausible id in, one sale summary out, the
Gumroad token never leaving n8n credential `K1D8KUvTcWDcdrV0`. Proved on two
manual executions before publish. The first call from the phone is Tee's, and
until it lands the door is published, not proven from the outside.

## Why the phone failed is not known

Two symptoms, two calls, one phone, both with Private Relay off. What was not
tried from a session, because a session cannot run a phone: opening
`https://api.gumroad.com/v2/products` in Safari to see whether a plain 401
comes back quickly (which would put the fault in Shortcuts, its user agent or
QUIC, rather than the network), and the same Shortcut on cellular against
Wi-Fi. The ruling made the diagnosis unnecessary for the sale check, and it is
recorded here so nobody spends an evening on it by accident.

## What was built

Workflow `7bDqKNdMHY8sxoXa`, "DEVON Gumroad Sale Check", in the personal
project, published as `8c50cbb8` at about 11:53 UTC and republished as `e187e828`
at about 12:19 UTC after the fresh critic below (an empty-sale guard, successful
executions no longer saved). Eight nodes including the note:

1. `Sale Check (Webhook)`: POST, path `devon-gumroad-sale-check`, header
   auth on the Devon Capture Key credential `FYRvkRTOcROEYZ9P`, responds
   through the Respond nodes.
2. `Preflight`: reads `sale_id` from the JSON body or the query, and refuses
   before any request leaves unless it matches the same rule the V5 guard
   uses since the same-day fix, letters, digits, underscore, hyphen and up to
   two trailing equals signs. A missing id is refused too. Refusals answer
   400 with the reason.
3. `Plausible id?`, then `Gumroad GET sale`: `GET /v2/sales/:id` with the id
   URL-encoded, credential `K1D8KUvTcWDcdrV0` by id, `fullResponse` and
   `neverError` so the status code is read rather than assumed, 20 second
   timeout.
4. `Summarise`: the status code is the receipt. Gumroad's own 200 with
   `success: false` becomes a 404 with Gumroad's message; 401 or 403 becomes
   a 502 naming the credential to check; no answer becomes a 502; success true
   with no sale object becomes a 502 (added after the fresh critic on the first
   publish); a found sale answers 200 with id, created_at, product name and permalink, formatted
   total, price in cents, currency symbol, quantity, buyer email, refunded,
   disputed, dispute won and order id, plus `source` naming the endpoint and
   the credential so the answer says where it came from.
5. Two Respond nodes, one per branch, carrying the status code from the item.

Error workflow `rqYmaQh91iCce8DJ`, timezone America/New_York. Registered in
`vault.py` as WEBHOOKS `devon-gumroad-sale-check` and in WORKFLOWS, and the
`x-devon-key` holder checklist moved from twenty to twenty-one in the same
change, with the stale line saying V5 was inactive corrected while it was
open.

Successful executions are not saved, the house setting on fourteen of the
sixteen sibling `x-devon-key` doors, because `fullResponse` would otherwise
keep Gumroad's response headers and a real buyer's email in the execution
store. Error executions still save.

## What was proved

| execution | input | what happened |
|---|---|---|
| 6482 | `AAAAAAAAAAAAAAAAAAAAAA==`, a made-up but plausible id | Preflight passed it, Gumroad answered HTTP 200 with `success: false` and "The sale was not found." in 250 ms, the door answered 404 with that message |
| 6483 | `AAAA=AAAA===`, an implausible id | Preflight refused it, the Gumroad node did not run, the door answered 400 |
| 6489 | `B28UKN-dvxYabdavG97Y-Q==` with the Gumroad reply pinned to HTTP 200, `success: true`, no `sale` object | Summarise answered 502 naming the shape; before the guard this shape answered "Sale found." with every field undefined |
| 6490 | the same id with the Gumroad reply pinned to a found sale | the door answered 200 with the thirteen-field summary, the first time the found-sale branch ran anywhere |
| 6494 | throwaway probe workflow `D29SrhWXAxCZc9Ix`, archived after this one run: two real production POSTs at the door from inside n8n | with the Devon Capture Key credential by id: HTTP 404, "The sale was not found.", through the whole production path; without any header: HTTP 403, "Authorization data is wrong!", n8n's own header-auth refusal |

Both ran in manual mode with the request body supplied to the trigger, so
the header check itself was not exercised by them; it is the same credential
and mechanism as the four V5 doors proved on 2026-09-07. 6489 and 6490 pinned
the Gumroad node, so no request reached Gumroad; they prove the Summarise code,
not the credential.

## Tee's Shortcut, the change

Replace the Get Contents of URL action's target and header:

| field | value |
|---|---|
| URL | `https://thequietoperator.app.n8n.cloud/webhook/devon-gumroad-sale-check` |
| method | POST |
| header | `x-devon-key`, the value the Pause and Resume Shortcuts already send |
| body | Request Body set to JSON, one key: `{"sale_id": "<the id>"}` |
| show | Quick Look on the response |

Quick Look shows the JSON the door answers. How Shortcuts presents a 400, 404
or 502 body, as the JSON or as an error, is unverified from a session; the
`message` field carries the reason either way.

The `Authorization: Bearer` header and the Gumroad token come out of the
Shortcut. After that the phone holds no Gumroad token at all, which is one
fewer place to visit when the token rotates on 2026-10-08.

## The July token, retired

The Credentials registry carried the Gumroad token exposed in July 2026 as
EXPOSED since 2026-08-06. Tee confirmed on the card that it is gone from the
Gumroad application page, and the row `rec8XU8gaKQgznlAY` moved to Retired
with a dated note. The current token has its own row, `recsutD24MMpzTamX`,
on the monthly cadence ruled earlier the same day.

## What was not verified

- The first call from the phone. Until Tee runs the repointed Shortcut and
  sees a 404 for a made-up id or a 200 for a real one, the door is proved from
  inside n8n only.
- A real sale. No real sale id has been through this door or the V5 guard.
- Why the phone could not reach `api.gumroad.com` directly.
- The three 502 branches against a real Gumroad reply: no answer, 401 or 403,
  and success true with no sale object. 6489 proved the last on a pinned
  reply; none has run against Gumroad itself.

## Fresh critic, 2026-09-08 about 12:05 UTC

A cold subagent given only the diff, the live workflows and the executions
returned PASS-WITH-CONDITIONS (mean 4.00, security 4, correctness 5). What it
found and what happened to each:

| finding | consequence | done |
|---|---|---|
| the vault and the sticky note said the token had left the phone | a rotator trusting the record undercounts holders | reworded to pending in both, true when Tee's first call lands |
| registry row `recsutD24MMpzTamX` still told the rotator to re-enter the token in the Shortcut, and did not list this door as a consumer | the 2026-10-08 rotation would put the token back on the phone | row rewritten: n8n credential only, door listed, Shortcut marked as leaving |
| Summarise answered "Sale found." for success true with no sale object | one misleading read | guard added, proved on 6489, republished as `e187e828` |
| successful executions were saved with Gumroad's full response headers | set-cookie strings and a real buyer's email in the execution store | saving off for successes, proved on the published settings |
| the OS 29 doc carried two activeVersionIds for one workflow | a reader cannot tell which is live | header and STATUS now say `36b3170c`, V5 says `bde7ddec` |
| "proved on 6482 and 6483" without the manual-mode caveat | the header check reads as proved when it is not | caveat carried into the vault and this doc |
| the Shortcut table did not say Request Body JSON or what a non-2xx looks like | a stalled first call | body row amended, presentation marked unverified |

Left as the critic scored it: the Monthly Credential Review counts a Retired
row as tracked and current (cosmetic, pre-existing), and the OS 29 same-day
rerun would double-append a failure line (pre-existing behaviour).

## Probe from inside n8n, 2026-09-08 13:20 UTC

Tee said "just run the shortcut" at about 13:15 UTC. A session cannot run a
Shortcut on a phone, does not hold the `x-devon-key` value, and the container's
proxy refuses a tunnel to the n8n webhook host (CONNECT 403, measured twice).
What a session can do is have n8n call its own production door. A throwaway
workflow, `D29SrhWXAxCZc9Ix`, made two POSTs at
`/webhook/devon-gumroad-sale-check` on execution 6494 and was archived straight
after, so it is not a standing key holder:

| call | answer |
|---|---|
| with the Devon Capture Key credential `FYRvkRTOcROEYZ9P` by id, body `{"sale_id": "AAAAAAAAAAAAAAAAAAAAAA=="}` | HTTP 404, `The sale was not found.`, `gumroad_status` 200, in about 0.9 s |
| the same body with no header at all | HTTP 403, `Authorization data is wrong!`, from n8n's header check before the workflow ran |

Two corrections from the measurement. A missing key gets 403, not the 401
written in the earlier draft of this doc and in the session's report to Tee.
And the door's own successful executions are not saved (by design, above), so
the door side of the 404 call left no execution; the probe's record is the
receipt. What the probe does not prove is Tee's phone: the Shortcut on it has
still not called the door.

## First call from the phone, 2026-09-08 13:47 UTC

Tee rebuilt the Shortcut from a copy of DEVON Pause while the session watched
over screenshots: door URL, POST, one header `x-devon-key`, JSON body
`sale_id`, Quick Look on the answer, the Authorization Bearer row deleted.
Three corrections on the way, each caught from a screenshot before a run: the
old Shortcut had been calling `/v2/sales` with no id (Gumroad's list endpoint,
not a sale check), the body key was `sale id` with a space, and the
Authorization row survived one edit. On the first run Quick Look showed:

```
"sale_id" : "Provided Input", "http_status" : 400,
"message" : "REFUSED before any work: sale_id is not a plausible Gumroad id ..."
```

That is the receipt for three things at once. The phone's path to the door
works, and the header was accepted, since a wrong key answers 403 before
Preflight can run. Preflight refused before any request left, exactly as
built. And Shortcuts renders a non-2xx JSON body in Quick Look rather than
throwing, which closes the presentation question above. The refusal itself is a
Shortcuts quirk: the body value was the typed text "Provided Input" rather than
the magic variable from Ask for Input, so the door was handed the literal
string. After that the phone held no Gumroad token.

At 13:58 UTC, with the variable in place, Quick Look showed `ok: false`, the
`source` line naming GET /v2/sales/:id on credential `K1D8KUvTcWDcdrV0`, and
`gumroad_status` 200: the door went through to Gumroad from the phone and came
back with the not-found answer. That is the whole path end to end from the
phone, and the last open condition on this door. The Shortcut's own quirk,
Provided Input arriving as typed text, is reached through Select Variable and
the blue Ask for Input pill under the ask action, not through the keyboard
row, which offered no such variable.

## DEVON RECEIPT

```
AREA: TQO
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_gumroad-sale-check_v1_2026-09-08
DATE: 2026-09-08
DECISIONS: RULED route the Gumroad sale check through n8n, the token leaves the phone; RULED the July 2026 Gumroad token is gone, its registry row retired; RULED the Firecrawl failure path writes its reason into the row with no email (recorded in the OS 29 doc); RULED wait for tomorrow's firing before touching the volatility rule
FINDINGS: the phone timed out twice against api.gumroad.com with Private Relay off and no VPN while n8n answered in 250 ms; the door refuses an implausible id before any request and turns Gumroad's 200 success false into a 404
OPEN: a real sale through the door or the V5 guard; the phone's own path to api.gumroad.com; the door's 502 branches against Gumroad itself; whether the door gets a list job for a phone glance at recent sales, which waits on a ruling
STATUS: live, workflow 7bDqKNdMHY8sxoXa activeVersionId e187e828 (8c50cbb8 at first publish), proved on executions 6482 and 6483 (manual) and 6489 and 6490 (pinned Gumroad replies), successful executions not saved, header check proved from outside on probe execution 6494 (404 with the key, 403 without) and from Tee's phone at 13:47 UTC (400 at Preflight) and 13:58 UTC (the 404 end to end), the Gumroad token off the phone, one x-devon-key holder added, twenty-one in the checklist, fresh critic PASS-WITH-CONDITIONS with every condition applied the same hour
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
