# The EditForge artifact store, and what the Vercel surface is actually serving

Date: 2026-09-12. Supersedes nothing. This is the first status doc on the
EditForge artifact store, and it records a decision Tee has not yet made, so it
is filed open rather than closed.

Written because the question "why does the voice provider report
`readyToRun: false` when its key is set" has an answer that is an architecture
decision, not a settings page, and that answer was living in a chat thread.

## What was asked

Tee's Vercel agent was sent to check one thing: whether `ELEVENLABS_VOICE_ID`
was set on the EditForge project. It was not. The agent added it to Production
only, redeployed, and then refused to claim the provider had gone ready, because
it could not reach `/api/providers` to look. That refusal was correct and it is
the reason this document exists: the variable it set was not the one holding the
lane shut.

## The live read back, measured 2026-09-12

`GET https://editforge.vercel.app/api/health` is an open path
(`proxy.ts:22-33`), so this needs no credential. It answered HTTP 503 at
04:39:57Z:

```
status: degraded            store: kv                 storeReachable: true
storeEnv: KV_REST_API_URL, KV_REST_API_TOKEN, KV_URL
accessGate: false          sessionSecret: false      artifactStore: false
executionReady: false      workerConfigured: false   workerReachable: false
productionReady: false
```

`productionReady` is the conjunction of four flags
(`app/api/health/route.ts:17`), and all four are false. `healthy` is false
because `NODE_ENV` is production and `productionReady` is not true
(`route.ts:18`), which is why the endpoint answers 503 rather than 200. The
durable store is the one thing that is fine: Vercel KV, reachable, three
variables present.

Three more reads, all of them open paths, all at the same sitting:

| request | answer |
|---|---|
| `GET /api/providers` | 401 `{"error":"Authentication required"}` |
| `GET /api/passkeys/status` | 200 `{"available":false,"count":0}` |
| `GET /api/auth/google/status` | 200 `{"available":false}` |

Read those together and the surface is legible. The 401 comes from
`proxy.ts:71`, which is only reachable when `authenticationConfigured()` is
true; a false there returns 503 instead at `proxy.ts:41-45`. Since
`sessionSecret` is false, the only remaining disjunct in that function
(`lib/auth.ts:99-108`) is `EDITFORGE_MCP_TOKEN`, so production EditForge is
protected by that bearer token. That is an inference from two measured values,
labelled as one, and it is the benign reading: the gate fails closed, which is
exactly what `proxy.ts:11-18` says it is built to do.

The finding that is not benign is the pair of `available: false` answers. There
is no human sign-in path on that surface. A browser hitting any guarded route is
redirected to `/login` (`proxy.ts:75-77`), and at `/login` neither passkeys nor
Google is available, because `accessGateEnabled()` needs a session secret, a
Google client id, a client secret and an allowed email, and it reports false.
So editforge.vercel.app today is a token only API surface. Nobody can open the
studio in a browser and look at it. That is measured, not guessed, and it is an
item for Tee rather than a thing to fix unasked.

## Why the voice lane refuses, with receipts

The refusal is not a missing key and not a missing voice id. It is the artifact
store, and the chain is four links long across two files.

- `lib/artifacts.ts:109` reads the store directory from one place:
  `process.env.EDITFORGE_ARTIFACT_DIR?.trim()`, returning null when it is empty
  or absent.
- `lib/artifacts.ts:121`, `artifactStoreConfigured()`, is that function being
  null checked. Nothing else feeds it.
- `storeArtifact()` at `lib/artifacts.ts:177` writes with
  `fs.mkdir(dir, {recursive: true})` at :200 and `fs.writeFile` at :201, under a
  content addressed name.
- `app/api/artifacts/[name]/route.ts` serves the bytes back with `fs.stat` at
  :41 and `createReadStream` at :69, with byte range support at :50, :65, :82
  and :84.

So the store is the filesystem at both ends, write and read. Vercel's filesystem
is ephemeral, only `/tmp` is writable, and nothing written during one invocation
is visible to the next. There is no directory on that platform that satisfies
both halves of the chain.

The dependency is documented in the repository rather than folklore.
`.env.example:17-20` states it in the voice block: ElevenLabs answers with the
audio itself, so `EDITFORGE_ARTIFACT_DIR` must also be set or a voice run
refuses. And `lib/artifacts.ts:117-119` explains why the flag exists at all, in
its own words: so a voice submit that would refuse says so before anyone clicks
Run, rather than after a provider has already been paid for audio the studio
then throws away.

That last sentence is the whole point. `readyToRun: false` is the design
working. It is a guard that was built to spend nothing.

## Why not to set the variable on Vercel to clear the flag

Setting `EDITFORGE_ARTIFACT_DIR` on Vercel would flip
`artifactStoreConfigured()` to true, which would take `readyToRun` to true,
which would let a voice run start. ElevenLabs would then be called, real
characters would be spent, the bytes would be written into a lambda's
`/tmp`, and the artifact route would answer 404 from a different lambda that
never saw the file. The studio would have paid for audio and thrown it away,
which is the exact outcome the flag exists to prevent.

