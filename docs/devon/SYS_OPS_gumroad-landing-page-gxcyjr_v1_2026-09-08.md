---
title: Gumroad landing page for gxcyjr, built and sanitizer clean, publish held for a ruling
type: SYS_OPS
version: 1
date: 2026-09-08
area: TQO
status: preview-clean-publish-held-for-ruling
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
base: c31a7fe
branch: claude/video-analysis-incorporation-9h6rtc
supersedes: none
---

# Gumroad landing page for product gxcyjr

## Verdict in one paragraph

Tee asked for a custom landing page on Gumroad product `gxcyjr`, built and
published. The page is built, passes Gumroad's own server side sanitizer with
nothing removed, renders in light and dark mode at phone and desktop widths,
and carries the pay what you want checkout pattern Gumroad's template
prescribes. It is not published. Reading the product before writing to it
found an empty shell: no description, no files, no covers, zero sales, listed
at `$0+`. A landing page on that product would take money for nothing, and
the page's own delivery line would be a promise the product cannot keep. That
is Tee's call, not a session's, so the publish is held and the record hands
it back with the publish step reduced to one word in one node.

## What Tee asked, and what could not be done his way

The ask was Gumroad's landing page template: one self contained
`landing.html`, responsive, accessible, light and dark, at least one buy
element or a `gumroad:checkout` message so the product stays purchasable,
`data-gumroad-field` for the live values with fallbacks for rating and review
count, a price input for pay what you want that posts the price itself, own
Gumroad links plain, preview through the sanitizer until the report is clean,
publish, confirm the URL, then load the live page and click through to
checkout.

The template's tooling is the Gumroad CLI. It is not installed in this
container, and it could not be used if it were: outbound requests to
`gumroad.com`, `api.gumroad.com` and `public-files.gumroad.com` are refused by
the environment's proxy with a 403 on the CONNECT, re-checked at 09:25 UTC.
So the sanitizer, the publish and the read back all go through n8n Cloud,
which reaches Gumroad, using the existing header credential
`K1D8KUvTcWDcdrV0` by id. The one step that still cannot be done from a
session is the last one: loading the live page and clicking through to
checkout is Tee's, from his phone.

## What the product is

Read live on execution 6465 at 09:37 UTC, not from memory:

| field | value |
|---|---|
| name | Executive Efficiency OS |
| published | true |
| price | `$0+`, customizable_price true, usd |
| description | empty string |
| files | none, `file_info` empty |
| covers, thumbnail, preview | none |
| tags, variants, custom fields | none |
| sales_count | 0 |
| custom_html | null, so no landing page exists today |
| landing_url | `https://tdveal.gumroad.com/l/gxcyjr` |
| refund policy | inherited from the account |

DEVON holds no record of this product. The name, the price and the seller's
identity are the only facts the page could state without inventing anything,
and those are the only facts it states.

## What was built

`landing.html`, fourth revision, 18,046 bytes, sha256 prefix `34788939bdf17e2a`. One `<main>`
with an inline `<style>` and one inline `<script>`, no external script, style,
font or image host, no Tailwind. What is on it:

- A skip link to the price section, a header naming The Quiet Operator with a
  plain link to the storefront, and a hero whose `<h1>` carries
  `data-gumroad-field="name"`. The rating line carries the `rating` and
  `review-count` fields with "Be the first to review" as the fallback the
  template asks for.
- "Who made this": Terrance Veal, retired Sergeant First Class, The Quiet
  Operator. "How I work": proof over hype, a human watches every release,
  owned not rented. Nothing in either section is a claim about the product.
- "What you get" is a container with `data-gumroad-field="description"` and a
  fallback sentence saying the description appears once it is written. Gumroad
  interpolates the product description here, so the page tracks the listing
  rather than duplicating it.
