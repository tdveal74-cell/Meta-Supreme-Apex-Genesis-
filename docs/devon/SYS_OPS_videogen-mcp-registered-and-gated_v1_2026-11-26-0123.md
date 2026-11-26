# VideoGen MCP registered at project scope and gated

Status record for the `claude/mcp-videogen-integration-v7wvjx` branch, pull
request #493. First written 2026-11-26 at 0123Z, the stamp in its name, and
revised six times the same day, last at 0404Z after a fourth gauntlet pass on
the avatar lane correction and a fifth on its wording, after two gauntlet rounds: three
cold critics, two refuters per finding and eight receipt verifiers on the first
commit, then nine fix verifiers, two more critics and their refuters on the
revision; what the gauntlet changed is marked below. Supersedes nothing. It follows
`SYS_OPS_graphify-registered-and-gated_v1_2026-10-21-0744.md`, which is the
pattern this change copies.

## What arrived

Tee handed the session one line, the VideoGen connect link
`https://mcp.videogen.io/mcp?vg_client=claude`, on a branch named for an MCP
integration. VideoGen is a video generation API: narrated video from a script
or an uploaded voiceover, image and clip generation, text to speech, music,
avatars, upscaling, project export, all paid from the account's credits.

## What shipped

- `.mcp.json` registers `videogen` at `https://mcp.videogen.io/mcp` and
  `videogen-docs` at `https://docs.videogen.io/_mcp/server`, both
  `type: http`. `.claude/settings.json` enables both in
  `enabledMcpjsonServers`. Project scope rather than user scope, for the reason
  the Graphify record gives: a user scope entry lives in the container's home
  directory and is wiped with it.
- `"videogen"` is in `NAMED_SERVERS` in `.claude/hooks/gate_ledger.py`, so
  every VideoGen tool that is not a read needs a human signal inside the two
  hour window. No ruling was asked for that line; the Graphify precedent carried
  one ("Add it to the list", 2026-10-17). The direction is the conservative one,
  more calls need a signal, so it shipped and was offered to Tee on the card
  beside the sign in route rather than held. He confirmed it the same day,
  cancels included.
- `CLAUDE.md` names VideoGen in the gated list and carries a short section,
  "MCP servers in .mcp.json", on how a registered server gets its sign in and
  which VideoGen inputs put a rented voice or face on the work. The first
  version was a paragraph wedged inside the gate section, between its bullets
  and the "Not a sandbox: it reads" caveat, whose "it" then pointed at VideoGen;
  the gauntlet found that, and the section now sits before the Jev router.
- `test_gate_ledger.py` pins the fifty one documented tool names, thirty one
  gated and twenty passing, under four server spellings; the docs server's one
  tool; a parity test that every server in `.mcp.json` is enabled in settings
  and gated on an unlisted write verb; and, after the gauntlet, that a
  WaveSpeed style `estimate_only` flag passes nothing on VideoGen for each of
  the five verbs `WAVESPEED_QUOTE` names. The first version asserted that
  flag only on `generate_video_clip`, which the exemption never names, so the
  `"wavespeed" in server` condition had no test behind it: a critic deleted
  the condition and 285 selected tests stayed green.

## The URL

The connect link carries `?vg_client=claude`. The repo registers the canonical
`https://mcp.videogen.io/mcp` from the vendor's docs instead. The reason is
measured and takes two hops: the server's 401 carries
`WWW-Authenticate: Bearer realm="VideoGen MCP", resource_metadata="https://mcp.videogen.io/.well-known/oauth-protected-resource/mcp"`,
and that document's `resource` field is `https://mcp.videogen.io/mcp` with no
query string, so an OAuth client that checks the configured URL against the
declared resource would refuse the tagged form. Both URLs were probed on
2026-11-26 with an unauthenticated `initialize` request and returned byte
identical 401 bodies, so before sign in the tag changes nothing. What it does
once a token is present was not and could not be measured here; the vendor
documents no `vg_client` parameter, and the tag reads as client attribution.
If Tee wants it kept, it is a one line change and the parity test does not
care.

## How it was checked

