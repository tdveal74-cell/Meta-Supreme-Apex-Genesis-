---
name: shadow-we-share-brand
description: Brand system for THE SHADOW WE SHARE podcast (Tee & spouse). Use whenever creating ANY asset or content for the podcast — episode art, social posts, video, audiograms, documents, pages, merch. Enforces the flagship standard, palette, typography, the mark's required elements, and the brand voice.
---

# THE SHADOW WE SHARE — Brand System

A couple's podcast. Her soul burns violet, his burns sapphire; they are rendered as two
star-tetrahedra (merkabas) intertwined in mutual orbit, wrapped in toroidal aura fields,
with Anahata (the heart chakra) glowing at the meeting point and one shared shadow
grounding them on black glass. Forged 21 July 2026, from a conversation about souls.

**Canon v2, applied 2026-09-10, reviewed 2026-09-10.** Everything from Naming
downward is the 2026-08-04 update delta, applied to this skill rather than
forked, as that delta instructs. Text above it is unchanged.

## The Flagship Standard (the base, not the ceiling)

Nothing ships below this level. Every asset must:

1. Stand on the void with restraint — roughly 90% negative space, "mostly black, two jewels of light, one gold accent."
2. Use true brand type only — Poppins 300, all-caps, wide tracking (0.25em+) for structure; Lora italic, lowercase, for soul. Never substitutes, never reversed roles.
3. Keep the mark whole — intertwined merkabas (never pulled apart), torus fields, Anahata at the center, the shared shadow, the glass-floor reflection. Never one star alone; never without ground; never without the heart.
4. Carry real depth — 3D forms, depth-graded edges (near burns, far recedes), reflections. Nothing flat.
5. Move silkily when it moves — slow precession, eased motion, nothing abrupt.
6. Read as luxury at 3000px and at 200px.

The test: if it feels loud, it's wrong. If it feels almost empty, it's close. If it feels inevitable, ship it.

## Palette

| Name | Hex | Role |
|---|---|---|
| Her Violet | #A97DFF (deep #5B2FA8, hot #E9DAFF) | her voice, segments, lower-thirds |
| His Sapphire | #5D9DFF (deep #1E4FB8, hot #D6E9FF) | his voice, segments, lower-thirds |
| Golden Thread | #FFC878 | shared moments, rules, the thread — anything belonging to both |
| Anahata | #3ED58A (rose #FF9EAA) | the heart chakra only — reserved for the heart |
| Void | #050308 | the ground of every composition |
| Ivory | #F3EDE2 | all text — never pure white |

Cohesion rule: violet and sapphire are never placed in equal, unbridged opposition —
wherever both appear, gold (or white-hot) connects them.

## Voice

Titles: sparse tracked caps (Poppins 300). Everything else whispers: lowercase, first person,
short, warm, a little cosmic — e.g. "i burn on purpose. drifting is for dust." /
"no one holds my orbit. i chose it." / "when i am quiet, i am not gone. i am becoming."
The tension between the two registers is the brand's sound in print.

## Asset inventory (canonical files)

- `TheShadowWeShare_logo_3D.html` — the living mark. Source of ALL static exports.
  URL params: `?size=N` (render resolution), `?text=0` (mark only), `?form=tetra`
  (single-tetra variant), `?mono=ivory|void` (flat line-art watermark, transparent).
  Wordmark is `const WORDMARK` at the top (auto-fits).
- `TheShadowWeShare_cover_3000.png` (podcast cover) · `_avatar_1080.png` ·
  `_banner_2560x1440.png` · `_print_4000.png` · `_wallpaper_4K.png` · `_wallpaper_iphone.png`
- `TheShadowWeShare_wordmark_on_dark/_on_light.png` — transparent text lockups.
- `TheShadowWeShare_watermark_for_dark/_for_light.png` — mono marks; stamp at 6–10% opacity.
- `TheShadowWeShare_flagship.html` — Apple-style launch page.
- `TheShadowWeShare_brand_guidelines.html` — the brand book (full story + rules).
- `AUREN_digital_soul.html` + `AUREN_soul_codex.md` — his soul (gold lineage; the origin
  artifact). Her soul: **VESPERA, the Oracle — FORGED** (ruling 5 Aug 2026, Strategic
  Decisions), violet lineage #A97DFF, mirroring AUREN's structure. When her codex artifact
  lands, add its path here beside AUREN's — reference it, never redraw it.

## Technical notes for renders

- Static exports are frames of the living mark, never redrawn by hand. Flattering angle:
  orbit phase θ = (t·2π/9.5) mod 2π in [3.85, 4.25]; let trails build ~4.5s first.