So that is strictly worse than the honest refusal, and it is a change nobody
should make from a settings page. Recorded here so a future session does not
read `artifactStore: false` as a gap to close.

There is also no object store wired up to fall back to. In the EditForge
checkout at `be3eb47`, `grep -ni "blob\|aws\|s3\|storage\|minio" package.json`
returns nothing and exits 1. No `@vercel/blob`, no AWS SDK, no S3 client. The
filesystem is not one implementation among several; it is the only one.

## Where the store does exist

`compose.hostinger.yaml` already solves this for the self hosted shape. It sets
`EDITFORGE_ARTIFACT_DIR: /artifacts` at lines 30 and 83, mounts the named volume
`editforge_artifacts:/artifacts` into both services at lines 48 and 89, declares
it at line 195, and points `EDITFORGE_ARTIFACT_BASE_URL` at the app's own
artifact route at line 85. A second volume, `editforge_provider_artifacts`,
does the same job for the provider side at lines 143, 144 and 151.

So the voice lane is not unbuilt. It is built for a host with a disk, and the
production surface is a host without one.

## The four options

1. **Run EditForge where the volume exists.** No code change at all. The compose
   file already declares the variable and mounts the volume at the lines above.
   Whether that stack has ever actually been stood up is not something this
   session checked, so treat it as configured rather than as proven. Cost: the
   studio stops being a Vercel deployment, which is a decision about where
   EditForge lives, not a config edit.
2. **Add a blob store behind the same interface.** One implementation to
   replace, four definitions wide: `storeArtifact`, `artifactDir` with
   `artifactStoreConfigured`, `artifactUrl` at `lib/artifacts.ts:144`, and the
   GET route. That much is a clean seam. Two things make it more than a swap.
   First, the GET route's byte range handling is hand rolled against `fs.stat`
   and `createReadStream`, so it has to be either reimplemented against the blob
   API or delegated to a store that serves ranges itself. Second, the
   abstraction is not sealed: `artifactDir()` is called directly from outside
   the module, at `modules/canvas/render.ts:112` and at
   `app/api/artifacts/[name]/route.ts:26`, so a backend with no directory to
   return breaks both of those and they have to change with it. Counted rather
   than assumed: `artifactStoreConfigured()` is read in eight modules,
   `storeArtifact` is called from three (`app/api/canvas/upload/route.ts:67`,
   `lib/providers.ts:226` and `:267`), and `artifactUrl` from one
   (`lib/providers.ts:362`). Cost: real work, plus a new paid dependency, plus a
   store to keep clean.
3. **Split the surfaces.** UI on Vercel, execution on the VPS. Cost: two
   deployments, a network hop for every artifact, and a second place for
   configuration to drift. It buys the least of the three.
4. **Park it.** Cost: the voice lane on EditForge stays refused, and keeps
   saying so honestly.

## The recommendation, and the decision left open

Park it. Option 4 today, then option 1 or option 2 later as a deliberate choice
about where EditForge lives.

The reason park is not a dodge: the TQO render lane does not use this path. It
calls ElevenLabs from n8n Cloud and writes the MP3 to Google Drive, which is
recorded in `SYS_OPS_the-tqo-render-lane-and-two-content-stores_v1_2026-09-10.md`
and in `SYS_OPS_the-anthropic-funding-lane_v1_2026-09-11.md`. So nothing Tee is
currently shipping is blocked by `artifactStore: false`. Spending a day on a
blob store now would buy a capability nothing is waiting on, and it would be
spent before the question of where EditForge runs has been answered. Answer that
first and the artifact store answers itself.

Tee has not ruled on this. It is filed open.

## Two corrections, recorded so nobody re derives them

**I claimed EditForge production runs on Hostinger. It does not.** Tee corrected
it in the session, in his words: the EditForge url is a software on Vercel, not
the n8n workflows, and they are different. He was right. Verified afterwards:
`dpl_4PDLTgbhsQUKRycMdyefVfskfoBf` is READY with `target: "production"` on
commit `be3eb47`, and the live health read says `store: "kv"`, which is Vercel
KV. My error class was reasoning from repository contents to deployment state,
which is the precise thing the `deploy-readback` skill exists to stop. The
compose file being correct told me nothing about what was serving.

**I asserted "set it in Vercel" as a fact when it was an inference.** I flagged
that myself before Tee pushed back, and it later turned out to be the right
place anyway. Being right by luck is not the same as having checked, and the
first law in `CLAUDE.md` is about the checking.

## What the Vercel agent did, verified

`dpl_9iZuKYXY8ZBqzVyGCJwLyrJ3z1RU`, read back from Vercel today rather than
taken from the agent's report: READY, `target: "production"`, aliased on
`editforge.vercel.app`, `source: "cli"`, ready at 2026-09-11T23:48:09Z, on commit
`be3eb4702998ef2f20460f4e1fbb624e38485020`. Its metadata says
`action: "redeploy"` with
`originalDeploymentId: dpl_4PDLTgbhsQUKRycMdyefVfskfoBf`, which is the honest
signature of an environment variable change: same commit, new build, no code
moved.

