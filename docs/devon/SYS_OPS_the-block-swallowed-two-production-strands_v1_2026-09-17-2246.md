# The block swallowed two production strands, and then main moved twice

Dated 2026-09-17. A deployment read-back taken at 22:35Z, after Tee reported
clearing the Vercel block. It supersedes what
`SYS_OPS_devon-read-the-frame-and-misread-one-word_v1_2026-09-17-1422.md` and
PR #266's merge commit say about Vercel, which is that the block was still in
effect and nothing had shipped.

Both are answered. The block is cleared, proven the way the `deploy-readback`
skill prescribes, by a deployment record existing rather than by a status
turning green. It ran 20 hours and 8 minutes and it held real production
payload on both Vercel projects. Both strands are now live, shipped by the two
merges that landed on main at 22:47:31Z and 22:56:29Z, nine and eighteen
minutes after the first draft of this doc said they were stranded.

That last part is the second time today a sentence of mine went stale between
being written and being merged, and it is recorded rather than quietly fixed.
The first draft, timestamped 22:46Z, reported both surfaces stale with a
measured payload owed to each and said the next push to main would ship them.
Every number in it was right at 22:46Z. Sixty one seconds later PR #270 merged
and the web half shipped. The rule that catches this is not a better draft, it
is re-reading the live state immediately before merging a claim about it.

## What production serves, read at 23:05Z

Railway, project `devon-api`, environment `production`. Three services, counted
from `list-services` rather than from a table.

| service | deployment | status | commit | since |
|---|---|---|---|---|
| `api` | `93102939` | SUCCESS | `240a8f2` | 2026-09-17T15:57:59Z |
| `presence` | `d34c2e1e` | SUCCESS | `795b1d8` | 2026-09-17T15:41:31Z |
| `scheduler-cron` | `9bf6c0d8` | SUCCESS | `240a8f2` | created 2026-09-17T15:49:18Z |

Read at 22:35Z, before main moved. `presence` sits behind `api` and that is its
watch patterns working rather than drift: `git diff 795b1d8..240a8f2` over
`apps/presence`, `services` and `requirements.txt` is empty, so deployment
`54588e90`, which Railway marked SKIPPED on `240a8f2`, was correct. Both later
merges carry `services/` changes, so `presence` will rebuild on them and `api`
will wait for their check suites, which is `checkSuites: true` working.

Both public hosts answer. `GET /api/v1/health` on the api host returns 200 and
`healthy`. `GET /health` on the presence host returns 200 and the eleven keys
`test_presence_service.py::test_health_says_only_these_things_and_no_more`
pins: inference `cerebras`, fallback `mock`, speech `cartesia`, ears `mock`,
protocols `[1, 2]`, five CORS origins, `livekit_configured` true,
`audio_over_websocket` false, and the breaker closed with zero breaches and
zero opens. The serving commit carries `apps/presence/livekit_publisher.py`,
which is the fact that makes `true, false` the working pair rather than the
silent one.

Vercel, team `tdveal74-5020s-projects`, after the two merges.

| project | production deployment | state | commit | ready |
|---|---|---|---|---|
| `meta-supreme-apex-genesis-web` | `dpl_F89tEYKtgLgFSMkG7j8BV8CssYua` | READY | `53b3f48` | 2026-09-17T22:48:27Z |
| `devon-soul` | `dpl_EqbcffbHERX1URRkjY4o4suApUrZ` | READY | `d8d7144` | 2026-09-17T22:56Z |

`target` was checked on each, because a READY preview and a READY production
build read identically in `state` alone. The web project's production build on
`d8d7144` was skipped, and that skip is correct:
`git diff 53b3f48..d8d7144` over its four watched paths is empty, and the build
log shows the ignore step running and exiting 0 rather than a build failing.

The two `*.vercel.app` hosts cannot be fetched from this container. `curl` got
`CONNECT tunnel failed, response 403` from the agent proxy on both, so the
Vercel half of this read-back comes from deployment records and build logs and
the Railway half comes from records plus a live read. The network policy opened
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

It cleared at 19:07:13Z, and records have been created steadily since.

What cannot be established from here is the reason. The GitHub commit statuses
that would say "Account is blocked" rather than name the daily cap are not
readable through this session's tooling, so the cause rests on the record gap
and on Tee's own report that he cleared it on the Vercel side. The skill's
fourth recorded block was also never given a reason by any tool.

This one is the fifth, and two things about it are new. It is by a wide margin
the longest measured: the 2026-09-15 block ran about 97 minutes, and this ran
about 12 times that. And it is the first that held real production payload.

## What it held, and what shipped it

Computed by hand from each project's own `vercel.json`, from the commit of the
last deployment that actually built to main, which is the comparison the
`ignoreCommand` itself makes.

`meta-supreme-apex-genesis-web` served `f0f1e7e` from 2026-09-16T14:28:12Z
until 22:48:27Z today, owing ten files and 1312 insertions over `apps/web`,
`packages/ui`, `pnpm-lock.yaml` and `pnpm-workspace.yaml`. All ten came in one
commit, `164fd7f`, PR #262's push to talk build: `PresenceStage.tsx`,
`useBargeIn.ts`, `usePresenceSocket.ts`, `usePushToTalk.ts`,
`lib/presence/capture.ts`, `lib/presence/protocol.ts`, `package.json`,
`public/presence/capture-worklet.js`, `scripts/capture-check.mjs` and
`scripts/presence-check.ts`. PR #270 merged as `53b3f48` at 22:47:31Z, the
ignore step compared against `f0f1e7e` and found all ten, and the build went
READY at 22:48:27Z carrying the lot.