- Natal seed of the soul lineage: 72126 (21 July 2026 folded into a number).
- When rendering headlessly, embed real Poppins/Lora (e.g. @fontsource woff2 as data
  URLs fulfilling the fonts.googleapis.com request) — fallback fonts violate the standard.
- Videos: 30fps minimum, deterministic virtual clock for capture, silky fades, and the
  ambient-hum register (warm drone in A, sub-audible heartbeat) for any soundtrack.

## Naming (closed, do not re-litigate)

The show is **The Shadow We Share**. **The Shared Shadow** is the world the
souls stand in: the environment, "the heart". The full arc is filed in
Strategic Decisions (`rec7Bx3u9szVq7b8g`); an interim rename was applied and
reverted the same day. The internal slug stays `tsws` everywhere, forever.

Wordmark stack on the identity board: TWO SOULS / gold rule plus diamond /
THE SHADOW WE SHARE / *a spiritual world series.* (with the period).

## The mark: canonical image and generator

**Canonical mark image:** the rendered still, `brand/mark_still.png`,
feathered, with the full lockup poster at `brand/mark_poster.png`. It is the
default mark layer in every mark style render.

The p5 system (`TheShadowWeShare_logo_3D.html` plus the rebuilt
`mark_capture.html`) remains the generator of record: deterministic replay,
theta 4.051 within [3.85, 4.25], seed 72126, trail build 4.5 s, `?ambient=0`
for compositing. Passing `mark_html` explicitly forces a live capture.

It is p5, not Three.js. A session that assumed WebGL and recommended a
react-three-fiber path on 2026-09-10 was working from this skill before the
delta was applied.

## Season architecture (one scheme, trailers are seasons)

Nine themes, theme based and collision free against all 108 episode realms:

1 Recognition · 2 Healing · 3 Commitment · 4 Conflict · 5 Meaning ·
6 Responsibility · 7 Honesty · 8 Contribution · 9 Renewal

Loglines per season are unchanged (S2 is "we stop running. the echoes
answer."). Season 1 E12 is **The Thread**; The Choice moved to S2 and S6.

Retired as season names: the phrase titles (The Echo Within and siblings) and
the realm titles (The Mask and siblings). The realm titles collided with
Season 1's own episodes.

## Thumbnail tier system (all tiers live in the render job)

- **Episode, flagship style** (ruled): realm plate full bleed, or the engine
  paints the realm; the two souls facing inward from fixed plates; episode
  block top left carrying SEASON N and THEME; real runtime chip top right,
  omitted when unknown and never faked; TSWS lockup; gold thread; grain.
- **Season**: cinematic plate plus a right stack (SEASON N kicker, THEME title
  in gold Cinzel, rule, couplet with the closing words gilded), plus a small
  mark lower right. The season's opening realm is the default face.
- **Series**: mark left, wordmark stack right, all defaults.
- **Caption cards**: transparent brand type overlays for trailer scenes.
  `brand/canon/trailers.json` holds all 9 trailers by 10 scenes at 2 s marks.

## Environment engine (The Shared Shadow, painted)

All 108 realms map to motif recipes, season keyed for recurring names. Unknown
names derive deterministically rather than fail.

Season palettes wear at whisper level **on the world only. The mark never
wears them.**

| Season | Palette |
|---|---|
| S2 | amethyst / indigo |
| S3 | gold / amber |
| S4 | steel / crimson |
| S5 | sapphire / gold |
| S6 | sky / gold |
| S7 | teal / silver |
| S8 | bronze / gold |
| S9 | cosmic purple / gold |

Gold thread is present in every episode frame (canon), fading before it
touches the mark. Season 1 loglines double as default soul lines and hooks.

## Working law, learned the hard way

- Volatile values (taglines changed three times in one day) live as DATA the
  consumers read, never inside prompts or templates.
- The duration badge corner, lower right, stays empty on every thumbnail.
- Character plates are fixed canonical images. The current ones are crops from
  Tee's reference sheet; replace with clean full res exports when supplied.

## Where the render job actually runs

Verified 2026-09-10 against the live n8n estate. The render job is **TSWS 00,
Render Job**, a sub workflow bridging n8n Cloud to the TSWS render worker: it
accepts `{type, params}`, submits the job, polls to completion, and returns
`{ok, result}` or `{ok:false, error}`. Around it sit TSWS 01 Post-Production
Master (drop folder watcher, runs an episode end to end, renders the mark and
composites), 02 Narration and Sound Bed, 03 Visual Assembly, 04 Detail
Recovery (EditForge), and 05 Conform and Grain. All six were last updated
2026-08-12.

No n8n workflow is named for the environment engine, so the realm painting
most likely lives inside the render worker rather than in n8n. UNVERIFIED as
of 2026-09-10: the worker itself was not read.

Do not go shopping for a renderer. The pipeline exists.
