# VideoGen MCP registered at project scope and gated

Status record for the `claude/mcp-videogen-integration-v7wvjx` branch, written
2026-11-26 at 0123Z, the stamp in its name. Supersedes nothing. It follows
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
  hour window. `CLAUDE.md` names VideoGen in the gated list and carries a
  paragraph on what the owned voice rule allows once the gate opens.
- `test_gate_ledger.py` pins the fifty one documented tool names, thirty one
  gated and twenty passing, under four server spellings, plus the docs server's
  one tool and a parity test that every server in `.mcp.json` is enabled in
  settings and gated on an unlisted write verb.

## The URL

The connect link carries `?vg_client=claude`. The repo registers the canonical
`https://mcp.videogen.io/mcp` from the vendor's docs instead, for a measured
reason: the server's 401 names its OAuth resource as
`https://mcp.videogen.io/mcp` with no query string, and an OAuth client that
checks the configured URL against that resource would refuse the tagged form.
Both URLs were probed on 2026-11-26 with an `initialize` request and returned
byte identical 401 bodies, so the tag changes nothing in the answer. It reads
as client attribution for VideoGen's own records. If Tee wants it kept, it is
a one line change and the parity test does not care.

## How it was checked

- An unauthenticated `initialize` POST to either URL returns HTTP 401 with
  `WWW-Authenticate: Bearer realm="VideoGen MCP"` and the JSON-RPC error
  "Missing VideoGen credentials. Send an API key (create one at
  https://app.videogen.io/api) or an OAuth access token". A GET returns 405.
  The protected resource metadata at
  `/.well-known/oauth-protected-resource/mcp` names the authorization server
  `https://mcp.videogen.io`, whose metadata points at Supabase Auth endpoints
  and advertises a registration endpoint, so Dynamic Client Registration is
  real. No credential is in the repo and none was entered.
- The docs server answered `initialize` with no credential at all, as
  `fern-docs-mcp-server` 1.0.0 over SSE, and `tools/list` returned one tool,
  `searchDocs`. Its name begins with `search`, so `READ_VERB` passes it, and
  the `videogen` substring still gates any write verb it grows later.
- The tool names come from `docs.videogen.io/libraries/mcp`, read on 2026-11-26.
  Its tables name fifty one tools. The page says forty nine on the hosted
  server, which is the fifty one less `open_uploader` (hosted only widget)
  and `upload_file` (local stdio server only), and it also says "46 API
  tools" in the uploader's own row, which disagrees with its forty nine. The
  live catalogue was not read, because the server answers 401 before sign in,
  so the tests pin the documented names and the rule, as the Graphify tests did
  before its names could be read. A script diffed the test lists against every
  backticked name in the docs tables: fifty one in both, none missing, none
  extra. The REST mapping table has forty seven rows, the fifty one less the
  four guidance tools, which have no REST equivalent.
- `classify` was run, not read: `mcp__videogen__script_to_video` returns
  gated, `mcp__videogen__get_me` passes, `mcp__videogen__cancel_workflow_run`
  is gated (a cancel is an outward change and `cancel` is no read verb),
  `mcp__videogen-docs__searchDocs` passes, `mcp__videogen-docs__frobnicate`
  is gated, and `mcp__claude_ai_VideoGen__generate_avatar` is gated.
- `test_gate_ledger.py` went from 962 to 1169 passed. With `"videogen"`
  removed from `NAMED_SERVERS` the 124 write cases went red, the 80 read cases
  stayed green, and the docs server test and the parity test went red; with it
  restored, all 207 new cases pass. The parity test holds for the two servers
  already registered as well: `blotato-help` is gated by the `blotato`
  substring and `graphify` by name.
- `test_devon_integrity.py`, `test_estate_reconcile.py`,
  `test_automation_registry.py` and `test_agent_hq.py` passed together, 623
  tests, after the edits; `test_jev_route.py` passed 3111; `ruff check .`
  clean; both JSON files parse. The standalone list and the full suite are
  recorded on the pull request, not here, because this doc was written before
  they ran.

## What the owned voice rule says about this server

