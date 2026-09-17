# The block swallowed two production strands

Dated 2026-09-17. A deployment read-back taken at 22:35Z, after Tee reported
clearing the Vercel block. It supersedes what
`SYS_OPS_devon-read-the-frame-and-misread-one-word_v1_2026-09-17-1422.md` and
PR #266's merge commit say about Vercel, which is that the block was still in
effect and nothing had shipped.

The block is cleared, proven the way the `deploy-readback` skill prescribes,
by a deployment record existing rather than by a status turning green. Both
Vercel production surfaces are still stale, and that is now a separate fact
with a separate cause: the block ran from 2026-09-16T22:58:52Z to
2026-09-17T19:07:13Z, and everything either project owed production landed on
main inside that window.

## What production serves, read at 22:35Z

Railway, project `devon-api`, environment `production`. Three services, counted
from `list-services` rather than from a table.

| service | deployment | status | commit | since |
|---|---|---|---|---|
| `api` | `93102939` | SUCCESS | `240a8f2` | 2026-09-17T15:57:59Z |
| `presence` | `d34c2e1e` | SUCCESS | `795b1d8` | 2026-09-17T15:41:31Z |
| `scheduler-cron` | `9bf6c0d8` | SUCCESS | `240a8f2` | created 2026-09-17T15:49:18Z |

`api` and `scheduler-cron` are on current main. `presence` sits one commit
behind and that is its watch patterns working rather than drift:
`git diff 795b1d8..240a8f2` over `apps/presence`, `services` and
`requirements.txt` is empty, so deployment `54588e90`, which Railway marked
SKIPPED on `240a8f2`, was correct.

Both public hosts answer. `GET /api/v1/health` on the api host returns 200 and
`healthy`. `GET /health` on the presence host returns 200 and the eleven keys
`test_presence_service.py::test_health_says_only_these_things_and_no_more`
pins: inference `cerebras`, fallback `mock`, speech `cartesia`, ears `mock`,
protocols `[1, 2]`, five CORS origins, `livekit_configured` true,
`audio_over_websocket` false, and the breaker closed with zero breaches and
zero opens. The serving commit carries `apps/presence/livekit_publisher.py`,
which is the fact that makes `true, false` the working pair rather than the
silent one.

Vercel, team `tdveal74-5020s-projects`.

| project | production deployment | state | commit | since |
|---|---|---|---|---|
| `meta-supreme-apex-genesis-web` | `dpl_FMkk6p9nL1ztnBPG3fhHrvhxztB2` | READY | `f0f1e7e` | 2026-09-16T14:28:12Z |
| `devon-soul` | `dpl_AATtAoyp63si8K797vLXjtY5xjq3` | READY | `94de84b` | 2026-09-16T12:25:30Z |

Every later production record on either project is CANCELED. `target` was
checked on each one, because a READY preview and a READY production build read
identically in `state` alone.

The two `*.vercel.app` hosts could not be fetched from this container. `curl`
got `CONNECT tunnel failed, response 403` from the agent proxy on both, so the
Vercel half of this read-back comes from deployment records and the Railway
half comes from records plus a live read. The network policy opened
`*.up.railway.app` on 2026-09-16 and has not opened `*.vercel.app`. That is
Tee's to change if a session should be able to read those two surfaces
directly.

## The block, measured

Both projects created their last record before the gap at 2026-09-16T22:58:52Z,
on `ce70236`. Neither created another until 2026-09-17T19:07:13Z. That is 20
hours and 8 minutes with no deployment record of any kind on either project,
which is the signature the `deploy-readback` skill names: while an account is
blocked, a blocked account and a quiet account look identical in every status
field, and only the absence of records tells them apart.

The account was not quiet. Nine commits landed on main inside that window and
not one produced a record on either project.

| commit | landed | subject |
|---|---|---|
| `3112aea` | 2026-09-17T01:36:26Z | PR #259, the ElevenLabs contract and the coverage guard |
| `82f6810` | 2026-09-17T03:30:28Z | PR #260, close the ears arc, correct a vault entry |
| `164fd7f` | 2026-09-17T04:23:04Z | PR #262, push to talk |
| `e647762` | 2026-09-17T11:14:47Z | PR #261, the Pulse watchdog |
| `cfe29b0` | 2026-09-17T12:52:07Z | PR #264, the feeder ran |
| `3b30e10` | 2026-09-17T13:09:23Z | PR #265, the spent output budget |
| `926098d` | 2026-09-17T14:24:54Z | PR #263, three live defects |
| `795b1d8` | 2026-09-17T15:39:52Z | PR #267, the title was never indexed |
| `240a8f2` | 2026-09-17T15:49:14Z | PR #266, DEVON read the frame |

It cleared at 19:07:13Z. Four records now exist on each project, at 19:07:13Z,
19:07:15Z, 19:10:34Z and 21:33:13Z, and two of them are READY previews. A
fifth arrived at 22:41:44Z on each while this doc was being written. None of
them is on main, because main has not moved since 15:49:14Z, three hours before
the block lifted.

What cannot be established from here is the reason. The GitHub commit statuses
that would say "Account is blocked" rather than name the daily cap are not
readable through this session's tooling, so the cause rests on the record gap
and on Tee's own report that he cleared it on the Vercel side. The skill's
fourth recorded block was also never given a reason by any tool.

This one is the fifth, and two things about it are new. It is by a wide margin
the longest measured: the 2026-09-15 block ran about 97 minutes, and this ran
about 12 times that. And it is the first that held real production payload.