The agent set `ELEVENLABS_VOICE_ID` in Production only, and it declined to
report the provider as ready because `/api/providers` needs a credential it did
not have. Both calls were right. The 401 measured above is the same wall it hit.

## What is still unverified

The voice provider's own readiness detail, `credentialSet: true`,
`settingsMissing: []`, `readyToRun: false`, comes from reading
`lib/provider-registry.ts:577` and `app/api/providers/route.ts` plus the Vercel
agent's report. I could not measure it live: `/api/providers` is behind the
bearer token, and a credential does not belong in this session. So that line is
source read and reported, not measured, and it is labelled that way on purpose.
What is measured is `artifactStore: false`, which is the flag that decides the
refusal, and that one came straight off the live surface.

## DEVON RECEIPT

```
AREA: Systems, Podcast
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-editforge-artifact-store_v1_2026-09-12
DATE: 2026-09-12
DECISIONS: none ruled. The recommendation put to Tee is to park the artifact store, option 4, and to pick later between running EditForge where a volume exists, option 1, and putting a blob store behind the existing four call site interface, option 2. The one decision taken inside this arc was mine and it was a refusal: not to set EDITFORGE_ARTIFACT_DIR on the Vercel project, because flipping that flag green would let a voice run spend real ElevenLabs characters and then serve 404 for the audio, which is worse than the honest refusal the flag was built to give. Recorded rather than done.
FINDINGS: EditForge production on Vercel answers 503 degraded, with all four conjuncts of productionReady false, artifactStore false, executionReady false, workerConfigured and workerReachable false, accessGate false and sessionSecret false, while the durable store itself is healthy on Vercel KV with three variables present; the voice lane refuses because the artifact store is the filesystem at both ends, artifactDir reading EDITFORGE_ARTIFACT_DIR at lib/artifacts.ts:109, storeArtifact writing with fs.mkdir and fs.writeFile at :200 and :201, and the GET route serving with fs.stat and createReadStream at route.ts:41 and :69 including hand rolled byte ranges, so no directory on an ephemeral filesystem satisfies both halves; the refusal is deliberate and documented at lib/artifacts.ts:117-119 and .env.example:17-20, built so a voice submit that would refuse says so before a provider has been paid for audio the studio then throws away; there is no object store to fall back to, a case insensitive grep for blob, aws, s3, storage and minio in package.json at be3eb47 returning nothing; compose.hostinger.yaml already solves the same problem for a host with a disk, EDITFORGE_ARTIFACT_DIR set at lines 30 and 83 with the named volume mounted at 48 and 89; the artifact abstraction is not sealed, artifactDir() being called directly from outside its own module at modules/canvas/render.ts:112 and at app/api/artifacts/[name]/route.ts:26 while artifactStoreConfigured() is read in eight modules and storeArtifact is called from three, so the blob store option is wider than the four definitions it looks like, which was corrected inside this arc by counting the callers rather than estimating them; and the larger finding nobody was looking for, that there is no human sign-in path on that surface at all, passkeys status answering available false count zero and Google status answering available false, so a browser is redirected to /login and cannot get in, leaving editforge.vercel.app a token only API surface protected by EDITFORGE_MCP_TOKEN, which is the benign reading because proxy.ts fails closed but is still a live fact Tee did not know.
OPEN: where EditForge runs is undecided, and the artifact store answer follows from it rather than the other way round; no human can open the EditForge UI on the production surface today and that needs a ruling, not a fix taken unasked; the voice provider's readyToRun detail is source read and reported rather than measured, because /api/providers is behind the bearer token; every open item from the previous arc stands, which are the ElevenLabs key rotation at the provider that Tee is checking, the 16 character floor on deploy/soul/main.py _require blocked until he confirms his console token length, the watchdog alarm negative control blocked until he sets one tqo_content row to Error, the 45 grandfathered SYS_OPS docs needing a ruling, TSWS 00 still carrying a literal placeholder worker URL, the presence total_breaches watch at 1500 ms, and the voice hold with its three line listen test before anything narrated by the clone ships.
STATUS: filed, nothing shipped and nothing changed. No repository code was touched in this arc and no Vercel setting was changed by me; this document is the only artifact. Every claim in it was measured today against the live surface or read off a named file and line, and the two things that could not be measured are labelled in the text rather than rounded up. The one deployment this arc touched, dpl_9iZuKYXY8ZBqzVyGCJwLyrJ3z1RU, was Tee's Vercel agent setting ELEVENLABS_VOICE_ID in Production, and it is READY on target production on commit be3eb4702998ef2f20460f4e1fbb624e38485020 as a redeploy of dpl_4PDLTgbhsQUKRycMdyefVfskfoBf, verified here rather than taken from the agent's report.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
