# SYS_OPS: OS 29 Platform Policy Sensor, the capture was hollow and the record said watched

Date: 2026-09-08, later the same night
Workflow: `7WyIarNoJa2irx2r`, active, `activeVersionId 138e7ceb` (was `9a235eaa` when this
doc was first written, `38857d14` from about 05:56 UTC, and republished at about 06:33 UTC
with the Firecrawl cache bypass recorded below)
Supersedes: `SYS_OPS_os29-platform-policy-sensor_v1_2026-09-08` on the coverage claim, on the
scrape count (five a sweep and about 150 a month, not four and 120), and on the timing of the
first scheduled firing.
Amended 2026-09-08 after merge (#165), on a fresh critic's findings against the raw execution
data, and again after merge (#166) when the locale pin exposed Firecrawl's default cache. The first version of this doc inverted the silencing timeline, omitted that the sensor
had erased its own material verdicts, and overstated stability. Each is corrected in place.
Ruled by Tee: block-level diff with self-learned volatile blocks; fix the capture rather than
the comparison; add the X successor as a watched source and leave his curated note alone.

## The correction, first

The v1 doc says eight of eight sources watched, execution 6414, all Stable, real
fingerprints. That was true of the fetch and false of the capture. Meta Content
Monetization Policies came back HTTP 200 with 14,919 characters of markdown (execution 6420; the figure moves
by a few characters per scan), and three
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
returned to fingerprint `7fcf18d2`, the identical value from seventy minutes
earlier, and pages are not edited back into an identical prior state.

The first diagnosis was cosmetic jitter from a support chat widget, and a block-level
diff with self-learned volatile blocks was built and published against it. Sixteen local
assertions across three harnesses passed before it touched the instance, including the case that killed the first
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
`{{ $json.url }}` serving all five Firecrawl sources, and a literal there would have
silently repointed TikTok, both X pages and the other Meta page at the Facebook page
while all five kept reporting Stable. The research converge step caught that in one researcher's
recommendation and refused it.

`rawHtml` was carried so the same scrape could say which default mattered: markdown is
derived from it, so body text in rawHtml but not markdown would mean the filter, absent
from both would mean timing. That readout was never done, and because both defaults were
flipped in one body it could not have attributed the hollowing to one of them anyway. The
result is 2.3 MB of rawHtml stored per sweep, 2,292,773 characters on 6430, with no consumer, since `Fingerprint
Rendered` reads only markdown. It should be dropped; see the open items.

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
Firecrawl. Meta Content went 14,919 to 29,578 characters of markdown and 54 to 162
normalised blocks. Four of the five Firecrawl sources gained blocks; TikTok gained none, unchanged at 99,
so its capture was already complete. `onlyMainContent` had been stripping the other
four, not just the one with the visible hollow headings.

Stability across the next scan, 6430 to 6431:

| source | blocks | churn |
|---|---|---|
| X Creator Revenue Sharing | 85, 85 | none |
| X Original Content Rewards | 144, 144 | none |
| TikTok Creator Rewards | 99, 99 | none |
| Meta Content | 162, 163 | the support chat promo |
| Meta Partner | 110, 111 | the chat promo leaving, two feedback prompts returning |

Three sources returned identical normalised fingerprints across three scans in thirteen
minutes. That is fingerprint stability over lowercased, date and hash stripped, deduplicated
block text, not byte identity, and two consecutive pairs is not a determinism proof. The two
Meta pages still move by two or three blocks between scans, and every instance inspected
was chrome: the support chat promo, and on Meta Partner the two feedback prompts, "have a
moment?" and "tell us how we're doing".

## The learning had already silenced policy, and was reset


The first version of this doc said the volatile counter had silenced policy blocks
"before the fix landed", trained on the broken captures. The raw data says the opposite,
and the difference matters.

| execution | Meta Partner volatile | newly volatile | when |
|---|---|---|---|
| 6424, last run before the fix | 0 | 0 | 03:56 |
| 6430, first run with the fix | 7 | 7 | 04:24 |
| 6431 | 9 | 2 | 04:30 |

The broken capture had dropped those blocks. The fixed capture restored them. The two flip
rule read a block that had left and come back twice as chrome, and silenced it. Seven of the
nine were policy: the established presence requirement and the whole political entity
eligibility rule. Two were chrome. The hole was open from 04:24 until the indexes were
cleared at 04:35, about eleven minutes, and it was opened by the fix's own first two runs.

That makes it a standing mechanism, not a legacy artifact. Any policy line that a flaky
capture drops and restores twice is silenced permanently until someone clears the index by
hand. With the capture now stable that should be rare. It is not impossible, and the sensor
does not say when it happens: `Record Checked` writes Last Fingerprint, Last Checked,
Status, Consecutive Failures and Block Index, and not the note that carries "newly classed
as volatile chrome". A block going quiet with nothing else changed leaves Status at Stable
and sends no mail. Nobody is told.

All nine `Block Index` fields were cleared and the sensor re-baselined on the clean capture
in execution 6432. Verified after: `first_sight` true on every row, no verdict fired, zero
volatile blocks on any source, all seven policy blocks back in the watched set. The reset
has a cost the first version did not state: every flip counter restarts, so each Meta chrome
block costs up to three more noisy mornings, a Claude call, a mail and an orange row each,
before it is learned again.

## The sensor erased its own material verdicts, and I did it

Execution 6430 fired the assessment on four sources. Two came back MATERIAL. Meta Content Monetization, 04:25:18: `tragedy or conflict`,
`debated social issues` and `objectionable activity` now reduce or disable monetization
"even for fictional or discussion-only depictions", affects NCO Forge and TSWS, action is
to audit NCO Forge framing and thumbnails toward the one carve-out, "explicitly uplifting
manner". Meta Partner Monetization, 04:26:48: a 30 day established presence threshold,
follower and video count minimums for in-stream ads, and a connected entity liability rule
under which one show's violation can strip monetization from the others, affects all
three. Both were mailed and both were written to `AI Verdict`.

They were not the first. Execution 6424 at 03:56, on the last hollow capture before the fix,
had already fired two MATERIAL verdicts, and both were false alarms manufactured by the
missing sections. Meta Content, 03:56:33, confidence high: Meta "adds three new prohibited
monetisation formats", looping videos, text montages and embedded ads, which had merely
reappeared in that capture. Meta Partner, 03:56:56: Meta "removed the established presence
monetization eligibility requirement and the political/government entity ineligibility
rules", which had merely dropped out of that capture. Nothing was added or removed on Meta's
side. Both were mailed as MATERIAL, both went through Record Change, and both were then
overwritten by the 6430 verdicts through the same last write wins path. So the inbox holds
four MATERIAL mails from tonight: the two from 6424 are wrong and the two from 6430 are
right, and nothing in the record said so until this amendment. A hollow capture does not
only hide policy; it invents removals.

Execution 6431, my determinism run five minutes later, fired on the support chat widget and
wrote "not material" over both cells. Execution 6432, the re-baseline, set both rows to
Stable. The 6430 verdicts then existed in Tee's inbox and in execution 6430 and nowhere in
the record. Both were restored verbatim at 05:35 UTC, above
the verdicts that overwrote them with a dated note between, and both rows were put back to
the Changed unreviewed status.

The defect is that `AI Verdict` is last write wins. Any quiet scan erases the material one
before it. That is the same class of failure as the Spotify note earlier the same night,
where a test run destroyed a curated note, and it was caught the same way: by reading the
data back, not by the run reporting success.

## What the fix recovered

From the previously hollow `Restricted categories`. The words are the page's; the heading
is folded into the first line and the paragraph break before "However" is collapsed:

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

`validate_node_config` performs no schema checking on this community node. Run first hand
at 05:38 UTC with five candidates in one call: the real shape, invented keys
(`onlyMainConten`, `waitForrr`, `totallyMadeUpKey`), `resource: NotAResource`, and an
empty parameters object all returned `valid: true`; the control, `n8n-nodes-base.set` with
`mode: notARealMode`, was correctly rejected with the expected values named.
Every "validated" claim any session has made about a community node is worth nothing.

The assessment prompt still described TQO as faceless and named the podcast The Shared
Shadow. A sensor that thinks the shows are faceless misjudges a likeness or voice
cloning rule, which is the highest stakes lane it watches. Both corrected; the prompt
now judges a real added and removed diff rather than re-reading the whole page.

## Gumroad, exercised live for the first time

This is on TQO FINAL V5, workflow `gsGJQan7a6ZufhYt`, nodes `Gumroad: Verify Sale` and
`Gumroad: Normalise Sale`, not on the sensor. The credential Tee created is Header Auth,
not Bearer Auth, id `K1D8KUvTcWDcdrV0`, named "Gumroad OAuth - DEVON OS 29" although it
serves V5; the node was switched to match rather than asking him to rebuild it.
Execution 6422, status error by design because the guard throws, probed with a well formed but
non existent sale id. Gumroad answered HTTP 200 with `success: false, The sale was not
found`, and the guard refused with nothing written. Gumroad returns 200, not 404, for a
missing sale; a guard checking only the status code would have sailed past it.

## The sensor's writes, changed the same night on Tee's ruling

Tee ruled all three sensor changes and the completeness rule at about 05:30 UTC. All four
landed in one workflow update and were proved by manual run before publishing.

**`AI Verdict` is append-only.** `Record Change` now writes the new verdict, a blank line,
then whatever the cell already held, capped at 60,000 characters, newest on top. A quiet
scan can no longer erase a material one. Proving run 6436 exercised it on Spotify, which
fired a not-material verdict onto an empty cell; the two restored MATERIAL verdicts on the
Meta rows were untouched because those rows did not fire.

**A silencing is no longer invisible.** Both fingerprint nodes now emit the text of every
block that crosses the two-flip threshold. A new branch on the unchanged path, `Newly
Volatile?`, routes any such row through `Build Silencing Note` and `Record Silencing`,
which prepend a dated note naming the silenced lines to `AI Verdict`, set the row to
Changed unreviewed, and pass it to `Notify`. The note says how to re-arm a line that turns
out to be policy: clear the row's Block Index. On 6436 the branch ran seven times and
fired zero times, as it should with every counter freshly reset.

**`rawHtml` is out of the custom body.** Formats are `["markdown"]` only.

**The completeness rule.** In both fingerprint nodes, after the 1,000 character floor: a
line ending in a colon that is answered by a heading at the same level or shallower than
the section it sits in makes the capture a reported failure, never a baseline. On the
plain HTTP path, `<h1>` to `<h6>` are turned into markdown headings before tags are
stripped so the rule can see structure there too. Measured on the ten real captures on
disk before deployment: three hits on the known hollow capture, zero on the nine complete
ones. A first version also treated an empty level 2 heading as a hole. Proving run 6436
refused YouTube Shorts on both paths for "Learn more about YouTube Shorts monetization",
a real heading with nothing under it. That clause never produced a true positive and was
removed; re-measured at three and zero.

**Proving run 6436, the rest of it.** Meta Content came back from Firecrawl as `Bad
gateway - the service failed to handle your request`, a 502 on one page while the same
body worked on four others. The node reported it, carried the index forward, and set the
row to Fetch failing with one consecutive failure, rather than baselining on nothing.
Spotify and TikTok each fired a not-material verdict on one-block footer churn. Nothing
was silenced.

**Proving run 6437, after the clause was removed.** Success, 05:49:09 to 05:51:12. All
four plain HTTP pages fingerprinted, YouTube Shorts back at 115 blocks with no hollow
hit. All five Firecrawl pages fingerprinted, Meta Content recovered from the 502 at 186
blocks. `rawHtml` absent on every Firecrawl response, markdown intact. The silencing
branch ran eight times and fired zero. Meta Content fired one verdict, not material, on
+71/-45 blocks that turned out to be Meta serving the en-GB spelling of the same page:
monetisation for monetization, behaviours for behaviors, centre for center. Append-only
held: that verdict sits above the restored MATERIAL one, which is untouched. Published
on that receipt at about 05:56 UTC as `activeVersionId 38857d14`.

## Firecrawl was serving cached copies, found while pinning the locale

Amended 2026-09-08 after #166 merged, when the open items were being closed.

The locale pin was applied first, on its own: `location: { "country": "US",
"languages": ["en-US"] }` added to the custom body and proved on execution 6442. It did
not work. Meta Content came back in en-GB again, 40 British spellings and no American
ones, the same as 6437, while Meta Partner came back in en-US on the same sweep.

Reading Firecrawl's documentation for why gave the actual defect. The scrape endpoint
returns a cached copy of a URL whenever one exists that is younger than `maxAge`, and the
documented default for `maxAge` is 172,800,000 milliseconds, two days. The sensor never
set it. So on every sweep, before the custom body and after it, each of the five
Firecrawl sources could be served a copy up to two days old rather than the page as it
stood that morning. A daily policy sensor cannot run on that: a rule changed on a Monday
could read Stable on the Tuesday and the Wednesday. The locale flips fit the same cause.
The cache is keyed on the URL, so whichever English Meta happened to serve the last fresh
render is what the following sweeps got back, and the pin could not reach a copy that was
never re-rendered. Whether that cache is shared beyond this account is not stated in the
documentation and is unverified.

`maxAge: 0`, which the documentation names as the way to force a fresh scrape, was added
to the custom body and proved on execution 6443. All five Firecrawl sources came back
fresh with status 200. Meta Content came back in en-US for the first time in three sweeps,
no British spellings and 41 American, 29,127 characters of markdown, all three lead-ins
answered by body text, the Tragedy or conflict section present, no hollow sections. The
diff read 45 blocks added and 70 removed, which the verdict called a spelling swap plus a
cookie banner leaving, not material, and filed to the row. Meta Partner, both X pages and
TikTok were unchanged against their baselines.

Whether `location` now holds the locale steady cannot be proven from one fresh sweep. The
claim on record is narrower: with the cache bypassed, one render came back en-US. The
10:00 UTC scheduled firing is the second sample.

What this costs. A fresh scrape is slower and Firecrawl's documentation says it fails more
often. 6443 took 2 minutes 5 seconds against 6442's 2 minutes 9 seconds, so no cost showed
on this run. A failure is reported on the row as Fetch failing, never silently, and the
next morning retries.

What the earlier figures in this doc still mean. Every Firecrawl-path result recorded
above, 6430 through 6437, was produced without `maxAge` set. The 6430 capture itself was
fresh, because it differed from every capture before it, but the stability figures from
6430 to 6437 may include cache hits and are weaker evidence of page stability than they
read as above. The pre-registered grep test was re-run on 6443 and passed on a capture
that is known to be fresh.

The Firecrawl node note now reads 150 scrapes a month, names `maxAge` as load bearing, and
records why. Published as `activeVersionId 138e7ceb` at about 06:33 UTC, before
the first scheduled firing at 10:00 UTC.

## Stated, not papered over

- The completeness rule was measured on the five Firecrawl pages before deployment and on
  the four plain HTTP pages only by proving run. A false positive there shows as Fetch
  failing; 6436 produced exactly one, since fixed.
- Meta's locale flips, read as 116 moved blocks on 6437, traced to Firecrawl's two day
  default cache rather than to Meta alone; see the section above. `maxAge: 0` and a US
  English `location` are live; only the cache bypass is proven, the pin has one sample.
- YouTube Advertiser-friendly guidelines runs at 733 blocks and 76,868 characters, over
  the 30,000 character snippet cap, so on that page a removed block is reported as a
  count and its text is not retained. The prompt says so and forbids guessing what it
  said. Every other watched page is under the cap and keeps removed text.
- `onlyMainContent: false` admitted roughly 28 footer blocks on each X page. A footer
  edit on X now fires a verdict until the learning classes those blocks as chrome.
- `view_sales` on the Gumroad token is inferred from the endpoint accepting it, not
  proven by a successful sale read.
- TQO FINAL V5 was published at 05:35 UTC on Tee's ruling with its six schedule triggers
  disabled first, `activeVersionId 73efec8d`, trigger count seven: the webhooks behind his
  Shortcuts, the run links and the Gumroad guard are live, and nothing runs unattended.
  Each schedule is re-enabled as its own named act.
- The DEVON thread log for this arc was filed on 2026-09-08 after #166 merged, two pages:
  Tee's Gumroad credential receipt verbatim, and the sensor arc. The Context Pill pointer
  was revised the same morning: faceless framing retired, OS 29 live, V5 published dark.
- X's "created or posted using automated means" exclusion is unresolved against an AI
  scripted, AI voiced pipeline and needs a ruling before TQO plans X revenue.

## DEVON RECEIPT

```
AREA: OS
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_os29-platform-policy-sensor_v2_2026-09-08
DATE: 2026-09-08
DECISIONS: Tee ruled a block-level diff with self-learned volatile blocks over a similarity threshold; fix the Firecrawl capture rather than the comparison; watch the X successor as a new row and leave his curated note alone; Systems primary and Money cross-reference for the Gumroad credential; no calendar rotation for the Gumroad token, scope reduction and exposure triggers instead; the Gumroad Application ID and Secret stay unwired
FINDINGS: the v1 coverage claim was true of fetch and false of capture, Meta Content Monetization had three hollow policy sections since the sensor was built; root cause was waitFor 0 and onlyMainContent true, both Firecrawl defaults in force because the node sent no options; the fix's own first two runs pushed seven real policy blocks on Meta Partner over the two flip threshold and silenced them for eleven minutes until the indexes were cleared, and the mechanism is standing, with no signal to a human when it fires; execution 6424 produced two false MATERIAL alarms from the hollow capture, one of them reporting a removal that never happened, and execution 6430 produced two real MATERIAL verdicts which execution 6431 overwrote, restored by hand at 05:35 UTC; the Tragedy or conflict restriction governing NCO Forge on Facebook was never captured before tonight; the March 3 2026 AI conflict disclosure rule carries over into X Original Content Rewards verbatim; validate_node_config returns valid for anything on community nodes; Gumroad returns 200 not 404 for a missing sale; Firecrawl's documented default maxAge of two days meant every Firecrawl sourced sweep could be served a cached copy, fixed with maxAge 0 and proven fresh on execution 6443
OPEN: view_sales inferred not proven; V5 published with schedules disabled, activeVersionId 73efec8d, each schedule re-enabled as its own named act when Tee can watch it; the location pin has one fresh sample and the 10:00 UTC firing is the second; X automated means exclusion needs a ruling
STATUS: OS 29 active, activeVersionId 138e7ceb, daily 06:00 America/New_York, nine sources watched, Firecrawl on a custom body with maxAge 0 and US English location, completeness rule live on both paths, AI Verdict append only, silencing routed to the notify path, rawHtml dropped, zero volatile blocks, both restored MATERIAL verdicts intact with newer verdicts stacked above them; the first scheduled firing is 10:00 UTC on 2026-09-08, the same morning, and a check-in is armed for 10:20 UTC that day
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
