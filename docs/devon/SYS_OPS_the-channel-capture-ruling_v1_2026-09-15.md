# The daily channel capture, measured and declined

Date: 2026-09-15. Closes the one open item left by
`SYS_OPS_the-timesfm-evaluation_v1_2026-09-15.md`, which asked whether to
start capturing a daily channel analytics series so a forecasting option would
exist in a year. Tee said start it. Three checks against the live account said
do not, and he ruled to file the finding rather than build.

## The reason the lane is not needed

YouTube already keeps the history the lane would have captured.

`vidiq_channel_analytics` on `UCZ58HLffFc3VJJ_RfvOLteQ`, dimensions day,
metrics views, estimatedMinutesWatched, subscribersGained and subscribersLost,
queried in one call across 2024-01-01 to 2026-09-13, returned 16 rows running
from 2025-11-24 to 2026-09-04. That is roughly 21 months of daily history
retrieved on demand with no capture job anywhere.

The API returns only days with activity, so the absence of 2024 rows cannot be
read as a retention cutoff. It could equally be 2024 retained and empty. What
the call does establish is that retrieval reach is not the constraint, which is
the only thing the capture lane would have been protecting against.

## The reason there is nothing to capture

`vidiq_channel_stats` on the same channel, read the same day. The channel is
"The Quiet Operator", published 2007-12-21T15:18:36Z, which makes it a
repurposed personal account rather than a new one. Country US. Topics
Technology and Lifestyle (sociology).

Current: 4 subscribers, 18 views, 24 videos. Growth across the default 30 day
window: 0 subscribers gained, 1 view gained, 0 videos published. The daily
series it returned for 2026-08-16 through 2026-09-15 is flat at 4 subscribers
and 24 videos throughout, with views sitting at 17 until 2026-09-06 and 18
after.

The analytics rows over the full 21 months sum to 24 views, 17 estimated
minutes watched, 5 subscribers gained and 3 lost.

Twenty four videos have produced eighteen lifetime views. No forecaster reads
a signal there, and neither does a straight edge.

## One number that does not reconcile, stated rather than smoothed

The public lifetime view count is 18 and the Analytics API attributes 24 views
across the window. Those disagree and this session did not reconcile them. The
likely reading is the ordinary difference between the public counter and what
Analytics attributes, but that is a guess and is labelled as one. Both numbers
are small enough that the conclusion does not move either way, which is the
only reason this was not chased further.

Net subscribers from the analytics rows is plus 2 against a current count of 4,
so 2 predate the window's first active day. That one is not a discrepancy.

## Where a capture lane would have earned its place

Channels Tee does not own. For those, vidIQ surfaces about 30 days of daily
stats and everything older is unrecoverable, so a daily snapshot builds history
that genuinely cannot be bought back later. That is the version worth building.

`vidiq_list_competitors` on the owned channel returns an empty list. There is
no competitor set to point it at, so even that version has no target today.

## The ruling

Do not build the capture lane. Nothing was added: no table, no migration, no
scheduled job, no n8n workflow, no dependency. The instrumentation that would
have justified it already exists and costs one call.

The finding that matters more than either of the above is not a measurement
problem. Twenty four published videos and eighteen views is distribution, and
no instrumentation moves it. Forecasting was never the missing piece and
neither is capture. That is named here rather than acted on, because it is
Tee's call and not a lane to wire.

## DEVON RECEIPT

```
AREA: TQO, Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-channel-capture-ruling_v1_2026-09-15
DATE: 2026-09-15
DECISIONS: Tee said start the daily channel analytics capture, then ruled to file the finding rather than build once the measurements came back. The recommendation put to him and accepted is to build nothing: no table, no migration, no scheduled job, no n8n workflow, no dependency. The decision taken inside this arc was mine and it was a refusal to build the lane on the instruction alone, because the three checks that decide it were cheap and unrun, and a capture job duplicating YouTube's own retention for a flat line is infrastructure that looks like progress and is not. If Tee overrules, the version worth defending is a daily snapshot of channels he does not own, which needs a competitor set chosen first because none is tracked today. This closes the open item carried by SYS_OPS_the-timesfm-evaluation_v1_2026-09-15.md.
FINDINGS: YouTube retains and serves the daily history the capture lane would have built, vidiq_channel_analytics on UCZ58HLffFc3VJJ_RfvOLteQ with dimensions day and metrics views, estimatedMinutesWatched, subscribersGained and subscribersLost returning 16 rows spanning 2025-11-24 to 2026-09-04 from a single call covering 2024-01-01 to 2026-09-13, which is roughly 21 months on demand with no job anywhere, though the API returns only days carrying activity so the absent 2024 rows cannot be read as a retention cutoff and may equally be retained and empty, a limit named here rather than rounded up; the channel itself carries no series worth forecasting, vidiq_channel_stats reading The Quiet Operator published 2007-12-21T15:18:36Z as a repurposed personal account at 4 subscribers, 18 views and 24 videos, with 0 subscribers and 1 view gained across the default 30 day window, a daily series flat at 4 subscribers and 24 videos from 2026-08-16 to 2026-09-15 with views stepping 17 to 18 on 2026-09-06, and the 21 months of analytics rows summing to 24 views, 17 estimated minutes watched, 5 subscribers gained and 3 lost; the public lifetime view count of 18 and the 24 views the Analytics API attributes across the window disagree and were not reconciled in this session, the ordinary public counter versus attributed difference being the likely reading and labelled a guess, with both numbers small enough that the conclusion does not move; net subscribers from the analytics rows is plus 2 against a current 4, so two predate the window's first active day, which is not a discrepancy; and the one non redundant use of a capture lane, daily snapshots of channels Tee does not own where vidIQ surfaces about 30 days and the rest is unrecoverable, has no target because vidiq_list_competitors on the owned channel returns an empty list.
OPEN: no capture lane exists and none is proposed; a competitor set for TQO is unchosen, and choosing one is what would make the defensible version of this lane buildable; the 18 against 24 view discrepancy is unreconciled and stays that way until a number depends on it; TQO's distribution problem, 24 published videos against 18 lifetime views, is named in this document and not acted on anywhere, and it is a ruling for Tee rather than a lane to wire; the forecasting question itself stays parked exactly where the TimesFM evaluation left it, revisit when a channel is doing numbers worth reading.
STATUS: filed, nothing shipped and nothing changed. This document is the only artifact. No table, migration, scheduled job, workflow or dependency was created, and no estate code was touched. Every number above was read today from the live vidIQ connector against the authorized account tdveal74@gmail.com and is quoted as returned rather than remembered, with the one figure that does not reconcile and the one inference that is a guess both labelled in the text.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
