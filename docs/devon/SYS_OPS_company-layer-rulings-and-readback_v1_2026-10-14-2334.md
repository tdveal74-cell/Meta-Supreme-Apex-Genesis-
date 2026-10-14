# Company layer: rulings of 2026-10-14 and the read back of main 951af6a

Supersedes the open list in `SYS_OPS_company-layer-six-function-queues_v1_2026-10-12-2225.md`. That doc is a dated record and stays as written. Where the two disagree, this one is newer.

## Rulings closed

Tee ruled on inline cards on 2026-10-14, in two rounds.

Round one, merged in PR #337 as main 951af6a:
- A one to one Sales email needs no AI disclosure. The recommendation was to keep it; Tee overruled it and it was built as ruled. A disclosure that is given is still checked and still needs 10 visible characters. Migration 027 makes the column nullable.
- The dash rule covers decision notes, Product acceptance checks, Product prose reference artifacts and Research measured and unverified references. It does not cover URLs or quoted text.
- The hyphen look-alikes U+2010 and U+2011 stay allowed.
- The visible character counter was fixed. Braille blanks, Hangul fillers and bare combining marks no longer clear a 10 character floor.

Round two, this change:
- The dash rule now covers Sales `qualification_reason` and Support `reply_basis`.
- Ten more look-alikes are banned: U+301C, U+3030, U+30A0, U+2E40, U+058A, U+05BE, U+1806, U+2E17, U+2E1A and U+10EAD. U+058A and U+05BE are real Armenian and Hebrew hyphens, so text in those scripts is refused. The content is English, so that cost was accepted.
- The Vercel newest-READY check is left to Tee in the dashboard. It has not been confirmed.

## Read back of main 951af6a

Railway, all three on commit 951af6ae2bdfd602b99d05faaf7d2a2a3313c9b5: api 51cb8ec1 SUCCESS, presence 5e9662d9 SUCCESS, scheduler-cron 64d263df SUCCESS. The api deploy log reads `Running upgrade 026_company_proposals -> 027_lead_disclosure_optional`. The api health read at 21:54Z returned healthy; presence returned ok with livekit_configured true, audio_over_websocket false and the breaker closed.

Vercel: git diff over each project's watched paths was empty from the last READY production commits as recorded on 2026-10-12, web ac9bb36 and soul e8a72b7. Whether those are still the newest READY deploys is unverified, because the Vercel connection returned 403 for the team scope. Tee confirms in the dashboard.

## Verification of the round two change

Ruff clean. Full API suite run alone: 4081 passed, exit 0. Targeted route and queue tests against the database passed. Three mutations were each killed by a failing test and restored byte identical: removing the Sales reason check, removing the Support basis check, and removing U+10EAD from the list. No independent critic ran on this slice.

## Open

- Stripe authorization, the Blotato subscription and vidIQ credits are Tee's account steps. Nothing reads from them yet.
- Sales inbox and form intake, Support knowledge base and posting, and Research search are not built.
- Thai, Arabic and Devanagari text counts lower than it reads, because combining marks do not count toward the floor. Accepted.
- A lone surrogate in raw JSON likely returns a 500 across the app. Not fixed.
- No company route has been exercised in production.
- The 10 character floors are enforced in code. The database only requires non-blank.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_company-layer-rulings-and-readback_v1_2026-10-14-2334.md
DATE: 2026-10-14
DECISIONS: Tee ruled on 2026-10-14 on inline cards: Sales email needs no AI disclosure; dash rule extended to notes, acceptance checks, prose references and measured references but not URLs or quoted text; hyphens U+2010 and U+2011 allowed; dash rule extended to Sales qualification_reason and Support reply_basis; ten more dash look-alikes banned; superseding status doc; the Vercel newest-READY check is left to Tee in the dashboard.
FINDINGS: Main 951af6a read back: Railway api, presence and scheduler-cron SUCCESS, migration 027 logged, api and presence health read. Vercel diff empty from ac9bb36 and e8a72b7, newest-READY status unverified. Round two change passes the full suite, 4081 passed, and three mutations were killed.
OPEN: Stripe authorization; Blotato subscription; vidIQ credits; Sales and Support intake and knowledge base not built; Vercel newest-READY confirmation; lone surrogate 500; no company route exercised in production; no critic on this slice.
STATUS: Round one of the 2026-10-14 rulings is merged and live on Railway. Round two is built and passes the local suite; it merges after CI is green.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