## What it stranded

Computed by hand from each project's own `vercel.json`, from the commit of the
last deployment that actually built to current main, which is the comparison
the `ignoreCommand` itself makes.

`meta-supreme-apex-genesis-web`, over `apps/web`, `packages/ui`,
`pnpm-lock.yaml` and `pnpm-workspace.yaml`, `f0f1e7e..240a8f2`: ten files, 1312
insertions, 11 deletions. All ten came in one commit, `164fd7f`, PR #262, the
push to talk build. `PresenceStage.tsx`, `useBargeIn.ts`, `usePresenceSocket.ts`,
`usePushToTalk.ts`, `lib/presence/capture.ts`, `lib/presence/protocol.ts`,
`package.json`, `public/presence/capture-worklet.js`, `scripts/capture-check.mjs`
and `scripts/presence-check.ts`.

`devon-soul`, over `deploy/soul`, `94de84b..240a8f2`:
`deploy/soul/services/devon/vault.py`, 57 insertions, 13 deletions, from
`82f6810` and `926098d`.

Both landed inside the window. That is the shape the skill wrote up on
2026-09-15 as the thing to watch for and could not yet show, that a block
lasting into a real change would hold a production update silently with only
an absence to show for it. It has now happened on both projects at once, and
the web surface is the expensive half: the presence page in production cannot
send a clip, because the client half of protocol v2 is sitting in main
undeployed while the presence service has been serving `protocols: [1, 2]`
since 15:41:31Z.

## What ships it

The next push to main, and nothing else. There is no owed work here and no
setting to change; the `ignoreCommand` on each project will compare its last
successful deployment against the new head, find the files above, and build.

A Redeploy from the Vercel dashboard cannot do this job. Redeploy rebuilds the
commit of the record it is launched from, and no record exists for `240a8f2`
on either project, so the newest thing either one could rebuild is a commit
from 2026-09-16. This was recommended earlier in the session and was wrong;
it is corrected here rather than quietly dropped.

## Two things in the skill that no longer match the estate

Recorded rather than acted on, because both are Tee's call.

`list_teams` now reports `"plan": "hobby"` for `tdveal74-5020s-projects`. The
`deploy-readback` skill records `"pro"`, read from the same field on
2026-09-04, and the whole free plan section is kept there as history on the
strength of that. If the account is back on Hobby then the 100 deployments per
day cap applies again and that history is live guidance rather than history.
Whether the plan actually changed, or the field means something else now, is
not established here. Worth Tee reading the Vercel billing page.

`get_project` returns `"live": false` for both projects. It was false for both
earlier in this session as well. No interpretation is offered: it is recorded
so the next reader does not treat it as new.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-block-swallowed-two-production-strands_v1_2026-09-17-2246.md
DATE: 2026-09-17
DECISIONS: Tee ruled on an inline card on 2026-09-17 to redeploy both Vercel projects from the dashboard once he had unblocked the account; that recommendation was withdrawn and corrected before he acted, because Redeploy rebuilds the commit of the record it starts from and no record exists for current main on either project. The standing decision that replaces it is that the next push to main is what ships both strands, which needs no approval and no setting.
FINDINGS: The Vercel block is cleared and both production surfaces are still stale, and those are now two separate facts. The block ran from 2026-09-16T22:58:52Z to 2026-09-17T19:07:13Z, 20 hours and 8 minutes with no deployment record of any kind on either project while nine commits landed on main. It is the fifth block recorded in this estate, about 12 times longer than the only other one whose duration is known, and the first to hold real production payload: ten files and 1312 insertions owed to meta-supreme-apex-genesis-web, all from PR #262's push to talk build, and 57 insertions of deploy/soul/services/devon/vault.py owed to devon-soul, every one of them landing inside the window. Production web therefore cannot send a clip while the presence service has served protocols [1, 2] since 15:41:31Z. Railway is current: api and scheduler-cron on 240a8f2, presence one commit behind on 795b1d8 because its watch patterns correctly found nothing to rebuild.
OPEN: list_teams now reports plan hobby for this team where the deploy-readback skill records pro as of 2026-09-04, which if real puts the 100 deployments per day cap back in force; unresolved and worth Tee reading the billing page. Both projects report live false, observed twice and unexplained. The reason for the block itself is unestablished from here, because the Vercel commit statuses are not readable through this session's tooling. The two vercel.app hosts cannot be fetched from a container, so no Vercel surface can be read back directly the way presence can. Tee's password remains disclosed and unrotated from a 2026-09-17 screenshot. The ten year access token issued to this session is revoked only by rotating SECRET_KEY on the api and presence services together with RECEIPT_SIGNING_KEYS_PREVIOUS carrying the old value, unstarted. Approval card REQ-F3F9F01CB06F expires unruled on 2026-09-20.
STATUS: Read back at 22:35Z. Railway api 93102939 SUCCESS on 240a8f2 since 15:57:59Z, presence d34c2e1e SUCCESS on 795b1d8 since 15:41:31Z, scheduler-cron 9bf6c0d8 SUCCESS on 240a8f2. Vercel meta-supreme-apex-genesis-web production READY on f0f1e7e since 2026-09-16T14:28:12Z, devon-soul production READY on 94de84b since 2026-09-16T12:25:30Z. Both api and presence answered a live health read; neither Vercel host could be fetched from this container.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
