# Gemini thinking usage: live verification and Presence repair

Status measured 2026-11-06 at 09:19 UTC: PR #488's API accounting passed a live
positive-thinking case and an independent committed-ledger readback.
Supersedes the activation-held status in
SYS_OPS_gemini-provider-compatibility_v1_2026-11-04-2051.md for the API path only.

## Live production evidence

The API ran merge 6cf649b749f6bbf24ad3fb6feb046c8b3f34f196 in Railway deployment
a4cfe313-ce0d-492c-b37a-51c2cea57c0f. The running Gemini adapter SHA-256 was
48e08ca7ef1503e1a99ce1724394208289855d43f36ea768036db9557bf7a002, matching that source.

Two separately bounded synthetic requests used the deployed adapter and actual
MeteredProvider, zero retries each, the verified active owner's tenant context
and the unchanged 500,000-token daily cap. No private prompt or tools were sent.

| Case | Raw prompt | Raw visible | Raw total | Ledger input | Ledger output |
|---|---:|---:|---:|---:|---:|
| Marker, requested max 64 | 10 | 7 | 17 | 10 | 7 |
| Reasoning, requested max 512 | 52 | 3 | 546 | 52 | 494 |

Both returned HTTP 200 from gemini-3.8-flash and the expected answer.
For the second, 546 minus 52 minus 3 gives 491 nonvisible thinking tokens.
Output is 494, already including the visible 3. One call was recorded each;
the system bucket changed by zero. No manual second ledger write was made.

The reasoning request ran from 09:18:53.468895 to 09:18:58.011646 UTC, with the
owner row committed at 09:18:57.970273. A separate Python process, using a
read-only SQL transaction at 09:19:38.606903, read 2 calls, 62 input and 501
output for the day. The cap allowed this real 563-token balance, with 499,437
remaining. The readback made no provider call or database write.

A process-local synthetic balance equal to the actual cap also caused the
deployed wrapper to return 429 provider_spend_cap before any provider attempt.
This tested deployed threshold behavior without exhausting or altering a real
tenant. The cap is a before-call check, not a reservation; concurrency can
overshoot. No invoice or dollar amount was inspected.

The historical 1,413 / 40 / 1,605 example remains an n8n fixture. Its correct
ledger shape is 1,413 input and 192 output, including the 152 difference once.
It was not substituted for the live observation.

## Presence repair and release contract

An independent verifier at 6cf649b confirmed Presence used the bare provider,
discarded usage, and passed no tenant into accounting. Offline reproductions
also showed TTFT cancellation reaching the provider and a naive cap exception
triggering fallback. They establish behavior, not an actual lost paid charge.

This change relays paid Presence text through an authenticated API endpoint.
The API validates the active owner, fixes the prompt/model/output contract,
uses zero retries and acknowledges only a committed usage write. Retained
bounded tasks preserve accounting if the HTTP waiter disconnects. Authentication,
cap and accounting refusals are terminal; no paid fallback bypasses them.
Presence receives no database credential.

Configuration: PRESENCE_API_BASE must be the API HTTPS origin,
https://api-production-5644.up.railway.app. Deploy the API route before the
Presence client. The existing mock fallback remains local and explicitly
simulated. Provider timeout or process kill can leave an unknown vendor
outcome; the code names this and does not automatically retry.

The pre-repair factory negative control failed as intended. The repair's
targeted offline run passed 112 tests, including tenant isolation, cap refusal,
strict ledger failure and cancellation. These checks are not live acceptance.

## Acceptance record

The current production verification, deployment readback and remaining limits
are maintained in the versioned acceptance report:
https://chatgpt.com/library?file_id=libfile_fde3_f-b0bb912d4d3c81918e38a68416c7cd5a_c9f987edf9148191860c977440c87468&account_id=personal

The API thinking-case acceptance above is complete. Presence requires its own
post-release request and durable readback; neither merge nor offline tests
alone establish that result. No speech, transcription or LiveKit acceptance
is claimed by this text-accounting change.

## DEVON RECEIPT

TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_gemini-thinking-live-and-presence-metering_v1_2026-11-06-0934.md
DATE: 2026-11-06
DECISIONS: Tee authorized bounded inference and completion of verification and necessary repairs.
FINDINGS: Positive live thinking counts matched durable owner usage; independent verifier confirmed Presence bypass.
OPEN: Presence release and post-release acceptance recorded in the linked current report.
STATUS: PR488 API thinking case live verified; this change carries the Presence repair.
