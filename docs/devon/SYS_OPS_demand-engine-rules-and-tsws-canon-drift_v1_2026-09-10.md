# Demand engine rules, and three TSWS canon drift findings

Session capture, 2026-09-10. Two unrelated jobs landed in one thread: an
outside video analysed for what transfers to the content operation, and a TSWS
question that turned up canon drift in the estate. The second is the one that
matters.

## Source: a KDP demand engine video

`https://youtu.be/_QcuQRBrASA`. Transcript pulled through vidIQ. Title,
channel, publish date, view count and duration are all UNVERIFIED: the vidIQ
metadata call needed an approval this session did not hold, and youtube.com is
blocked by the network egress proxy. The video leans on on screen charts and
dashboard screenshots that were never seen, so this is an audio only reading.

Structurally it is a case study VSL for a paid coaching community. Proof stack,
mechanism, two case studies, mid roll offer, two more case studies, principle,
close. The presenter labels his own pitch section out loud.

The thesis: discovery moved off Amazon search and onto the social feed. The old
loop was find keyword, publish, run Amazon ads to rank, keep paying or vanish.
The new loop is create attention on TikTok or Instagram, convert it in TikTok
Shop, and let outside traffic and sales velocity pull organic Amazon rank, so
one asset earns twice. His compression: the moat is no longer the keyword, it
is the ability to manufacture attention.

That thesis is correct and it is not new. It is the same logic as any creator
who owns distribution instead of renting placement.

### Claimed numbers, none verified

Proper nouns below are garbled by the ASR and are recorded as heard.

| Subject | Claim |
|---|---|
| Larkin Road | 2.25M on TikTok Shop, January through July; about 12K per day; 30K peak day |
| Claremont Road Books | about 80K per month TikTok Shop; 80K to 100K per month KDP, estimated via Book Beam |
| A client, Amar | one Instagram reel; 3.7K peak day; stabilised 1K to 1.5K per day; 20K to 30K per month profit |
| The Fallen Poet | about 1K per day royalties, no Amazon ads |
| The presenter | 113K on his top KDP title last year; 250K TikTok Shop year to date |

Every figure is self reported or estimated by a third party tool. Book Beam
numbers are BSR derived guesses, not royalty statements. He states outright
that he does not know one subject's ad spend or margins, then presents the
revenue anyway. That is the honest tell and the reason to discount the proof
stack heavily.

### Where the argument is weak

Attribution is asserted rather than measured. The whole spillover claim needs
TikTok attention to cause Amazon sales, and nobody shows attribution data,
because without Amazon Attribution links it is close to unobtainable. The
direction is plausible. The magnitude is unestablished.

Survivorship is buried inside his own best case. Claremont took four months and
roughly 200 videos before anything clicked. Said once, quietly, while the 2.25M
figure gets a chart.

Platform concentration is never addressed. The engine sits on TikTok Shop, one
policy change away from zero. The Amar case is the counterexample he appears
not to notice he is holding: pure Instagram, no shop, no ad spend, and it
worked.

Assessment: 6.5 of 10 as a read on a real shift, 3 of 10 as evidence.

## Two standing rules taken from it

Neither rule was written down in the estate before today.

**Rule: reusable creative architecture.** The strongest case study's winner was
an eleven second format, one emotional hook, one sound, and only the footage
swapped. Five of their top ten seasonal videos were the same asset re shot.
Apply this at the clip level, not just the episode level: one proven Short
skeleton per show, with the payload rotating inside it, rather than a new
format per topic.

**Rule: prove the angle before you scale it.** His line is that you should not
recruit affiliates to discover your positioning, you give them positioning
worth multiplying. The same holds for any distribution partner, repurposing
lane, or automation pointed at a show. Prove the converting hook by hand first,
then let the machine copy it. Scaling an unproven angle only buys volume of
nothing.

Not imported: the seasonal variant playbook. It works for gift books because
the product is disposable and the buyer is not the reader. The shows here run
on a returning audience and an owned voice, so cloning one emotional promise
under new labels would read as churn.

## TSWS canon drift, three findings

Surfaced while answering a question about environmental themes for the podcast.

**Finding 1: the installed brand skill is five weeks stale, and it is the root
cause of the other errors in this session.** `shadow-we-share-brand-UPDATE.md`
in Drive (id `1K0_KAuFOewWG5LRmNVntZuZpGhW8CvP6`, 3,520 bytes, dated
2026-08-04) opens by instructing that it be applied to the existing skill, not
forked, with a version bump and reviewed date on apply. The skill loaded in
this session contains none of it. Missing from the installed copy:

- the naming ruling, closed, that the show is The Shadow We Share while The
  Shared Shadow is the world the souls stand in, the environment, the heart
- the season architecture, nine themes against 108 episode realms
- the thumbnail tier system, episode, season, series and caption cards
- the environment engine, section 5, which is exactly what was asked about
- the working law that volatile values live as data the consumers read and
  never inside prompts or templates

Consequence measured in this session: two wrong answers given to Tee in a row.
The living mark was called almost certainly Three.js and a react-three-fiber
path was recommended, when the delta states it is the p5 system. Environmental
themes were described as a parameter layer on the mark, when canon says season
palettes wear on the world only and the mark never wears them.

**Finding 2: five copies of the living mark, precedence unresolved.**
`TheShadowWeShare_logo_3D.html` exists five times across four Drive folders.
Four are 30,263 bytes. The newest, 2026-08-06, is 30,265 bytes and is the only
one that differs, and it does not carry the "THE LIVING MARK, source of all
exports" title. That title sits on the 2026-08-01 copy in a different folder.
The 08-06 copy does sit alongside `mark_capture.html` and the current PNG
exports, which reads like the live bundle, but that is inference and not a
ruling.

