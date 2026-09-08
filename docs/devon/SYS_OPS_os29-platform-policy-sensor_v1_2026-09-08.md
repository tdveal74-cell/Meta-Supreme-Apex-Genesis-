# SYS_OPS: OS 29 Platform Policy Sensor, switched on and made honest

Date: 2026-09-08
Workflow: `7WyIarNoJa2irx2r`, active, `activeVersionId 2799a1e4`
Ruled by Tee: switch it on; turn Gateway credits on; find fetchable alternatives;
Firecrawl as a fallback for the failing four; a separate column for machine verdicts.

## Why it was switched on

The 2026-09-07 estate prune found a policy sensor sitting inactive. Tee's
standing rules say there is no exception path for compliance items and name
platform policy first. A policy sensor switched off is that exception in
practice, so it was raised as a finding rather than pruned, and Tee ruled it on.

## What it does

Daily 06:00 America/New_York, it reads eight watched platform policy pages,
fingerprints the normalised text, and only when a fingerprint moves does it ask
Claude whether the change is material to TQO, TSWS or NCO Forge. It files the
verdict in the OS 28 Policy Watch table and mails it. It changes nothing on any
platform.

Its cron was implicit and would have inherited the instance default. It is now
pinned to America/New_York, matching the six other scheduled workflows pinned on
2026-09-07. Zero behaviour change today, and it survives a VPS cutover.

## The defect that mattered

The first sweep, execution 6401, reported success and recorded baselines for
seven of eight sources. Three of those baselines were empty:

| Source | Readable text |
|---|---|
| Meta Content Monetization | 79 characters |
| Meta Partner Monetization | 75 characters |
| TikTok Creator Rewards | 14 characters |

They fetched HTTP 200 and cleared the raw byte guard, then normalised to nothing,
because Meta's Business Help Center and TikTok's support site are JavaScript
applications with no server rendered policy text. The raw TikTok body is literally
`<div id="root"></div>` with the content never rendered.

A fingerprint of 14 characters can never move. All three would have read **Stable**
in Airtable forever while nothing was watched. Three platforms looking covered and
not being covered, in the one sensor whose entire job is compliance.

That is green light drift, by the name the estate itself gave it in a convention
written the previous day. The convention was written on 2026-09-07 and its first
live example was found on 2026-09-08, in the estate's own machinery.

**The fix.** A page must now yield 1000 characters of readable text or it becomes
a reported failure that chases after three days. The four readable sources measure
14016 to 84552 characters, so the threshold clears the largest empty shell by a
factor of 177. Proven by 8 local cases and by execution 6402, where the four
working fingerprints came back byte identical, which is what proves the
normalisation regexes survived the edit.

## Two remedies tried, both failed, both measured

Neither was reasoned about and dropped. Both were run and reverted.

- **A browser User-Agent**, execution 6403. X stayed 403, TikTok stayed at 14
  characters, and Meta's useless 200 became a flat 400. The four working sources
  were unaffected. Reverted: a change with no demonstrated benefit does not stay.
- **Substitute URLs**, execution 6407. Both `transparency.meta.com` candidates
  returned 404 and TikTok's legal page returned 6 characters, worse than the 14 it
  had. Reverted. A search then confirmed the original `facebook.com/business/help`
  URLs are canonical and no server rendered alternative exists.

The honest conclusion at that point was that plain HTTP would never fix this, and
guessing more URLs was spending executions to learn nothing.

## Gateway credits

`list_n8n_gateway_services` reports `available: true` on this instance. Two nodes
were moved onto it, and n8n attached the managed credential automatically in both
cases, so no key is held anywhere in the estate.

**Assess Materiality.** Was a raw HTTP POST to `api.anthropic.com` with a generic
header credential that was never attached, so it could only ever have thrown
`Credentials not found`. It is now the langchain Anthropic node on a managed
`anthropicApi` credential. `simplify` is false, which returns the raw API shape
that Parse Assessment already reads, so the parser was not touched. The system
prompt and user message are read from the existing `claudeBody` object rather than
retyped, so that large prompt could not be damaged.

The first attempt returned `Bad request`. The cause was found in the Claude API
reference rather than guessed: **Sonnet 5 and Opus 5 both removed the sampling
parameters, so `temperature` returns a 400.** It was a parameter error, not a model
id error. `maxTokens` was also raised from 1200 to 8000, because thinking is on by
default on Opus 5 and is drawn from the same ceiling.