`devon-soul` served `94de84b` from 2026-09-16T12:25:30Z until 22:56Z today,
owing 57 insertions of `deploy/soul/services/devon/vault.py` from `82f6810` and
`926098d`. PR #268 merged as `d8d7144` at 22:56:29Z, adding four more files
under `deploy/soul`, and its production build went READY carrying both the new
work and the owed vault change.

For about 42 hours the presence service served `protocols: [1, 2]` while the
page that speaks v2 sat in main undeployed, and no status anywhere said so.
That is the shape the skill wrote up on 2026-09-15 as the thing to watch for
and could not yet show: a block lasting into a real change holds a production
update silently, with only an absence to show for it. It has now happened on
both projects at once.

**A cleared block does not ship what it held, and the next push does.** The
comparison base is the last successful deployment, so the owed diff survives
intact and the first build after the block carries it. That is what both
projects just did. The operational rule is to check what is owed the moment a
block lifts, name the commit that will ship it, and then check again rather
than assuming the naming was the shipping.

Two things that do not work, recorded because both were considered here. A
Redeploy from the Vercel dashboard rebuilds the commit of the record it is
launched from, and during a block no record was created for the commits that
matter, so the newest thing it can rebuild is the stale one already live. It
was recommended earlier in this session and withdrawn before Tee acted. And a
push to a branch cannot do it either: a branch push makes a preview, and its
comparison base is that branch's own last deployment rather than production.

## Two things in the skill that no longer match the estate

Recorded rather than acted on, because both are Tee's call.

`list_teams` now reports `"plan": "hobby"` for `tdveal74-5020s-projects`. The
`deploy-readback` skill recorded `"pro"`, read from the same field on
2026-09-04, and the whole free plan section is kept there as history on the
strength of that. If the account is back on Hobby then the 100 deployments per
day cap applies again and that history is live guidance rather than history.
Whether the plan actually changed, or the field means something else now, is
not established here. Worth Tee reading the Vercel billing page.

`get_project` returns `"live": false` for both projects. It was false for both
earlier in this session as well, including while production was building. No
interpretation is offered: it is recorded so the next reader does not treat it
as new.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-block-swallowed-two-production-strands_v1_2026-09-17-2246.md
DATE: 2026-09-17
DECISIONS: Tee ruled on an inline card on 2026-09-17 to redeploy both Vercel projects from the dashboard once he had unblocked the account; that recommendation was withdrawn and corrected before he acted, because Redeploy rebuilds the commit of the record it starts from and no record exists for the commits a block swallowed. What replaced it needed no decision: the first push to main after a block carries the whole owed diff, which is what the 22:47:31Z and 22:56:29Z merges did.
FINDINGS: The Vercel block ran from 2026-09-16T22:58:52Z to 2026-09-17T19:07:13Z, 20 hours and 8 minutes with no deployment record of any kind on either project while nine commits landed on main. It is the fifth block recorded here, about 12 times longer than the only other one whose duration is known, and the first to hold real production payload: ten files and 1312 insertions owed to meta-supreme-apex-genesis-web, all from PR #262's push to talk build, and 57 insertions of deploy/soul/services/devon/vault.py owed to devon-soul, every one of them landing inside the window. Production web therefore could not send a clip for about 42 hours while the presence service served protocols [1, 2]. Both strands are now live: 53b3f48 built the web surface to READY at 22:48:27Z and d8d7144 built devon-soul, and the web project's skip on d8d7144 is correct because 53b3f48..d8d7144 is empty over its watched paths. Railway was current at 22:35Z with api and scheduler-cron on 240a8f2 and presence one commit behind on 795b1d8, correctly, because its watch patterns found nothing to rebuild.
OPEN: This doc's first draft was stale 61 seconds after it was written, because main moved twice while it was being committed; that is the second stale sentence of the day and the remedy is re-reading live state immediately before merging a claim about it, not a better draft. list_teams now reports plan hobby for this team where the deploy-readback skill records pro as of 2026-09-04, which if real puts the 100 deployments per day cap back in force; unresolved and worth Tee reading the billing page. Both projects report live false, observed three times including while production was building, and unexplained. The reason for the block itself is unestablished from here, because the Vercel commit statuses are not readable through this session's tooling. The two vercel.app hosts cannot be fetched from a container, so no Vercel surface can be read back directly the way presence can. Tee's password remains disclosed and unrotated from a 2026-09-17 screenshot. The ten year access token issued to this session is revoked only by rotating SECRET_KEY on the api and presence services together with RECEIPT_SIGNING_KEYS_PREVIOUS carrying the old value, unstarted. Approval card REQ-F3F9F01CB06F expires unruled on 2026-09-20.
STATUS: Railway read at 22:35Z: api 93102939 SUCCESS on 240a8f2 since 15:57:59Z, presence d34c2e1e SUCCESS on 795b1d8 since 15:41:31Z, scheduler-cron 9bf6c0d8 SUCCESS on 240a8f2. Vercel read at 23:05Z: meta-supreme-apex-genesis-web production dpl_F89tEYKtgLgFSMkG7j8BV8CssYua READY on 53b3f48 at 22:48:27Z, devon-soul production dpl_EqbcffbHERX1URRkjY4o4suApUrZ READY on d8d7144. Both api and presence answered a live health read; neither Vercel host could be fetched from this container, so that half rests on deployment records and build logs.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