Most of what VideoGen makes is a rented voice. `script_to_video` narrates the
script with a VideoGen `voiceId`, `text_to_speech` speaks text in a catalogue
voice, `slideshow_to_video` narrates slides the same way, and the
`CHANGE_NARRATOR` edit swaps one in. None of that goes on anything published
under a show's name, and the rule covers likeness as well as voice, so a
catalogue actor on `generate_avatar` is rented too. The tools that fit the rule
take audio that already exists: `voiceover_to_video` builds visuals under an
uploaded track, and `generate_avatar` animates an actor entity to an uploaded
track. Fed a Tee clone track from ElevenLabs, and for the avatar an ACTOR
entity built from Tee's own reference images, either stays inside the rule.
`upload_file` is
not on the hosted server, so the bytes go up through `create_file_upload`,
which returns a presigned URL, and a PUT. The gate does not enforce the voice
rule; it only asks for a human signal. The rule is written where a session
reads it first, in `CLAUDE.md`.

Whether an actor entity built from Tee's own reference images and animated
by `generate_avatar` is a candidate for the avatar render lane, which does
not exist yet, is a scouting question and Tee's to open. Nothing here starts
it.

## Open

- Sign in. The server's tools will not load in a cloud session until either
  Tee signs in on his own machine (Claude Code's `/mcp` runs the OAuth flow
  with the loopback callback the vendor lists) or saves an API key as a network
  secret for `mcp.videogen.io`, where the proxy adds the bearer header and the
  container never holds the key, the route the TypeSafe key takes for the Jev
  hook. Whether the MCP client's own connection gets the same injection is
  unverified until it is tried; the connection does go through the proxy,
  because the Zoom plugin servers failed this session with a proxy tunnel error.
  The recommendation is the network secret, because an OAuth sign in is per
  machine and a cloud container is new every session. Tee's call.
- The live tool names, once readable, are to be checked against `READ_VERB`
  and these tests, and the fifty one updated if the server differs from its
  docs.
- Credit prices were not read. `get_me` is the connection test the vendor
  names; the first call after sign in should be that and nothing that spends.
- `videogen-docs` was added beyond the one URL Tee gave, because the vendor
  recommends it alongside and it is read only, unauthenticated and free. It is
  one server entry and one settings line to remove if he does not want it.
- Two cancels, `cancel_workflow_run` and `cancel_tool_execution`, are gated
  like every other write. A paid run can only have been started inside the
  window, so its cancel is normally inside it too; if that ever bites, listing
  the two as reads is a ruling and a two line change.

## DEVON RECEIPT

```text
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: VideoGen MCP registered at project scope and gated
DATE: 2026-11-26
DECISIONS: register videogen at the canonical https://mcp.videogen.io/mcp and videogen-docs beside it in .mcp.json and enabledMcpjsonServers, project scope not user scope; add videogen to NAMED_SERVERS so every non-read tool needs a human signal; name VideoGen in the CLAUDE.md gated list with the owned voice rule mapped onto its tools; pin the fifty one documented tool names and a .mcp.json to settings parity test
FINDINGS: both the tagged and canonical URLs return byte identical 401 bodies and the OAuth resource is the bare /mcp, so the vg_client tag is attribution only; DCR is advertised through Supabase Auth; the docs server is unauthenticated with one read tool, searchDocs; the vendor page says 49 hosted tools and 46 in one row, its tables list 51 across both transports; gate tests 962 to 1169, mutation 124 writes red and 80 reads green; script_to_video, text_to_speech, slideshow narration and CHANGE_NARRATOR put a stock voice on the work, voiceover_to_video and generate_avatar take an uploaded Tee clone track
OPEN: sign in route, network secret for mcp.videogen.io recommended over per machine OAuth (Tee); live tool names unread until sign in, then check against READ_VERB; credit prices unread, get_me first; videogen-docs added beyond the one URL given, removable; cancel_workflow_run and cancel_tool_execution gated as writes; generate_avatar with a Tee actor entity as an avatar lane candidate is a scouting question for Tee
STATUS: built and tested on the branch; standalone list and full suite recorded on the pull request; not merged
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
