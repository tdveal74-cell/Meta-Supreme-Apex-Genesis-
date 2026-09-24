# TSWS goes full motion: Act-Two now, open source on trial

Filed 2026-09-24 at 08:08Z. A research answer that turned into a ruling. Tee
asked for free open source alternatives to Runway and HeyGen, then how much GPU
they need, then for the same answer covering TSWS and ACX, then ruled that TSWS
goes full motion.

## Rulings

All from Tee, 2026-09-24.

- TSWS goes full motion. In chat, in his words: "TSWS is going full motion".
- Runway Act-Two carries TSWS full motion first, and one TSWS scene is trialled
  through Wan 2.2 Animate on a rented GPU for a side by side. Chosen on a
  card, the recommended option. The stated cost was Runway credits per episode
  until the trial wins.
- Rent, never buy, and run at top quality. In chat, in his words: "I want to
  rent and I want top quality". This moves the trial off the 48GB tier onto
  80GB, where the 14B models run natively at 720p with no quantization and no
  offloading. It supersedes the 48GB trial card above; the ruling to trial
  stands.
- This doc. Chosen on a card, the recommended option.

## What full motion means here

TSWS moves onto the micro-drama path that
`SYS_OPS_devon-editforge-execution_v1_2026-08-26.md` defines: clone voice, full
motion, lip sync, episode assembly. In EditForge `generate-full-motion` is
mapped to Runway Act-Two with a canonical character reference and an approved
performance video, per `SYS_OPS_devon-editforge-live-provider_v1_2026-08-27.md`.
That record claims no live provider generation, and none has been recorded
since, so Act-Two is wired and has never rendered a frame here. The first
TSWS render is also the first live exercise of that path.

The VPS render worker the TSWS block uses, `deploy/render-worker/jobs.js`,
builds ffmpeg jobs and calls no generative model. Whether any TSWS n8n
workflow generates picture is UNVERIFIED: their bodies are not in this
repository, and `TSWS 04 Detail Recovery (EditForge)` calls into EditForge and
was not read. Full motion
is therefore a new lane in front of TSWS 03 Visual Assembly, not a setting on
it.

## Gates the ruling does not loosen

- Auren and Vespera need their own identity registry record. EditForge refuses
  identity work without a clone id, a voice id, an identity version and
  `consentRecorded: true`, and Tee's record is permitted for TQO and NCO Forge
  only. TSWS cannot inherit his provider ids silently.
- The recorded consent has to cover performance capture and character motion,
  not voice alone. Whether the existing recordings do is UNVERIFIED. If they
  cover voice only, they are re-recorded before any full motion render.
- The brand floor says every asset must "Move silkily when it moves", with
  slow precession, eased motion and nothing abrupt
  (`.claude/skills/shadow-we-share-brand/SKILL.md` line 25). Character
  performances fall under it, so they are directed restrained.
- EditForge refuses `generate-full-motion` without a positive
  `params.maxCredits`, and the ceiling is part of the approval. Every Act-Two
  render carries a stated credit cap.

## Open source options researched

Every licence and VRAM figure below is from training data with a June 2026
cutoff and was NOT re-checked on 2026-09-24. Licence is a compliance item: read
each repository's LICENSE and model card before anything earns money. Weights
often carry different terms from code.

| Tool | Job | Licence as last known | VRAM, approximate |
|---|---|---|---|
| Wan 2.2 Animate 14B | Performance video drives a character, full body; the Act-Two equivalent | Apache 2.0 | 24GB quantized and slow, 48GB comfortable, 80GB native |
| LivePortrait | Face and expression onto a portrait | MIT code, InsightFace models non-commercial | about 8GB |
| Wan character LoRA training | Keeps a character consistent across shots | Apache 2.0 base | 24GB minimum, 48GB comfortable |
| LatentSync 1.5 and 1.6 | Lip sync onto existing footage | Apache 2.0 | about 8GB, about 18GB |
| InfiniteTalk | Audio driven presenter | Apache 2.0 | 24GB with offload, 48 to 80GB comfortable |
| MuseTalk | Real time lip sync | MIT code, check bundled models | 6 to 8GB |
| Wan 2.2 5B | Text or image to video, B-roll | Apache 2.0 | 24GB |
| Wav2Lip | Lip sync | Pretrained model non-commercial, never for revenue content | small |

## GPU tiers

Rental prices are unverified and move; check before spending.

| Work | Tier | Rental card | Rough rate |
|---|---|---|---|
| TQO and NCO Forge lip sync, B-roll | 24GB | RTX 4090 | about $0.35 to $0.70 an hour |
| TSWS full motion, ACX micro-drama | 48GB | L40S or RTX A6000 | about $0.80 to $1.20 an hour |
| Heavy batch days | 80GB | A100 or H100 | about $1.50 to $3 an hour |

Under the top quality ruling every show runs on the 80GB row, H100 first. A
smaller card only saves money by quantizing or offloading, which is exactly
the quality Tee ruled out, and one tier means one endpoint for EditForge to
call. The trial rents an on demand H100 by the hour. If the trial wins, the
pipeline moves to a serverless GPU billed per second, so idle time between
episodes costs nothing; which vendor is UNVERIFIED and is a choice for the
adapter arc.

The VPS is taken to be CPU only; that is UNVERIFIED and was not read. Nobody has
measured render minutes per finished minute on any of these, so no monthly cost
or buy decision can be made yet. The trial produces that number.

## Findings

- ACX was read as Ascension Caudex. The canonical Area vocabulary names it
  so (`services/devon/areas.py`, ruled the ninth Area on 2026-08-20, from
  Drive `AREAS.md`), though
  `SYS_OPS_rakazo-lane-producers_v1_2026-09-23-1537.md` records Tee not saying
  so in chat. If he meant Audible's audiobook platform, the GPU answer does not
  apply to it.
- A self hosted engine is a build arc: a new EditForge provider adapter behind
  the same identity and spend gates, plus a rented GPU endpoint for it to call.

## DEVON RECEIPT

AREA: TSWS
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_tsws-full-motion_v1_2026-09-24-0808.md
DATE: 2026-09-24
DECISIONS: Tee ruled that TSWS goes full motion, that Runway Act-Two carries it first, that one TSWS scene is trialled through Wan 2.2 Animate for a side by side, and that GPU is rented, never bought, at top quality, which puts every show on the 80GB tier, H100 first.
FINDINGS: Full motion puts TSWS on the EditForge micro-drama path, which needs its own identity registry record for Auren and Vespera; the render worker calls no generative model, so full motion is a new lane in front of TSWS 03, and Act-Two is mapped in EditForge but has never rendered live. Open source alternatives to Runway and HeyGen exist; the 24GB tier covers lip sync and the 48GB tier covers full motion. Licences, VRAM and prices are from training data and unverified today. ACX was read as Ascension Caudex from the Area vocabulary.
OPEN: A TSWS identity registry record. Confirm the recorded consent covers motion, or re-record it. The Wan 2.2 Animate trial scene with Tee watching end to end. Read TSWS 04 to confirm no TSWS workflow already generates picture.
STATUS: Ruled; nothing built; trial not run.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
