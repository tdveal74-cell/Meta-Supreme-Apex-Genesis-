---
title: DEVON EditForge Live Provider Boundary
type: SYS_OPS
version: 1
date: 2026-08-27
area: Systems
status: implementation-verified
owner: DEVON
---

# DEVON EditForge Live Provider Boundary v1

DEVON remains the only executive control plane. EditForge remains the media
execution engine. This build adds a private provider service behind EditForge's
existing adapter boundary. It does not create a second planner or move network
effects into `services.devon`.

## Live provider mapping

| Edit operation | Provider execution |
|---|---|
| `synthesize-voice` | Canonical registry-locked ElevenLabs voice |
| `lip-sync` | Canonical registry-locked Runway custom avatar |
| `generate-full-motion` | Runway Act-Two with canonical character reference and approved performance video |
| Local picture and finishing edits | Existing EditForge FFmpeg worker |

The external identity registry binds identity version, clone ID, voice ID,
permitted properties, consent state, and provider identifiers. Tee's identity is
permitted for TQO and NCO Forge only. TSWS and Ascension Caudex require separate
registry records and cannot inherit Tee's provider IDs silently.

## Approval and spend

DEVON refuses voice work without `params.maxCharacters` and refuses Runway
motion or lip-sync work without `params.maxCredits`. These ceilings are visible
in the approval consequence and are part of the exact intent hash. The provider
adapter applies the lower of the command ceiling and host ceiling, then cancels
a Runway task if the provider reports an estimate above that bound.

Provider keys, voice IDs, avatar IDs, and reference assets are not returned in
public execution state or receipts. Only hashed artifacts return to DEVON.

## Verified evidence

- EditForge: 254 application tests passed.
- EditForge worker/provider: 14 tests passed.
- EditForge lint, type checks, and production Next.js build passed.
- DEVON targeted integrity and execution slice: 158 tests passed.
- DEVON Ruff checks passed.
- Full DEVON suite additionally recorded 875 passes; database-backed tests could
  not run in the verification workspace because PostgreSQL was not available.

## Remaining deployment inputs

1. Authenticate the target Docker host.
2. Enter Runway and ElevenLabs keys in the host secret manager.
3. Install the consented Tee identity registry outside Git.
4. Provide the canonical voice ID, avatar ID, character reference, performance
   source, and an explicit per-job ceiling.
5. Boot the Compose stack and run one paid preview only after Tee approves the
   exact assets and ceiling.

No live provider generation was claimed in this record.