Proven end to end by execution 6409: a real verdict in 13.7 seconds, 2699 input and
858 output tokens, `stop_reason: end_turn`, and a real email accepted by SMTP with
`250 2.0.0 OK`. The model worked out unprompted that TSWS is the only Spotify
exposed show.

**Firecrawl.** Runs only when plain HTTP has already failed, so about 120 scrapes a
month rather than 240, and the four sources already proven keep the path that
works. Execution 6410 proved the routing exactly, four Firecrawl calls for four
failing sources and none for the working four, and Firecrawl returned a precise
400: `expected array, received object` at path `actions`, from the scrapeOptions
collection. Markdown is already the default format, so the collection was removed
rather than fought with.

## Coverage is now eight of eight

Execution 6414, all eight `Stable`, zero consecutive failures, real fingerprints.

| Source | Readable text | Path |
|---|---|---|
| YouTube advertiser friendly content guidelines | 84552 | plain HTTP |
| YouTube channel monetization policies | 28508 | plain HTTP |
| YouTube Shorts monetization policies | 16147 | plain HTTP |
| Spotify for Creators Partner Program | 14016 | plain HTTP |
| TikTok Creator Rewards Program | 10138 | Firecrawl |
| Meta Partner Monetization Policies | 8225 | Firecrawl |
| X Creator Revenue Sharing | 5415 | Firecrawl |
| Meta Content Monetization Policies | 4206 | Firecrawl |

Firecrawl cleared X's 403, which was bot blocking rather than JavaScript rendering
and was not expected to work.

## The curated notes are now protected

Forcing a test change proved that `Record Change` overwrote the `Assessment`
column wholesale. That column holds Tee's researched notes, including the X one
recording that undisclosed AI conflict video costs 90 days of revenue sharing,
independently verified against three outlets. The test destroyed the Spotify note
twice and it was restored by hand only because it had been read first. Every real
change would have done the same, permanently, one source at a time.

Tee ruled a separate column. Machine verdicts now go to **AI Verdict**
(`fldygGYiK89Z0tJ82`) and the workflow no longer writes `Assessment` at all.

## What the sensor found on its first real read

The X page, now readable for the first time, says verbatim:

> as of august 7, 2026, we are no longer accepting new enrollments into the
> creator revenue sharing program, and it will be retired on september 7, 2026.
> apply to the new original content rewards program to continue earning from your
> content on x.

**Creator Revenue Sharing was retired on 2026-09-07, the day before this sweep.**
The curated note on that source describes a programme that no longer exists. The
AI conflict disclosure rule is still on the page and still real, but it now
attaches to a dead scheme, and there is a successor called Original Content
Rewards with its own eligibility that nothing in the estate is tracking.

That is the highest stakes source in the table by Tee's own note, it governs
NCO Forge, and the gap existed precisely because the page could not be read.
It is raised here and left for Tee: the note is his and was not edited.

## What was not verified

- The Gumroad API contract remains unverified from a session container, because
  egress to `api.gumroad.com` is blocked. Unrelated to this sensor, still open.
- Firecrawl's cost per scrape was not measured, only its call count, which is four
  per sweep.
- The 06:00 scheduled firing has not yet happened. Every proof above is a manual
  execution of the same published version.

## DEVON RECEIPT

```
AREA: OS
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_os29-platform-policy-sensor_v1_2026-09-08
DATE: 2026-09-08
DECISIONS: Tee ruled switch OS 29 on, turn Gateway credits on, Firecrawl as a fallback for the failing four only, a separate column for machine verdicts, and close the arc after Firecrawl landed
FINDINGS: the sensor reported Stable on three JavaScript rendered sources yielding 79, 75 and 14 characters of readable text, which is green light drift found one day after the convention naming it was written; a browser User-Agent and substitute URLs were both tried and reverted with receipts; temperature returns a 400 on Sonnet 5 and Opus 5 because sampling parameters were removed; Record Change was overwriting the curated Assessment column and would have destroyed every researched note one source at a time; coverage went four of eight to eight of eight once Firecrawl was wired, and Firecrawl also cleared X's 403
OPEN: X Creator Revenue Sharing was RETIRED 2026-09-07 and replaced by Original Content Rewards, so the curated note on the estate's highest stakes source describes a dead programme and the successor is untracked; the Gumroad API token is still not created, so V5 cannot publish
STATUS: OS 29 active, activeVersionId 2799a1e4, daily 06:00 America/New_York, eight of eight watched, verdicts on Opus 5 via Gateway credits with no API key held
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