**Finding 3: WITHDRAWN, same day.** It was raised as `engine.realm` being one
byte and therefore a truncated or failed write. Checked rather than assumed:
the file decodes to a single newline, and its folder
(`1xZx8qdUI3bYhSce8jlRQr7BLntJnMc-H`) holds `flutter_tools.snapshot`,
`flutter.version.json`, a `dart-sdk` directory, and stamps for
`gradle_wrapper`, `material_fonts`, `ios-deploy`, `libimobiledevice` and
`openssl`. That is a Flutter SDK `bin/cache` directory synced into Drive.
`engine.realm` is Flutter's own artifact tracking file and has nothing to do
with TSWS or the render pipeline. One newline is normal for it.

Recorded rather than deleted, because the error is the useful part: a byte
count was raised as a finding before its blast radius was worked out, which is
the over-calling this estate's first law names explicitly. The check that
settled it cost one download and one folder listing.

## What already exists, so nobody goes shopping again

The question asked was which renderer could produce the environmental themes.
The answer is that the pipeline is already built and the stale skill hid it.
Confirmed present in Drive: `mark_capture.html` (33,409 bytes, 2026-08-06), a
written contract for it describing a frame accurate wrapper rebuilt 2026-08-04
that ships in the studio bundle, `stub_mark_capture.html`, `trailers.json`
(10,949 bytes, nine trailers by ten scenes), and `mark_still.png`,
`mark_still_full.png` and `mark_poster.png` dated 2026-08-06.

The mark side is fully specified by the delta: deterministic replay, theta
4.051 within the range 3.85 to 4.25, seed 72126, trail build 4.5 seconds,
`?ambient=0` for compositing, and `mark_html` passed explicitly to force a live
capture.

The environment side is described in the delta as 108 realms mapped to motif
recipes, season keyed for recurring names, with unknown names deriving
deterministically rather than failing, and season palettes worn at whisper
level on the world only. Whether that engine is built or only documented is
UNVERIFIED. The engine code was not read in this session.

## Same day update: the delta is applied and the engine is located

Tee ruled the same session: apply the delta, and the engine is built on n8n.

The delta is applied. `shadow-we-share-brand` was not committed to this
repository, it loaded from an ephemeral synced directory in the container, so
editing it there would have died with the session. It is now committed at
`.claude/skills/shadow-we-share-brand/SKILL.md`, stamped Canon v2, applied
2026-09-10, reviewed 2026-09-10, with all six delta sections merged in and the
pre-existing canon text preserved verbatim rather than rewritten.

The n8n lead is confirmed and the estate is larger than the delta implies.
Six live workflows, all last updated 2026-08-12: TSWS 00 Render Job, a sub
workflow bridging n8n Cloud to the TSWS render worker that accepts type and
params, submits and polls; TSWS 01 Post-Production Master, which watches the
drop folder and runs an episode end to end including rendering the mark and
compositing; and 02 Narration and Sound Bed, 03 Visual Assembly, 04 Detail
Recovery, 05 Conform and Grain. TSWS 00 is the render job the delta keeps
referring to.

No n8n workflow is named for the environment engine, so the realm painting
most likely sits inside the render worker rather than in n8n. That remains
UNVERIFIED. The worker was not read.

One operational risk this creates: the container still carries a synced copy
of the skill at the stale pre-delta version. Two copies of one skill name can
load together and the wrong one can win, which is the failure this repository
already documents for pinned plugins. The synced copy needs retiring at its
source.

## DEVON RECEIPT

```
AREA: TQO, Podcast
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_demand-engine-rules-and-tsws-canon-drift_v1_2026-09-10
DATE: 2026-09-10
DECISIONS: Tee ruled the neta.art assessment out of this capture and the rest of it in, then ruled to apply the 2026-08-04 delta and stated the environment engine is built on n8n; no ruling yet taken on which of the five logo files is the source of exports
FINDINGS: the installed shadow-we-share-brand skill is five weeks behind a 2026-08-04 canon delta and caused two wrong answers in this session, calling the p5 living mark Three.js and describing environmental themes as a parameter layer on the mark when canon says the mark never wears season palettes; five copies of TheShadowWeShare_logo_3D.html exist across four Drive folders with the newest two bytes larger and not carrying the source of exports title; a third finding about engine.realm being a truncated write was raised and then WITHDRAWN the same day, the file being Flutter's own cache artifact and not TSWS at all; the KDP demand engine video rates 6.5 of 10 as strategy and 3 of 10 as evidence, with every revenue figure self reported or Book Beam estimated and the attribution claim asserted rather than measured; two standing rules were extracted that the estate did not previously hold in writing
OPEN: rule on which of the five logo files is the source of exports, the 2026-08-06 copy being the only one that differs and the only one sitting with the current bundle while the source of exports title sits on the 2026-08-01 copy elsewhere; retire the stale synced copy of shadow-we-share-brand at its source, the container copy having been deleted 2026-09-10 after confirming it carried none of the delta, but it resyncs from the account and will return; read the TSWS render worker to confirm the environment engine is implemented there rather than only documented; video title, channel, publish date and view count remain unverified because vidIQ metadata needed an approval not held and youtube.com is egress blocked
STATUS: capture filed; delta applied and committed as Canon v2 at .claude/skills/shadow-we-share-brand/SKILL.md; n8n render pipeline confirmed as six live workflows fronted by TSWS 00; one finding withdrawn on inspection; the mark was verified by rendering it headlessly from the 2026-08-06 file at 2000px on the canonical angle and published as a live viewer; two open items remain, one of them a ruling only Tee can make
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
