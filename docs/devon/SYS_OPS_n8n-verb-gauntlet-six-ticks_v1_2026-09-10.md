# SYS_OPS: the n8n verb gauntlet, six ticks

Dated 2026-09-10. Supersedes nothing; it is the record of one loop Tee ordered
against one guard, and it closes with his ruling that the sixth tick was the
last.

## What was run

Tee's instruction was "put the telemetry on a gauntlet loop for the verbs". The
guard under attack is the claim that `app/services/n8n_telemetry.py` and
`app/api/v1/n8n_executions.py` are read only by construction: they can speak no
HTTP verb but GET.

Each tick spawned ONE fresh adversary in its own git worktree, pinned to the
current head with `git checkout -B verify <sha>` and made to echo
`git rev-parse --short HEAD` back, because a worktree does not start on the
parent's HEAD. Each was told every shape already closed, so nothing was
resubmitted. Each had to show a green suite AND a request line logged by a
capture server on 127.0.0.1. Reasoning from a library's source was not accepted
as proof, and none of the six offered it.

## Six ticks, six breaks

Every one of them was carried to a real socket, and every one is now a probe in
one of the two corpora.

1. Two shapes at once. `client.request("DELETE", url)` and
   `client.send(httpx.Request("POST", url))` sat inside the production fetcher
   while a NAME based syntax walk reported 41 passed. Closed by folding the verb
   out of a tracked dispatcher's arguments rather than reading the callee's name.
2. `_verb = "de" + "lete"` handed to `getattr`. No value analysis can see a verb
   assembled in a variable, so the SHAPE was refused instead.
3. `request.method = "POST"` on a prebuilt request, then `client.send`. Every
   rule to that point reasoned about a call site and this one sat at none.
   Refused by shape, whatever the value.
4. `client.request(**{"method": "DELETE", ...})` and
   `object.__setattr__(request, "method", "POST")`. The first spelled DELETE in
   full at a tracked callee and was invisible because the container was a dict.
   That tick forced the design change: the guarantee moved from the syntax walk
   to an EXECUTED check that installs a recording transport under the real
   fetcher and asserts on the request the transport is handed.
5. A second egress door. `urllib.request.urlopen(Request(url, data=b"{}"))`
   appended to the service, logging POST on a retry endpoint with the API key,
   while the suite reported 191 passed. Neither layer could see it: `urllib`
   promotes GET to POST purely because `data=` is not None, so no verb token
   exists, and `urlopen` never touches httpx, so the recorder's silence read as
   a pass. That is when the honest limit of the executed check was written down:
   it audits ONE FUNCTION, not the module's egress surface.
6. An asymmetry and a fetcher that behaved while watched. `getattr` was refused
   by shape when handed an unreadable name; `setattr` was only checked for its
   values, so `setattr(_req, "method", "".join(chr(c) for c in (80, 79, 83, 84)))`
   set a live POST with no verb string in the file. And the executed check drove
   ONE hand written URL while every production URL carries `includeData=false`
   from `_executions_url`, so a fetcher branching on that token was GET under
   the recorder and POST on the wire. The capture is the finding in two lines:

   ```
   POST /api/v1/executions?limit=5&includeData=false HTTP/1.1
   GET  /api/v1/executions?limit=1 HTTP/1.1
   ```

The sixth adversary of the loop returned a PARTIAL rather than a break, graded
that way by itself and confirmed here. It planted `X-HTTP-Method-Override:
DELETE` into the header dict `_read_pages` builds, and every layer stayed silent
with the suite at 215 passed while a capture server logged the header leaving on
the real production read. The verb on the wire was GET, so nothing mutates
unless an intermediary honours the override, and n8n on Express does not by
default. The defect was not a live write. It was that this file names those
three header names as dangerous and never inspected the place production writes
them, which is a guard credited for a check it never performed. Closed.

## What the guarantee is now

Four claims, and it needs all four. Any one of them alone was beaten during this
loop.

1. `test_the_audited_fetcher_is_the_only_door`. A measured import allowlist, a
   banlist the allowlist cannot relax, `httpx` importable only inside
   `_httpx_get`, pinned members of the two local packages, and dynamic code
   refused by shape. One door.
2. `test_the_audited_fetcher_cannot_tell_it_is_being_watched`. `_httpx_get` may
   contain no branch at all, and the executed check drives the URLs
   `_executions_url` itself produces rather than hand written ones.
3. `test_the_production_read_path_sends_only_gets`. `read_all` driven with no
   fake at all, across two pages so the cursor URL is built, with one shared
   reader naming a verb other than GET, any override header, or any path but
   `/api/v1/executions`.
