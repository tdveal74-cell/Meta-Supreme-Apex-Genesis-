# SYS_OPS: OS 29 Platform Policy Sensor, the capture was hollow and the record said watched

Date: 2026-09-08, later the same night
Workflow: `7WyIarNoJa2irx2r`, active, `activeVersionId 9a235eaa`
Supersedes: `SYS_OPS_os29-platform-policy-sensor_v1_2026-09-08` on the coverage claim only.
Ruled by Tee: block-level diff with self-learned volatile blocks; fix the capture rather than
the comparison; add the X successor as a watched source and leave his curated note alone.

## The correction, first

The v1 doc says eight of eight sources watched, execution 6414, all Stable, real
fingerprints. That was true of the fetch and false of the capture. Meta Content
Monetization Policies came back HTTP 200 with 14,926 characters of markdown, and three
whole policy sections inside it were a heading, a lead-in sentence, and nothing:

```
## Prohibited behaviors
The following behaviors cannot monetize:
                                              (nothing)
## Restricted categories
Content that ... may face reduced or restricted monetization:
                                              (nothing)
## Prohibited categories
The following types of content are ineligible to monetize:
                                              (nothing)
```

Only `Prohibited formats` rendered its body. The three lists that say what actually
gets a page demonetized on Facebook were absent from every scan since the sensor was
built, and the 1,000 character floor added in v1 cannot see that: a capture missing
three sections cleared it by a factor of four and read Stable. That is the same green
light drift v1 named, one layer down. A floor on total text does not detect a partial
capture. Only a per-heading completeness check can, and that check is not built yet.

## How it was found, including the wrong turn

Three of nine rows flipped to Changed inside one hour with no policy movement behind
them. Two renders three minutes apart settled that it was not real change: Meta Partner
returned to fingerprint `7fcf18d2`, byte for byte the value from seventy minutes
earlier, and pages are not edited back into an identical prior state.

The first diagnosis was cosmetic jitter from a support chat widget, and a block-level
diff with self-learned volatile blocks was built and published against it. Nine local
checks passed before it touched the instance, including the case that killed the first
draft: a policy line deleted and then restored would have been silenced on the restore,
so a block now needs two flips rather than one before it is classed as chrome.

The diagnosis was wrong. Reading the added and removed blocks across scans 6423 and
6424 showed `misinformation` leaving and `looping videos`, `text montages`, `embedded
ads` arriving. Those are Meta's ineligible content definitions, not chrome. Real policy
text was moving in and out of the capture at random.

## The root cause, from source rather than from theory

A parallel research pass read the Firecrawl node schema on the live instance, the
published node source, and Firecrawl's own API source. Two defaults were in force
because the node sent no options at all:

- `waitFor` prefaults to 0. The DOM is serialised the instant navigation resolves, with
  no settle. Anything injected client side after that moment is not in the snapshot.
  Only a race can make an unchanged page return a different section set on each scan;
  every other candidate, CSS hidden dropping, click gating, boilerplate stripping, is
  deterministic and was ruled out by that argument alone.
- `onlyMainContent` prefaults to true. Its removal list keys on generic class names,
  `.top`, `.bottom`, `.side`, `.widget`, `.overlay`, `.share`. Deleting a sibling
  container while leaving the preceding heading and lead-in intact produces exactly the
  shape observed.

The CSS hidden accordion theory raised first in chat was actively contradicted: the
HTML to markdown converter has no layout engine and no rule keyed on `display:none`,
and Firecrawl's own guidance tells users who want hidden content removed to add an
exclude rule, which only makes sense if the default keeps it.

## The fix, and what it did not touch

`Firecrawl Render` now runs with `useCustomBody: true` and this body:

```json
{ "formats": ["markdown", "rawHtml"], "onlyMainContent": false,
  "waitFor": 15000, "timeout": 60000 }
```