- An unauthenticated `initialize` POST to either URL returns HTTP 401 with the
  `WWW-Authenticate` header quoted above and the JSON-RPC error "Missing
  VideoGen credentials. Send an API key (create one at
  https://app.videogen.io/api) or an OAuth access token as an 'Authorization:
  Bearer <token>' header." A GET returns 405. The protected resource metadata
  names the authorization server `https://mcp.videogen.io`, whose own metadata
  points at Supabase Auth endpoints and advertises a registration endpoint, so
  Dynamic Client Registration is real. No credential is in the repo and none
  was entered.
- The docs server answered `initialize` with no credential at all, as
  `fern-docs-mcp-server` 1.0.0 over SSE, and `tools/list` returned one tool,
  `searchDocs`, annotated read only. Its name begins with `search`, so
  `READ_VERB` passes it, and the `videogen` substring still gates any write
  verb it grows later.
- The tool names come from `docs.videogen.io/libraries/mcp`, read on
  2026-11-26. Its tables name fifty one tools across the two transports:
  `open_uploader` is hosted only and `upload_file` is local only, so each
  transport reaches fifty. The vendor's own counts disagree with each other:
  the page says "The server registers 49 tools: 45 API tools plus four guidance
  tools", the `open_uploader` row says "Not counted in the 46 API tools above",
  and `llms.txt` says "50 tools: 46 VideoGen API tools plus 4 operational
  guidance tools". The fifty one in the tables is the number this record
  trusts, because a script diffed the test lists against every backticked name
  in those tables: fifty one in both, none missing, none extra, and the REST
  mapping table has forty seven rows, the fifty one less the four guidance
  tools, which have no REST equivalent. The live catalogue was not read,
  because the server answers 401 before sign in, so the tests pin the documented
  names and the rule, as the Graphify tests did before its names could be read.
- `classify` was run, not read: `mcp__videogen__script_to_video` returns
  gated, `mcp__videogen__get_me` passes, `mcp__videogen__cancel_workflow_run`
  is gated (a cancel is an outward change and `cancel` is no read verb),
  `mcp__videogen-docs__searchDocs` passes, `mcp__videogen-docs__frobnicate`
  is gated, and `mcp__claude_ai_VideoGen__generate_avatar` is gated.
- `test_gate_ledger.py` went from 962 to 1169 passed on the first commit. With
  `"videogen"` removed from `NAMED_SERVERS` the 124 write cases went red, the
  80 read cases stayed green, and the docs server test and the parity test went
  red; with it restored, all 207 new cases passed. Independent verifiers
  reproduced every one of those counts in their own worktrees. The parity test
  holds for the two servers already registered as well: `blotato-help` is
  gated by the `blotato` substring and `graphify` by name. The revision's
  counts, 1174 in the gate file with the five price flag cases, and both
  gauntlet rounds are recorded in pull request #493's description.
- `test_devon_integrity.py`, `test_estate_reconcile.py`,
  `test_automation_registry.py` and `test_agent_hq.py` passed together, 623
  tests, after the first edits; `test_jev_route.py` passed 3111; the standalone
  job as `ci.yml` lists it passed 6067 with `PYTHONPATH` and both database
  URLs unset; the full API suite passed 10073 with 2 skipped; `ruff check .`
  clean; both JSON files parse.
- A fourth gauntlet pass at `c2e5b28`, the avatar lane correction: five
  independent verifiers in their own worktrees, each told to refute one claim
  by re-reading the n8n instance live and the repo. Four confirmed and one
  refuted. The refuted claim was the composition in the verifier's own prompt,
  which said a search for "avatar" returns both active workflows: the
  search, which matches names and descriptions, returns four rows, one active
  (`snRyzuQhPxkidipW`) and three inactive, one of those three matching on its
  description alone, and `m22GM2MZYUqGc1Gx` is active on the instance but
  carries no "avatar" in its name or description, so the search cannot find
  it. The doc's text never
  made that claim; it reads the two active workflows by id. The four
  confirmations carried precision notes, each folded into the bullets below:
  `look_id` is optional and the code fills the default; a repeated approval
  returns the existing registration rather than throwing; the bytes check
  covers length and SHA-256; the approve workflow also saves no executions;
  and the render workflow carries one Google Drive node the 2026-09-22 Drive
  table in `CLAUDE.md` predates. A fifth pass at `9a98596`, three verifiers on
  the folded wording: three of three confirmed against the same live reads,
  with the two hedges below as its only notes.

## What the owned voice and likeness rule says about this server

The rule is HardRule 6 in `services/devon/persona.py`, "Voice and likeness are
owned, never rented", and `test_devon_owned_voice.py` guards it; the first
version of this doc said the rule was written in `CLAUDE.md`, which only
applies it, and the gauntlet caught that. Read on 2026-11-26 from the vendor's
REST pages, except `storyboard_to_video`, whose REST page returns "Page Not
Found" and whose fields come from the MCP tool table, this is where VideoGen
can put a rented voice or face on the work:

- `script_to_video` and `slideshow_to_video` narrate with a catalogue voice
  whether or not `voiceId` is given ("A default voice is used when omitted").
- `text_to_speech` speaks text in a catalogue voice from `list_tts_voices`.
- `generate_video_clip` with `spokenDialogue` has the model synthesize the
  voice from the text, shaped by `voiceDescription`.
- `video_to_video` with `audio: GENERATE` "uses newly generated audio instead"
  of the source video's audio; the default, `KEEP_ORIGINAL`, keeps it. A restyle
  of Tee footage with `GENERATE` drops his recorded voice for generated audio.
  The second gauntlet round found this one missing.
- The `CHANGE_NARRATOR` edit re-narrates every AI narrated asset with a new
  catalogue voice and, optionally, an actor avatar; a project with no AI
  narrated asset is skipped unchanged. `TRANSLATE_PROJECT` re-narrates those in
  the target language unless disabled, its `changeVoice` defaults to true, and
  with `dubVideos` true it also dubs "the speech in the project's uploaded
  videos into the target language, replacing their original audio", billed per
  second of speech. Whose voice the dub carries is not stated on the page read;
  either way it is audio nobody recorded over Tee's own footage. The second
  round found `dubVideos` missing too.
- `actorEntityId` on `script_to_video`, `slideshow_to_video`,
  `voiceover_to_video` and `generate_avatar` (where it is required), and
  `actorEntityIds` on `storyboard_to_video`, deliver the narration through "a
  built-in stock actor or an ACTOR entity with an image reference". A stock
  actor is a rented face. An ACTOR entity built from Tee's own reference images
  is not. Two unknowns: `voiceover_to_video` lists `actorEntityId` on its REST
  page while the vendor's MCP tool row omits it, and the live schema is unread;
  `storyboard_to_video` has no REST page; its narration is read from the
  vendor's changelog v2.3.3 (2026-10-05), where "each scene's `voiceoverScript`
  can now hold about 30 seconds of speech", so a scene with spoken lines is
  narrated in a vendor voice, and its `actorEntityIds` come from the MCP tool
  table. The docs server found that page; the REST pages could not.

Inside the rule: an uploaded Tee clone track from ElevenLabs into
`voiceover_to_video` with no `actorEntityId`, or into `generate_avatar` on an
ACTOR entity built from Tee's own images, with no translate or narrator edit
after it. The first version of this doc called `voiceover_to_video` the fitting
lane without saying it takes `actorEntityId`; it does, so the fit holds only
with that field left out or pointing at Tee's own entity. `upload_file` is not
on the hosted server, so
the bytes go up through `create_file_upload`, which returns a presigned URL,
and a PUT. The gate does not enforce the rule; it only asks for a human signal.
Nothing published under a show's name carries a stock voice or face.

## The avatar lane exists, and this doc said it did not

The first version of this doc, and the card Tee answered at about 03:12Z on
2026-11-26, said "the avatar render lane does not exist yet". That sentence
came from an August profile note and was never checked against the estate,
which is the first law's exact failure: the check cost one search of the n8n
instance. Tee corrected it in chat at about 03:20Z, "I have a avatar lane on
my n8n", and the lane was read live at about 03:24Z:

- `snRyzuQhPxkidipW`, active, 14 nodes, created 2026-10-21, draft and active
  version the same. Its title on the instance is the words TQO & NCO, an em
  dash, then Hugging Face Avatar + Lip Sync; the dash is written out here
  because the docs ban carries no exemption, and `registry/automations.json`
  holds the title as typed. A private
  MuseTalk 1.5 Space on free ZeroGPU behind the VPS worker at
  `comfy.2-24-109-87.sslip.io/_worker/avatar/`, on the credential named "TSWS
  ComfyUI VPS Worker". TQO and NCO call it with `action` health, render or
  status. A render needs `approved_voice_audio: true` and a stable
  `request_id` (the same id and inputs return the same job); `look_id` is
  optional, one of eight Terrance looks, and the code fills
  `edbec2e477cff16bad4f492ed6503f35` when it is left out. A failed or
  interrupted job throws "No automatic retry or paid fallback". The output is
  a private review link, and its own note says "Unreviewed output is never
  registered in V5". It saves no executions, success or error, so its runs
  leave nothing for an execution reader, which is the
  `saveDataSuccessExecution: none` shape CLAUDE.md records for four other
  lanes. One of its fourteen nodes, Download Approved Voice, is a Google Drive
  node on the credential `NW3vR6nNcMoUkJyJ`; the Drive node table in
  `CLAUDE.md` was counted on 2026-09-22, a month before this workflow existed,
  so that count is dated and is not re-run here.
- `m22GM2MZYUqGc1Gx`, titled the same way with Approve HF Presenter Clip
  after the dash, active, 13 nodes, created the same day. It refuses a job unless `visual_reviewed`,
  `voice_identity_confirmed` and `segment_match_confirmed` are all true and
  `reviewed_by` is named, checks the episode key's format and refuses test
  jobs (an `episode_row_id` beginning VERIFY, TEST or SMOKE in any case),
  checks the render receipt (`bridge_verified`, `voice_track_in_clip`), returns
  the existing registration on a repeated approval of the same job instead of
  inserting twice, asks the VPS worker for a clip link that the workflow's own
  note calls revocable (the worker's code is not in this repository, so that
  word is its claim), downloads the bytes and checks their length and SHA-256
  against the reviewed render, then registers the clip in data table
  `7Eq5HbskxapeeHfo` (`at_tqo_presenter_clips`), which `TQO FINAL V5` reads
  through its Presenter: Fetch Clips node. It saves no executions either,
  success or error, so a refused approval leaves nothing to read.
- Inactive beside them: `NCO Forge | Google Vids personal-avatar pilot`
  (2026-11-05), `SCRATCH TQO 46 lip-sync status` (2026-10-26) and `TEMP Claude
  5 Oct: avatar_iii engine test` (2026-10-06, HeyGen).
- Recorded in earlier docs, not re-read today: HeyGen's digital twin group
  `f94efc2551ae403fa8d7c60c1aa5d1d5` with look 4
  (`c89667ba7c474e2694bf18ffc035c604`) made the TQO look on 2026-11-01
  (`SYS_OPS_openmontage-twin-test-and-arc-close_v1_2026-11-03-0703.md`), and
  the open model presenter pipeline on a rented Runpod GPU
  (`SYS_OPS_owned-presenter-pipeline_v1_2026-10-16-0153.md`).

So the owned lane is MuseTalk on his own looks and his approved voice segment,
human reviewed before registration, with HeyGen's filmed twin as a second
route. VideoGen's `generate_avatar` would be a third provider, vendor hosted
and paid, holding his reference images as an entity. The ruling Tee gave on the
03:12Z card, scout it after sign in, was taken on the false premise and was
re-asked once the lane was in view. Tee answered the second card at about
03:35Z in his own words: "Use HeyGen". Recorded as given: the avatar route is
HeyGen, his filmed digital twin on look 4, and VideoGen's `generate_avatar` is
not scouted. He did not rule on the MuseTalk workflows' standing beside that,
so they stay as they are on the instance and nothing here touches them.

## Open

- Sign in. Ruled by Tee 2026-11-26 on a card: the claude.ai custom connector,
  route 1 below. Connecting it is his act; afterwards a session reads the name
  the tools arrive under and adds a `SERVER_ALIASES` row the same day if it is
  a UUID. Three routes reach a VideoGen session, and the first version of this
  doc named only the last two:
  1. A claude.ai custom connector: Settings, Connectors, Add custom connector,
     the bare URL, OAuth through Dynamic Client Registration, no key held
     anywhere. This is the route the vendor documents for Claude, and a
     connector appears in cloud sessions. Its tools would arrive as
     `mcp__claude_ai_VideoGen__*`, which the tests already pin, or under a UUID,
     which the gate records as unmapped and does not refuse until it is listed
     in `SERVER_ALIASES`, as Graphify's was on 2026-10-22. On that arrival
     shape every one of the thirty one writes runs with a ledger row and no
     refusal, so read the name the tools arrive under before trusting the gate
     on them, and add the alias row the same day.
  2. An API key saved as a network secret for `mcp.videogen.io`, where the
     proxy adds the bearer header and the container never holds the key, the
     route the TypeSafe key takes for the Jev hook. Whether the MCP client's
     own connection gets the same injection is unverified until it is tried.
     That the client's connections go through the proxy at all is an inference,
     not a measurement of VideoGen's own: on 2026-11-26 other HTTP MCP servers
     in this cloud session failed with proxy tunnel errors.
  3. Claude Code's `/mcp` on Tee's own machine, which runs the OAuth flow with
     the loopback callback the vendor lists and serves that machine only. A
     cloud container is new every session, so this route never lights the
     server here.
  The recommendation was the connector, because it is the vendor's route, needs
  no key anywhere, and other claude.ai connectors loaded their tools in the
  cloud session of 2026-11-26, so the route reaches a container; the network
  secret second. Tee took the recommendation.
- Avatar. Ruled by Tee at about 03:35Z on a second card, after the first
  card's premise was corrected: "Use HeyGen". VideoGen's `generate_avatar` is
  not scouted. The MuseTalk workflows on n8n were not ruled on and stay as they
  are.
- Measured after a worker restart on this branch at about 03:10Z on
  2026-11-26: the restart read `.mcp.json`, `videogen-docs` loaded and its
  `searchDocs` answered a storyboard query, and no `mcp__videogen__` tool
  loaded, which is the 401 doing what this doc said it would. The parity test's
  premise, that `.mcp.json` plus `enabledMcpjsonServers` is what loads a server
  here, is measured rather than read.
- The live tool names, once readable, are to be checked against `READ_VERB`
  and these tests, and the fifty one updated if the server differs from its
  docs.
- Credit prices were not read. `get_me` is the connection test the vendor
  names; the first call after sign in should be that and nothing that spends.
- `videogen-docs` was added beyond the one URL Tee gave, because the vendor
  recommends it alongside and it is read only, unauthenticated and free. It
  went on the card rather than shipping as the default alone, and Tee ruled
  2026-11-26: keep it.
- The WaveSpeed price exemption matches `wavespeed` by substring, so a server
  named for both vendors (`videogen_wavespeed` and the like) would pass a
  VideoGen generate carrying `estimate_only`. None exists, and none should be
  registered under such a name. The second gauntlet round found it and graded
  it negligible; it is recorded so nobody wraps one vendor in the other's name.
- Two cancels, `cancel_workflow_run` and `cancel_tool_execution`, are gated
  like every other write. A paid run can only have been started inside the
  window, so its cancel is normally inside it too; if that ever bites, listing
  the two as reads is a ruling and a two line change.
- The August profile note that says the avatar render lane does not exist is
  stale, and it reached this doc and a card before anyone read the instance.
  Worth filing to DEVON so the CONTEXT-PILL stops carrying it; the capture key
  is not set here, so that is Tee's to do or to ask for.
- The Drive node count in `CLAUDE.md`, eighteen nodes across six workflows,
  was taken from the estate on 2026-09-22. The MuseTalk workflow created on
  2026-10-21 carries a Drive node on the same credential, so the count is due
  a re-enumeration across every active workflow; it is not raised or lowered
  here, because that number is only changed by re-running the count.
- The dependency audit is red on `main` and this branch inherits it: the
  `requirements.txt` pip-audit step fails on `dnspython` 2.9.0 (CVE-2026-128089,
  fixed in 2.9.2) and `pnpm audit` on three moderate `next` 15.5.28 advisories
  (fixed in 15.5.29), on every scheduled daily run read, 2026-11-21 to
  2026-11-25, and on this head. The first comment on the pull request said
  pip-audit passed, from reading the log's tail; the gauntlet caught it and a
  correction is on the thread. Both pins belong in one separate PR.

## DEVON RECEIPT

```text
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: VideoGen MCP registered at project scope and gated
DATE: 2026-11-26
DECISIONS: register videogen at the canonical https://mcp.videogen.io/mcp and videogen-docs beside it in .mcp.json and enabledMcpjsonServers, project scope not user scope; add videogen to NAMED_SERVERS so every non-read tool needs a human signal, shipped in the conservative direction and confirmed by Tee on a card, cancels included (Tee, 2026-11-26); keep videogen-docs (Tee, 2026-11-26); sign in through the claude.ai custom connector, no key anywhere, alias row on a UUID arrival (Tee, 2026-11-26); the avatar route is HeyGen, his filmed twin, and VideoGen's generate_avatar is not scouted, replacing the scouting ruling taken on the false premise that no avatar lane existed (Tee, 2026-11-26, "Use HeyGen"); name VideoGen in the CLAUDE.md gated list and add a short MCP servers section that maps HardRule 6 (voice and likeness owned, never rented) onto its inputs; pin the fifty one documented tool names, a .mcp.json to settings parity test and the WaveSpeed price flag on VideoGen
FINDINGS: both the tagged and canonical URLs return byte identical 401 bodies before sign in and the declared OAuth resource is the bare /mcp, so the vg_client tag is read as attribution and its effect after sign in is unmeasured; DCR is advertised through Supabase Auth; the docs server is unauthenticated with one read tool, searchDocs; the vendor publishes three tool counts (49, 46, 50) and its tables name 51; gate tests 962 to 1169 on the first commit, mutation 124 writes red and 80 reads green, reproduced by independent verifiers; a rented voice or face arrives through voiceId or its default, text_to_speech, spokenDialogue, video_to_video audio GENERATE, CHANGE_NARRATOR, TRANSLATE_PROJECT with changeVoice or dubVideos, and actorEntityId on four workflows and generate_avatar, while voiceover_to_video without an actor or generate_avatar on Tee's own ACTOR entity, both on an uploaded Tee clone track and with no edit after, stay inside the rule; storyboard_to_video has no REST page and its scenes carry spoken voiceoverScript lines in a vendor voice per the changelog v2.3.3; a worker restart on the branch loaded videogen-docs from .mcp.json and no videogen API tool, measured 2026-11-26; the avatar lane exists on n8n, two active workflows since 2026-10-21 (TQO & NCO Hugging Face Avatar + Lip Sync on MuseTalk, Approve HF Presenter Clip registering reviewed clips to at_tqo_presenter_clips) plus HeyGen's filmed twin, and this doc's first version and a card said it did not, from an unchecked August note; a fourth gauntlet pass at c2e5b28 confirmed four of five claims about the lane live against n8n and refuted the fifth, a composition error in the verifier prompt and not in the doc's text, and its precision notes are folded in; the dependency audit is red on main on dnspython and next and the first PR comment misread it
OPEN: Tee connects the claude.ai custom connector; the next session reads the arrival name and adds a SERVER_ALIASES row if it is a UUID; live tool names unread until then, then check against READ_VERB; credit prices unread, get_me first; the MuseTalk workflows' standing beside "Use HeyGen" was not ruled; the stale August note that no avatar lane exists is to be filed to DEVON (Tee); the 2026-09-22 Drive node count in CLAUDE.md predates the MuseTalk workflow's Drive node and is due a re-enumeration; dnspython 2.9.2 and next 15.5.29 pins in one separate PR before the standing merge grant can act
STATUS: built, tested and put through three gauntlet rounds, a fourth pass on the correction and a fifth on its wording, on the branch; four rulings taken on a card 2026-11-26; counts and verdicts in pull request #493's description; not merged, the dependency audit on main blocks the standing grant
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