- "Name your price": the listed price by field, a numeric input, four quick
  amount chips (free, five, fifteen, thirty), a button that posts
  `{type: "gumroad:checkout", params: {price}}` to the parent with `price`
  present only when the input holds a valid number of zero or more, and a
  `<button data-gumroad-action="buy">` beneath it as the second door. The
  custom price button does not carry `data-gumroad-action`, per the template.
  Enter in the field fires the same handler, a second press within 1.5 s is
  ignored, and if nothing has opened after four seconds the status line says
  to use the second door.
- Four questions: paying zero, delivery, refunds, and an AI disclosure. A
  footer that says the page was built with AI assistance under Tee's
  direction.
- Dark mode by `prefers-color-scheme`, reduced motion honoured, a sticky
  bottom bar on phones that appears once the price section has scrolled out of
  view, and `:focus-visible` outlines throughout. The scroll reveal is an
  enhancement: nothing is hidden until the script has taken the page over, so
  with scripts blocked every section, the price input and both buy doors are
  visible.

Rendered under Chromium at 390 by 844 and 1280 by 800 in both schemes, with
axe-core 4.13.0 reporting no violations once the reveal transitions have
settled; run mid-transition it reports partial-opacity text as contrast
failures on every revision, which is the sampling, not the page. The
screenshots were sent to Tee in the session. The page is not a description of
the product. It cannot be, since the product has none.

## How the bytes reach Gumroad

Workflow `vrcLMw802tgf3MpY`, "Gumroad Landing Page Helper (gxcyjr)", in Tee's
personal project. Manual trigger only, never published, registered in the
vault the same day. Seven nodes:

`Run` then `Action`, a one line Code node holding the word for this run, then
`Job`, a Code node that carries the page as base64, decodes it, and refuses to
continue unless the sha256 prefix and byte length match the constants it was
written with, so a transcription error can never reach Gumroad. `Read only?`
sends `read` to a GET on the product and everything else to an HTTP node
whose method, URL and body come from `Job`: `preview` posts to
`preview_custom_html`, `publish` PUTs `custom_html`, `clear` PUTs an empty
string. `Read back` reduces the response to status code, success, warning,
message, the sanitizer report and the product fields worth recording,
including the length of any `custom_html` already on the product.

The credential is bound by id on both HTTP nodes. No token appears in any
parameter, note or code, and none was typed by a session.

## What the sanitizer said

Execution 6474 at 10:28 UTC, action `preview` on the fourth revision, HTTP 200:

```
success: true
warning: null
message: null
sanitization_report: {removed_tags: [], removed_attributes: [], total_removed: 0, truncated: false}
```

The second and third revisions had returned the same empty report on 6464 at
09:23 UTC and 6472 at 10:09 UTC. Execution 6471 is a stray `read` run before
the third payload was loaded; it changed nothing and is on the instance.
Nothing removed on any of the three previews. Gumroad normalised the markup on the way through: SVG
`viewBox` came back lowercased, self closing SVG elements were expanded to
open and close pairs, the star entity was decoded, and whitespace inside the
three cards changed. Lowercase `viewbox` is corrected by the HTML parser's
SVG attribute adjustment, checked in Chromium the same hour: an SVG inserted
with `viewbox` reads back `viewBox="0 0 24 24"` with a base value width of
24. Earlier probes of the same sanitizer on this helper found that it strips
`noscript`, `meta`, `link`, foreign iframes, form `action`, `inputmode`, SVG
`<text>` and `focusable`, and keeps `<style>`, inline `<script>`,
`data-gumroad-*`, ids, classes, aria attributes, inputs, buttons, labels,
`details`, `dialog`, `svg` and `picture`. The shipped file contains none of
the stripped items, which is why the report is empty rather than tolerated.

## Fresh critic

The second revision went to a subagent that had seen only the file, Tee's ask
and the product facts, with instructions to attack it. It returned
PASS-WITH-CONDITIONS and six findings that held up on re-reading, each with a
measurement:

| finding | measurement | fixed in the third revision by |
|---|---|---|
| the price section started at opacity zero and only the script revealed it, so with scripts blocked the product was unpurchasable from the page | JS-off render: price opacity 0, buy button and second door invisible | the hide rule applies only once the script adds a class to the root |
| the second buy door was an `<a>` with no `href`, unreachable by keyboard and read as plain text | Tab from the buy button skipped it; ARIA snapshot read `text`, not `link` | a `<button type="button">` styled as a link, which Gumroad's delegated handler accepts per the template |
| if Gumroad interpolates the empty description the fallback vanishes and "What you get" heads an empty box | simulated: section text "What you get", box 50 px tall | the section hides itself when the description container is empty, by CSS `:has()` and by the script |
| "Your access link arrives by email" promised delivery on a product with no files | product read: `file_info` empty | replaced with "Through Gumroad, which handles checkout, the receipt and delivery. Nothing is sent by hand." |
| after the buy click the status said "Opening Gumroad checkout." forever, and the catch branch could never run | status unchanged five seconds after an ignored message | a four second hint pointing at the second door; the dead branch removed |
| the price field's boundary failed the 3:1 non-text contrast minimum in both schemes | border against page 1.22:1 light, 1.40:1 dark | border colour moved to the muted ink token, 5.72:1 against the page and 6.33:1 against the card in light |

Nine minor findings were taken as well: `aria-label` on a span and a
paragraph (prohibited on those roles), the FAQ marker glyph inside each
question's accessible name, chips stealing focus into the input and raising
the phone keyboard, values the input marks invalid still being posted, Enter
doing nothing and a double click posting twice, no background painted behind
the fragment, the TQO descriptor borrowing NCO Forge's audience line, the
description fallback pointing at a listing this page replaces, and the arc
having no record in the repository. Two of its minor notes stand as residual:
a comma typed as a decimal separator becomes a different number in Chromium
(the button label shows it before anything is posted), and whether Gumroad's
wrapper paints its own body background is unverified from here.

Every fix was measured in Chromium before the third revision went to the
sanitizer: with scripts off the price section, the buy button and the second
door all render at opacity 1; Tab from the buy button lands on the second
door; the parent receives `{}` for a blank field, `{price: "0"}` for zero,
`{price: "12.5"}` for 12.5, nothing for a negative or a sub-cent value with a
status message instead, `{price: "1000"}` for `1e3`; Enter posts once, a
double click posts once, the hint appears after four seconds; a chip click
leaves focus on the chip; an emptied description hides its section and a
rich one renders inside it; reduced motion leaves every section at opacity 1.

The same critic was then handed the third revision to re-verify each finding
against the new file, told not to assume anything had been fixed. Its second
report marked all six majors and all nine minors FIXED, each with its own
measurement, found no regression across the chips, sticky bar, skip link,
reduced motion, rating fill and rich description cases, agreed that the
mid-transition axe reads are sampling artefacts, and returned
PASS-WITH-CONDITIONS with the flagship bar met and every remaining condition
outside the file: attach a deliverable to the product (or a ruling that a
placeholder may sell) before `publish`, then the live click through. It left
three small items, taken in a fourth revision the same hour: the second buy
door rendered 22 px tall, under the 24 px target size minimum, and now
renders at 24; the `:has()` rule and the `.hide` rule shared one declaration,
so a browser without `:has()` would have dropped both, and they are now
separate; and the price input had no upper bound, so `1e21` posted a
twenty-one digit price, and it now carries `max="99999"` with a message that
names the range. The hint after a buy click also now names the second door by
its own text. Measured in Chromium before the fourth preview: the door is 24
px tall, `.hide` works on its own, `1e21` and `100000` are refused with the
range message, `12.5` still posts, the hint reads as written, and axe stays
clean in all four settled renders.

## Why the publish is held

Three things, in order of weight.

