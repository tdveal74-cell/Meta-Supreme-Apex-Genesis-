# Railway builds from the Dockerfiles: the switch, the stalled deploys, and the pyasn1 decode test

Status doc for Tee's ruling to point Railway at the repository's Dockerfiles, carried out on 2026-10-31. It covers three things: the pull request that made the images ready, the switch of all three services read back from production, and a day in which Railway stopped creating deployments for two of them. It also carries the android-key attestation test he ruled at 08:36:39Z, which ships in the same pull request as this doc. Written 2026-10-31. It closes the Railway and pyasn1 items that `SYS_OPS_openmontage-finding-verification_v1_2026-10-31-0642.md` left open.

## The ruling

Read on 2026-10-31, every live Railway deployment of `api`, `presence` and `scheduler-cron` had been built with Railpack, on Python 3.13.16, while CI built `infrastructure/docker/Dockerfile.api` on 3.12. The CI job named "Railway container contract" was testing an image Railway never built, which two independent verifiers confirmed. Tee ruled at 09:12:25Z to point Railway at the Dockerfiles, kept it at 16:34:36Z and again at about 18:27Z, and at 21:18Z chose "Switch both now" on a card for `api` and `presence`.

## PR #456, merged as `2b4846a`

It copies `policies/` in `Dockerfile.api`, because `app/api/v1/arf_shadow.py:30` reads `policies/reliability/profiles.v1.json` on every request and Railpack had been hiding the gap by copying the whole repository. The container job now checks the file is in the image and that `dispatch.py` imports there. A new workflow, `presence-image-ci.yml`, builds `Dockerfile.presence` path filtered, imports the app, proves the image refuses to start deployed without a `SECRET_KEY`, and reads `GET /health` started deployed with a generated one. `CLAUDE.md` counts seventeen CI jobs.

A fresh critic of `c7f13e3` raised 2 MED, 3 LOW and 1 NIT. The records stated the switch as already done, while `get-service-config` read RAILPACK for `api` and `presence`; that was fixed over two commits, and a verifier found one sentence left after the first, which the second rewrote. Another fresh verifier then found no present-tense claim of the switch at `c8b2ff1`. The presence job had run with `ENVIRONMENT=test`, a local environment that skips the `SECRET_KEY` refusal; it now runs deployed, and on `c8b2ff1` real Docker printed "Refusing to start" without a secret and served `/health` 200 with one. The step name that claimed more than its check is renamed. The other three, the start command's exec form, presence's watch patterns and the `checkSuites` wait, were Railway settings and are dealt with below. Every check passed on `c8b2ff1` and it merged under the standing approval at 19:13Z.

## The switch, read back

| service | deployment | built from | started | read back |
|---|---|---|---|---|
| `scheduler-cron` | `85c548c6`, 20:56Z | `Dockerfile.api`, `FROM python:3.12-slim`, `COPY policies/` | cron run at 21:15:09Z | "dispatch: 0 started, 0 skipped, 0 failed" |
| `api` | `22a45f34`, 21:23Z | `Dockerfile.api`, `FROM python:3.12-slim` | alembic preDeploy, then `Uvicorn running on http://0.0.0.0:8080` | `/api/v1/health` 200, healthy, 21:24:52Z |
| `presence` | `2edce5d4`, 21:24Z | `Dockerfile.presence`, `FROM python:3.12-slim` | `Uvicorn running on http://0.0.0.0:8080` | `/health` 200 at 21:25:04Z, after the old container was removed at 21:24:48Z |

All three are at commit `f2f3ccc`, which is main with nothing in a runtime path after `2b4846a`. `scheduler-cron` had been set at 18:28:29Z, and its Dockerfile builds began when deployments resumed. `api` and `presence` were already building from their Dockerfiles before this session touched them: `api` deployment `296d6a16` at 21:01Z logged the twelve steps of `Dockerfile.api` and `presence` deployment `d8287818` at 21:03Z the seven of `Dockerfile.presence`, both on `python:3.12-slim`, both listening on 8080. Both had read RAILPACK at about 18:50Z; who changed them before 21:01Z, and to what start command, was not read. This session's calls at 21:22Z set the Dockerfile paths, already in force, and `/bin/sh -c "exec uvicorn ... --port $PORT"` as the start command, because Railway's "Set a Start Command" page says a Dockerfile service runs its start command in exec form without variable expansion. Both deploy logs then show port 8080, so the variable expanded. `presence`'s watch patterns now also name its Dockerfile. Each fresh build was started through Railway's agent, which reported the `presence` build as Railpack; its build log shows `load build definition from infrastructure/docker/Dockerfile.presence`, so that report was wrong.

Presence's `/health` reads `inference: cerebras`, `fallback: mock`, `speech: cartesia`, `ears: elevenlabs`, `livekit_configured: true` and `audio_over_websocket: false`, the working pair on a build that carries `apps/presence/livekit_publisher.py`, which the Dockerfile copies with the rest of `apps/presence/`. A healthy `/health` is not proof of audio.

## The deploys that stopped

Railway created no `api` or `scheduler-cron` deployment, in any status, from 06:08:42Z until 20:54:35Z, across nine merges to main: `ef908cf`, `bfb6417`, `c32faba`, `ac691aa`, `ceb4619`, `715088e`, `1496501`, `2b4846a` and `f2f3ccc`. `presence` logged a SKIPPED row for each at push time, the last at 19:27:00Z, so the pushes reached Railway. Workflow `wf_d92bd150-978` sent one verifier to refute the first five with reads only; it confirmed every part and found no staged change, watch pattern, config file or skip marker to explain it. Production kept serving the code it had: eight of the nine touched no runtime path, and the ninth, `2b4846a`, changed only `Dockerfile.api`, which no running service was built from. Deployments resumed at 20:54:35Z, when `scheduler-cron` got `da61e2dd` for `2b4846a`, followed at 20:56:59Z by `85c548c6` for `f2f3ccc`; `api` and `presence` each got a Dockerfile deployment of `f2f3ccc` at 21:01Z and 21:03Z, already building from their Dockerfiles. Tee reported on a card that Railway fixed it. The cause was never established here.