4. The syntax walk, kept because it is cheap and names the offence precisely.

## Three doors nobody attacked, found by probing the fixes

These matter more than the tick count, because each one was open at the moment
the previous fix was called done.

* The import allowlist was keyed on the MODULE, so `from app.services import
  n8n_retry` satisfied it while `import app.services.n8n_retry` did not. Wire
  proved with a sibling module holding the POST, imported by the route beside
  `n8n_telemetry`: `POST /api/v1/executions/6679/retry` with the API key, suite
  at 205 passed, both guarded files innocent.
* `from app import services` bound the package rather than a pinned member, so a
  sibling was reachable through it with no import naming it.
* A module name spelled as a STRING has no import node to judge, so
  `getattr(builtins, "__import__")("socket")` walked past an import allowlist.

## Three findings against the guard's own author

Recorded because the pattern is the point: a rule with no control that has been
watched failing is a rule that is being credited.

* The banlist was decorative under test. With it emptied, all ten probes still
  passed, because the allowlist caught every one on its own. It now has a
  control that widens the allowlist by one entry the way a contributor would.
* A relative import branch was written and then DELETED. Neutering it changed
  nothing, because `module` keeps its leading dots and `.n8n_retry` is never on
  the allowlist. The probe stayed, the branch went, and a comment says why.
* The widened URL set left everything green when neutered, because on clean
  source there is no branch to expose. It earned a control that holds open the
  seam it actually covers: a mapping lookup diverges with none of the refused
  node types.

Per rule neuters are what caught all three. One shared green run would have
credited every one of them.

## Method notes worth keeping

* A worktree does not start on the parent's HEAD. Every prompt pinned the sha as
  its first instruction and made the agent echo it back, so a wrong base would
  have shown up in the receipt rather than in the verdict. All six echoed the
  right one.
* No adversary was allowed to run the bare full suite. One shared PostgreSQL
  cluster means concurrent runs collide on `users_email_key`, which reads as a
  branch failure and is not one.
* The guarded source files were sha256 checked before and after every probe, in
  every tick, including the ones run in this session's own tree. No live
  mutating verb was left anywhere.
* Every adversary report was reproduced here before being acted on. All six
  reproduced exactly.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_n8n-verb-gauntlet-six-ticks_v1_2026-09-10
DATE: 2026-09-10
DECISIONS: Tee ordered the gauntlet loop on the verbs and then ruled the sixth tick the last, so the loop ends at six rather than at the three consecutive holds it was originally to stop on; the design change at tick four, moving the guarantee from the syntax walk to an executed transport check, was taken on the adversary's own argument that the enumeration of places a verb can sit is finite while the ways to set one string field are not; a relative import branch was deleted rather than kept after its control showed it refusing nothing
FINDINGS: six adversaries each broke the guard once and each break reached a real socket, the shapes being a generic dispatcher taking the verb as data, a verb assembled in a variable and handed to getattr, the verb set as object state on a prebuilt request, a verb splatted from a dict plus the setattr dunder, a second egress door built on urllib.request where the verb is implied by data= rather than spelled, and an asymmetry that left setattr with no shape refusal combined with an executed check that drove one hand written URL while every production URL carries includeData=false; three further doors were found by probing the fixes rather than by any adversary, the import allowlist being keyed on the module so a sibling module satisfied it, the package bindable as a name, and a module name spelled as a string having no import node to judge; three rules were found to be decorative under test, the banlist, a relative import branch and the widened URL set, and each now carries a control that has been watched failing or was deleted; the sixth adversary of the loop returned a partial, a forbidden method override header planted where production assembles its headers passing every layer with the suite at 215 passed, graded as not a live write because the wire verb stayed GET and n8n on Express does not honour the override
OPEN: nothing on this guard; the loop is closed at Tee's ruling and the guarantee now rests on four claims each with its own negative control; the ElevenLabs key found as a literal in the archived Rendering sub workflow still needs rotating at the provider and that is Tee's to do; the 45 grandfathered SYS_OPS docs still need his ruling; the contrast pass on /control is still owed
STATUS: closed; PR 200 merged as a097469 with all six CI checks green on 73978fa, carrying ticks four and five plus the three self found doors; tick six's coverage gap closed in the follow on PR on this branch; the guard is 217 tests, 32 probes across two corpora, and every new rule this arc has a control that has been watched failing; guarded source files verified byte identical by sha256 after every probe in every tick
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