**The product delivers nothing.** No files, no rich content, no custom
delivery URL, an empty description. A buyer who pays five dollars through this
page receives a Gumroad receipt and an empty library entry. Gumroad's native
page today has the same buy button on the same empty product, so the landing
page does not create the problem, but publishing a page whose whole job is to
convert makes it worse on purpose. Under the house rule that compliance items
have no exception path, taking payment for an empty product is not a call a
session makes.

**The page cannot say what the buyer gets.** The delivery answer now says
only what is true, that Gumroad handles checkout, the receipt and delivery.
It still stands over a product whose library entry is empty, and no copy fixes
that; only a file does.

**The chips are an anchor nobody chose.** Free, five, fifteen and thirty
dollars were picked by a session to give the input a starting point. They are
not wrong, but they are the only numbers on the page that came from nowhere,
and Tee should either own them or replace them before they meet a buyer.

Underneath all three: nothing ships without a human watching it end to end,
and the end here is the checkout on the live page, which only Tee can reach.

## To publish, to check, to roll back

Each is the same act: open workflow `vrcLMw802tgf3MpY`, set the one word in
the `Action` node, run it, read the `Read back` node.

1. `publish`: expect HTTP 200, `success: true`, `warning: null`, and the same
   empty sanitizer report as 6474. The report on a publish reflects what
   actually shipped.
2. `read`: expect `custom_html_length` near 18,046 (the sanitizer normalises
   the markup, so the stored length may differ) and `landing_url` unchanged.
3. Load `https://tdveal.gumroad.com/l/gxcyjr` on the phone in both light and
   dark mode, enter a price, tap "I want this", and confirm the Gumroad
   checkout opens carrying that price. Tap the plain link beneath it and
   confirm the default checkout opens. Until that has happened, the page is
   published, not proven.
4. `clear`: the rollback. One run restores Gumroad's native product page.

Republishing the same file is idempotent: the PUT replaces `custom_html`
whole, and the gate refuses any bytes that are not the reviewed ones.

## What was not verified

- The live page and the checkout click through, for the reason above. The
  `gumroad:checkout` message was proved only inside a local harness that
  listened on the parent window; that Gumroad's parent handles it as the
  template says is trusted from the template, not observed.
- How Gumroad renders the interpolated description when it contains rich
  markup. The container styles headings, lists and images inside it, but the
  product's description is empty, so nothing was interpolated in the preview.
- Whether the fallback text in the `rating` and `review-count` spans survives
  on a product with reviews. It has none.

## DEVON RECEIPT

```
AREA: TQO
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_gumroad-landing-page-gxcyjr_v1_2026-09-08
DATE: 2026-09-08
DECISIONS: publish held for Tee's ruling; helper workflow vrcLMw802tgf3MpY registered in the vault as manual and never published; the sha256 and byte length gate on the payload is the rule for anything a session sends to Gumroad
FINDINGS: product gxcyjr is an empty shell, no files, no description, no covers, zero sales, custom_html null, read on 6465; landing.html fourth revision 18,046 bytes sha 34788939bdf17e2a passed the sanitizer with total_removed 0 on 6474, after a fresh critic found six majors in the second revision (price section hidden without JS, second buy door not a link, empty description box, delivery promise on a product with no files, buy status stuck, input boundary contrast), all fixed and confirmed fixed by the same critic's second pass, whose three leftovers (24 px target size, coupled :has() rule, unbounded price input) went into the fourth revision; the container cannot reach gumroad.com so preview, publish and read back run through n8n on credential K1D8KUvTcWDcdrV0; lowercase viewbox from the sanitizer is restored by the HTML parser, checked in Chromium
OPEN: whether to publish on an empty product, and if so whether the delivery line and the four price chips stand; the live page and checkout click through are Tee's; description interpolation with rich markup and the rating fallback on a reviewed product are unobserved
STATUS: built, fourth revision sanitizer clean on 6474, critic PASS-WITH-CONDITIONS with every condition outside the file, not published, one word in the Action node from live and one word from rolled back
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