`api`'s `source.checkSuites` read true at about 18:50Z and false at 21:23Z. What changed it is unverified: Railway's repair, the unread change that put `api` on its Dockerfile before 21:01Z, and this session's own `update-service` call at 21:22Z, which set only the start command and Dockerfile path, are all candidates. While it read false, the merge of PR #461 deployed to `api` while that commit's CI was still running. Tee ruled on a card to turn it back on. A change staged through Railway's agent showed only as `Source: "" to "{}"`; once committed it left the gate off, with the source intact. Tee then turned on the "Wait for CI" toggle in the service's Source settings, and `get-service-config` read `checkSuites: true` at 22:12Z with the source unchanged. The deploy-readback skill says both, and that the toggle, not the agent, is the way to set it.

## The pyasn1 decode test

pyasn1 is in the closure only through webauthn, and webauthn hands it device bytes in one place: `verify_android_key` BER-decodes the attestation certificate and its key description extension. No test sent an attestation, so the pyasn1 bump of PR #442 passed with nothing running that decoder. Two tests in `test_passkeys_api.py` now send py_webauthn's own Pixel 8a android-key attestation, from v3.0.0 (BSD-3-Clause, Duo Security), through the real options and complete routes. Each test points the settings at the vector's rp and origin, gives the options route the vector's challenge through webauthn's own argument, and gives the X.509 store a time inside the chain's validity. One test registers the credential and pins that both decodes ran, Certificate then KeyDescription. The other swaps the decoded attestation challenge for zeros and gets a 400, so the route acts on what pyasn1 returned. Three mutations were each caught: no store time (the chain is refused), an empty KeyDescription, and the production origin (the client data is refused). The decodes sit after certificate chain validation, so a malformed extension would have to be inside a certificate that chains to a Google root.

## Measured

| check | result |
|---|---|
| CI on `c8b2ff1` | every job green, the presence job in real Docker |
| `test_passkeys_api.py` on this branch | 7 passed |
| `get-service-config`, 21:23Z to 21:26Z | all three DOCKERFILE, start commands and presence watch patterns as above, and `checkSuites` false on all three |
| build and deploy logs | as in the switch table |
| `/api/v1/health` and `/health` | both 200 |

## Not verified

- **DEVON speaking through the presence stage on the new image.** Only a human listening proves the voice path, and nobody has listened since 21:24Z.
- **The reliability shadow route in production.** It needs an authenticated account and a task id. The image carries the file: the build logged `COPY policies/`, and CI asserts the path.
- **Behaviour on Python 3.12 beyond what is listed here.** No test suite for the API or presence runs on 3.12, the browser worker's being the only one that does: CI runs the standalone, engine and api jobs on 3.11 (`ci.yml` lines 24, 322 and 360), and the container and presence jobs only import and start the apps inside the 3.12 images. Production had run 3.13 until tonight.
- **The cause of the stalled deploys, and whether the `checkSuites` change belongs to Railway's fix.**

## Gauntlet verdict

VERDICT: PASS-WITH-CONDITIONS
Deliverable: PR #456 and the switch of three Railway services; the pyasn1 test and these records in the pull request carrying this doc.
Scores: correctness 5, scope 5, verification 4, security 5, reversibility 5, failure handling 4, idempotency 5, traceability 5, observability 4, completeness 4, maintainability 4 | mean 4.5 | flagship floor: met for the build switch
Conditions: Tee's ears on DEVON's voice through the new presence image. The CI gate on `api` is back on, read at 22:12Z.
Receipts: the deployment ids, log lines and HTTP bodies above; a fresh critic and two verifiers on PR #456; one verifier on the stalled deploys; one on this read back, which confirmed all seven of its claims from the live project.
Recommendation: listen to DEVON once. The human owns SHIP.

## Open

- Tee to talk to DEVON once through the presence stage, so the new image is heard end to end.
- The first merge with the gate back on should show `api` WAITING until CI finishes; read it then.
- Carried: the five installer NITs recorded in the 0642 doc, the first scheduled daily audit run, and the probe branch `claude/audit-red-path-probe`.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_railway-dockerfile-switch_v1_2026-10-31-2126.md
DATE: 2026-10-31
DECISIONS: Tee ruled to point Railway at the Dockerfiles at 09:12:25Z, kept it twice, and chose "Switch both now" for api and presence on a card at 21:18Z. On the stalled deploys he answered that Railway fixed it. The pyasn1 android-key test was ruled at 08:36:39Z.
FINDINGS: Railway built all three services with Railpack on Python 3.13 while CI built the Dockerfiles on 3.12. Dockerfile.api lacked policies/, which a reliability route reads per request. Railway created no api or scheduler-cron deployment from 06:08Z to 20:54Z across nine merges, cause unknown. api's checkSuites read false from 21:23Z until Tee turned it back on, read true at 22:12Z. Railway's agent misreported the presence builder. No test had reached pyasn1's android-key decode.
OPEN: DEVON's voice heard through the new presence image; the first WAITING api deploy under the restored gate; five installer NITs; the first scheduled daily audit run; the probe branch.
STATUS: PR #456 merged as 2b4846a. scheduler-cron, api and presence run from their Dockerfiles on python:3.12-slim at f2f3ccc, read back. The pyasn1 test and these records are in the pull request carrying this doc. Verdict PASS-WITH-CONDITIONS.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
