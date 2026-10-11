# Carousels

Ruled by Tee on 2026-10-07: one carousel per episode, automatic, from our own
HTML templates, delivered as files for review only. Nothing here posts, and
nothing writes to the instance.

TQO FINAL V5 already writes each episode's carousel as text. The packaging
step returns 7 to 9 one line slides cut from a framework in the script, the
hook first and the Quiet Move (TQO) or Forge Rule (NCO) last, and Parse
Packaging stores them in the row's `platform_packaging` as a `CAROUSEL` block.
This directory draws them.

| file | what it does |
|---|---|
| `parse.mjs` | reads the `CAROUSEL` block out of `platform_packaging` |
| `check.mjs` | refuses a carousel that breaks the packaging rules (7 to 9 slides, at most 12 words a slide, the right closing slide), carries a dash, or states a figure the row's own script does not |
| `templates.mjs` | the two slide templates, 1080 by 1350 |
| `render.mjs` | reads both content tables, checks, draws every slide and a contact sheet in Chromium, writes `summary.md` |
| `carousel.test.mjs` | the rules, with no browser, in the standalone CI job |

`.github/workflows/carousel-render.yml` runs it daily at 12:13Z, after the
script and promote passes, and uploads the slides as the run's artifact with
the summary on the run page. Locally:

```bash
PLAYWRIGHT_MODULE=$(npm root -g)/playwright/index.mjs node tools/carousel/render.mjs --out out/carousels
node tools/carousel/render.mjs --from tools/carousel/fixtures/rows.json --out out/carousels
```

A row is drawn when its status is past Idea and not Error and it has a
`CAROUSEL` block. Rows get that block when they are packaged, so on the first
run only TQO row 4 had one.

## The two looks

TQO follows its brand package v2 (`TQO_Brand_Package_v2`, revision
2026-09-30), which Tee handed over and ruled in on a card on 2026-10-11: deep
navy `#0A1628` as the ground, Amber Gold `#D4A017` for the wordmark, labels and
mark, the package's proposed warm off-white `#F4F0E8` for text, and Inter Bold.
The mark is "The Denominator", a fraction bar over one dot, drawn as vector in
`templates.mjs` so the gold is the exact hex rather than a generated pixel. It
sits on the cover and on the closing slide, where it replaced the hand drawn
tick. The memo layout from `sites/tqohq/DESIGN.md` (labels beside values, flat,
no card) is kept. The package's own PNGs are raster concepts it marks as not
production masters, so none of them is used.

NCO Forge stays on its brand package v1 by the same ruling, because its v2
package marks its gold and olive as proposals and its anvil and chevron emblem
is not the mark Tee ruled in. It follows v1 on Tee's Drive
(`NCO_BRAND_brand-package_v1`, 2026-08-03, read through its 2026-09-24 text
extract): Deep Navy `#0A1628` as the ground, Gold `#C5A46E` for the wordmark,
labels, Olive `#3D4F2F` for the rule under the wordmark, and Inter, one of
the package's recommended bold sans serifs, subset into `fonts/` under its OFL
licence. The wordmark is set in type. The mark, a shield with an anvil and a
star in the package's gold and olive, is `brand/nco-mark.png`, cropped to 480
px. Tee generated it from a prompt and ruled it in on 2026-10-07; it sits on
the cover and on the closing slide in place of the gold Forge Rule block. The
generator's background removal had punched four holes through its olive
field, and they were filled with the field's own colour before it went in. Both v2
packages were too large for the Drive connector until Tee uploaded them to the
session on 2026-10-11, which is when they were read.
The sample in `fixtures/rows.json` is labelled as a sample and is not an
episode.

## What it does not do

It does not check a slide against the row's approved sources directly. It
checks every numeral against the row's script, which passed the Sources Gate,
so a slide cannot state a figure the episode was not allowed to. A claim in
words alone is not checked, the same limit the gate has.
