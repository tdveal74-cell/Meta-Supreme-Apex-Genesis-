---
title: Gumroad sale check moved off the phone and behind x-devon-key
type: SYS_OPS
version: 1
date: 2026-09-08
area: TQO
status: live-2026-09-08-first-call-from-the-phone-pending
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
project, published as `8c50cbb8` at about 11:53 UTC. Eight nodes including
the note:

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
   a 502 naming the credential to check; no answer becomes a 502; a found sale
   answers 200 with id, created_at, product name and permalink, formatted
   total, price in cents, currency symbol, quantity, buyer email, refunded,
   disputed, dispute won and order id, plus `source` naming the endpoint and
   the credential so the answer says where it came from.
5. Two Respond nodes, one per branch, carrying the status code from the item.

Error workflow `rqYmaQh91iCce8DJ`, timezone America/New_York. Registered in
`vault.py` as WEBHOOKS `devon-gumroad-sale-check` and in WORKFLOWS, and the
`x-devon-key` holder checklist moved from twenty to twenty-one in the same
change, with the stale line saying V5 was inactive corrected while it was
open.

## What was proved

| execution | input | what happened |
|---|---|---|
| 6482 | `AAAAAAAAAAAAAAAAAAAAAA==`, a made-up but plausible id | Preflight passed it, Gumroad answered HTTP 200 with `success: false` and "The sale was not found." in 250 ms, the door answered 404 with that message |
| 6483 | `AAAA=AAAA===`, an implausible id | Preflight refused it, the Gumroad node did not run, the door answered 400 |

Both ran in manual mode with the request body supplied to the trigger, so
the header check itself was not exercised by them; it is the same credential
and mechanism as the four V5 doors proved on 2026-09-07.

## Tee's Shortcut, the change

Replace the Get Contents of URL action's target and header:

| field | value |
|---|---|
| URL | `https://thequietoperator.app.n8n.cloud/webhook/devon-gumroad-sale-check` |
| method | POST |
| header | `x-devon-key`, the value the Pause and Resume Shortcuts already send |
| body | JSON, `{"sale_id": "<the id>"}` |
| show | Quick Look on the response |

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

## DEVON RECEIPT

```
AREA: TQO
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_gumroad-sale-check_v1_2026-09-08
DATE: 2026-09-08
DECISIONS: RULED route the Gumroad sale check through n8n, the token leaves the phone; RULED the July 2026 Gumroad token is gone, its registry row retired; RULED the Firecrawl failure path writes its reason into the row with no email (recorded in the OS 29 doc); RULED wait for tomorrow's firing before touching the volatility rule
FINDINGS: the phone timed out twice against api.gumroad.com with Private Relay off and no VPN while n8n answered in 250 ms; the door refuses an implausible id before any request and turns Gumroad's 200 success false into a 404
OPEN: the first call from the repointed Shortcut; a real sale through the door or the V5 guard; the phone's own path to api.gumroad.com
STATUS: live, workflow 7bDqKNdMHY8sxoXa activeVersionId 8c50cbb8, proved on executions 6482 and 6483, one x-devon-key holder added, twenty-one in the checklist
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