plus `requestOptions.timeout` 120000 so the request budget covers the Firecrawl one.
Custom body was chosen over the `scrapeOptions` collection because every fixed
collection is hidden under it, so the empty container 400 from execution 6410 cannot
recur by construction. `url` stays out of the body on purpose: it is the expression
`{{ $json.url }}` serving all four Firecrawl sources, and a literal there would have
silently repointed TikTok and both X pages at the Facebook page while all four kept
reporting Stable. The research converge step caught that in one researcher's
recommendation and refused it.

`rawHtml` rides along so the same scrape says which default mattered: markdown is
derived from it, so body text in rawHtml but not markdown means the filter, absent from
both means timing.

## The test was fixed before the run, and it passed

Nobody in the chain could open a Meta page from this environment, so the test was built
from the observed shape rather than from any policy sentence someone might have
invented. On execution 6430:

| pattern | before | after |
|---|---|---|
| a body line following `cannot monetize:` | 0 | 1 |
| a body line following `restricted monetization:` | 0 | 1 |
| a body line following `ineligible to monetize:` | 0 | 1 |
| a heading directly after each lead-in (the complement) | 3 | 0 |
| hollow sections on the page | 3 | 0 |

`rawHtml` came back on all five Firecrawl sources, proving the custom body reached
Firecrawl. Meta Content went 14,926 to 29,578 characters of markdown and 54 to 162
normalised blocks. Every Firecrawl source gained blocks, so `onlyMainContent` had been
stripping all of them, not just the one with the visible hollow headings.

Determinism across the next scan, 6430 to 6431:

| source | blocks | churn |
|---|---|---|
| X Creator Revenue Sharing | 85, 85 | none |
| X Original Content Rewards | 144, 144 | none |
| TikTok Creator Rewards | 99, 99 | none |
| Meta Content | 162, 163 | the support chat widget |
| Meta Partner | 110, 111 | the same widget |

Three sources are byte stable. The two Meta pages still move by two or three blocks
between scans, and every instance inspected was chrome. That is the signal the volatile
learning was designed for. Until this fix it had been fed a broken one.

## The learning had already silenced policy, and was reset

Before the fix landed, the volatile counter, trained on the broken captures during the
manual runs that night, had classed nine blocks on Meta Partner Monetization as chrome.
Two were chrome. Seven were the established presence requirement and the whole
political entity eligibility rule. The sensor would not have reported a change to any
of it.

All nine `Block Index` fields were cleared and the sensor re-baselined on the clean
capture in execution 6432. Verified after: `first_sight` true on every row, no verdict
fired, zero volatile blocks on any source, and all seven policy blocks back in the
watched set. Nothing was lost, and that hole was live for roughly an hour.

## What the fix recovered

From the previously hollow `Restricted categories`, verbatim:

> Tragedy or conflict. We define "tragedy or conflict" as "physical or emotional
> distress, such as death, injury, abuse, illness, or destructive events." Depictions or
> discussions of these subjects, either real or fictional, may affect monetization for
> your content. However, content that depicts or discusses these subjects in an
> explicitly uplifting manner may still be eligible for monetization.

That governs NCO Forge on Facebook directly and had never been captured. The same
section restricts polarizing treatment of political affiliation, immigration and
election legitimacy, and `Prohibited formats` names text montages and looping videos as
ineligible, which lands on TSWS's stylised visual treatment.

## The X successor, and the disclosure rule that carried over

Creator Revenue Sharing was retired 2026-09-07. Its successor, Original Content
Rewards, is now watched as its own row, `recb7lpN516K7LZwE`. Tee's curated note on the
retired page was not touched, by his ruling. Reading the new page closed the question
v1 left open. Verbatim from the sensor's own render:

> Additionally, effective March 3, 2026 users who post AI-generated videos of an armed
> conflict without adding a disclosure that it was made with AI will be suspended from
> the Original Content Rewards Program for 90 days. Subsequent violations will result in
> a permanent suspension of further payments.

The rule did not lapse with the old programme. The eligibility maths did change: 500,000
Home Timeline impressions from verified users in 90 days with replies excluded, 500
verified followers, an active Premium subscription. The old five million figure belongs
to the retired programme.

## Two estate level findings from the research pass

`validate_node_config` performs no schema checking on this community node. It returned
`valid: true` for invented keys, for a bogus `resource` value, and for a completely
empty parameters object, while correctly rejecting a bad mode on `n8n-nodes-base.set`.
Every "validated" claim any session has made about a community node is worth nothing.

The assessment prompt still described TQO as faceless and named the podcast The Shared
Shadow. A sensor that thinks the shows are faceless misjudges a likeness or voice
cloning rule, which is the highest stakes lane it watches. Both corrected; the prompt
now judges a real added and removed diff rather than re-reading the whole page.

## Gumroad, exercised live for the first time

The credential Tee created is Header Auth, not Bearer Auth; the node was switched to
match rather than asking him to rebuild it. Execution 6422 probed with a well formed but
non existent sale id. Gumroad answered HTTP 200 with `success: false, The sale was not
found`, and the guard refused with nothing written. Gumroad returns 200, not 404, for a
missing sale; a guard checking only the status code would have sailed past it.

## Stated, not papered over

- YouTube Advertiser-friendly guidelines runs at 733 blocks and 76,868 characters, over
  the 30,000 character snippet cap, so on that page a removed block is reported as a
  count and its text is not retained. The prompt says so and forbids guessing what it
  said. Every other watched page is under the cap and keeps removed text.
- The per-heading completeness assertion is not built. Until it is, a future partial
  capture will pass the 1,000 character floor and read Stable.
- `view_sales` on the Gumroad token is inferred from the endpoint accepting it, not
  proven by a successful sale read.
- TQO FINAL V5 remains unpublished by choice. Publishing activates six schedules and
  seven webhooks across two shows, which is not the same act as attaching a credential.
- The DEVON thread log entry for this session was not filed. A safety classifier in the
  session blocked the Notion write and a local file write of the same content.
- The Context Pill needs updating: TQO and NCO Forge are presenter led with owned
  likeness and cloned voice; the faceless framing is retired.
- X's "created or posted using automated means" exclusion is unresolved against an AI
  scripted, AI voiced pipeline and needs a ruling before TQO plans X revenue.

## DEVON RECEIPT

```
AREA: OS
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_os29-platform-policy-sensor_v2_2026-09-08
DATE: 2026-09-08
DECISIONS: Tee ruled a block-level diff with self-learned volatile blocks over a similarity threshold; fix the Firecrawl capture rather than the comparison; watch the X successor as a new row and leave his curated note alone; Systems primary and Money cross-reference for the Gumroad credential; no calendar rotation for the Gumroad token, scope reduction and exposure triggers instead; the Gumroad Application ID and Secret stay unwired
FINDINGS: the v1 coverage claim was true of fetch and false of capture, Meta Content Monetization had three hollow policy sections since the sensor was built; root cause was waitFor 0 and onlyMainContent true, both Firecrawl defaults in force because the node sent no options; the volatile learning trained on broken captures silenced seven real policy blocks on Meta Partner for roughly an hour before the flip state was cleared; the Tragedy or conflict restriction governing NCO Forge on Facebook was never captured before tonight; the March 3 2026 AI conflict disclosure rule carries over into X Original Content Rewards verbatim; validate_node_config returns valid for anything on community nodes; Gumroad returns 200 not 404 for a missing sale
OPEN: per-heading completeness assertion not built; view_sales inferred not proven; V5 unpublished by choice; thread log entry unfiled after a classifier block; Context Pill stale on the faceless framing; X automated means exclusion needs a ruling
STATUS: OS 29 active, activeVersionId 9a235eaa, daily 06:00 America/New_York, nine sources watched, three byte stable across scans and the two Meta pages moving only on chrome, zero volatile blocks, first scheduled firing checked at 06:20
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
