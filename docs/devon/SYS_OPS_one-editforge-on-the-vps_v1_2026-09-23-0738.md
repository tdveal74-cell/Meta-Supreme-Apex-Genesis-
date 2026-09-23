# One EditForge, on the VPS

Written 2026-09-23. Tee asked for his two EditForge apps to become one, with
everything the Vercel copy did available on the VPS, and Google sign-in with a
passkey. He ruled the VPS at editforge.online the survivor, Vercel paused rather
than deleted, and each merge and the deploy on his explicit word in the session.

## What the two apps were

One codebase, `tdveal74-cell/EditForge`, deployed twice. Vercel built `main`
(`be3eb47`, 2026-09-07) at editforge.vercel.app. The VPS ran
`/opt/editforge/app`, a checkout of `bf5dce7` from 2026-08-29 with 18 edited and
29 new files that were never committed, plus a web image built by hand on
2026-09-21 and six upgrade folders under `/root` that existed nowhere else.

## What was done, in order

1. The whole VPS source went to a private repository first,
   `editforge-vps-snapshot` at `a456411`, with every `.env` file left out and
   a secret scan that stopped the push until each flagged line was reviewed.
2. EditForge PR #63 recorded the VPS edits on their own base and merged `main`
   into them. Main's Google sign-in won over the VPS version: it adds PKCE and
   already fixed the redirect the VPS hotfix patched. `compose.hostinger.yaml`
   now carries what the live box runs; the version on `main` would have
   replaced the host Caddyfile on the next deploy and taken down meta, rakazo,
   hud, tqohr, tsws and the basic auth studio subdomain.
3. The same PR sends a first Google sign-in with no passkey on file straight to
   passkey enrollment. Every later visit is "Continue with passkey", with Google
   kept as recovery.
4. EditForge PR #64 finished the home page's scroll-craft verification: two
   poster paths that pointed at files never committed, a pinned peak where
   nothing moved under the wheel, and phone headings that joined words.
5. Merged `1a8332f` and `55617cf`. Images published at `55617cfec10a`. The
   deploy ran as a dry run, then live: every EditForge service reported healthy
   and editforge.online/api/health answered healthy with productionReady,
   executionReady, workerReachable and artifactStore all true. The edge
   container read Running, not recreated.
6. n8n `DEVON — EditForge Handoff (Build 07)` now submits to
   editforge.online. Published and read back: activeVersionId equals versionId,
   sameAsDraft true, the code node identical to what was written, no reference
   to Vercel left in the workflow.
7. DEVON's `EDITFORGE_URL` default moved to editforge.online.
8. The Vercel project is paused; editforge.vercel.app answers
   `503 DEPLOYMENT_PAUSED`.

## Not verified

This container is blocked from editforge.online and from Google Drive, so no
browser here has loaded the live site. The sign-in, the passkey enrollment, the
home page scroll and the other subdomains are Tee's to check on the phone.
Whether Railway sets `EDITFORGE_URL` itself, which would override the new
default, was not read, because reading Railway variables returns their values.
Data in Vercel's KV store (jobs, any passkey enrolled there) did not move.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_one-editforge-on-the-vps_v1_2026-09-23-0738.md
DATE: 2026-09-23
DECISIONS: Tee ruled the VPS the one EditForge, pause Vercel then delete later, merge and deploy, Google sign-in with a passkey, and his own presenter b-roll in place of stock people on the site.
FINDINGS: The VPS ran uncommitted code 28 commits behind main. The Hostinger compose template on main would have taken down six subdomains on the next deploy. The home page shipped with two missing posters and a dead pinned peak. A paid job from DEVON Build 07 is refused by the VPS unless it carries confirmBillable, by design.
OPEN: Tee updates the n8n credential "EditForge MCP Token" to the VPS token and the Claude EditForge connector URL to https://editforge.online/api/mcp. Tee rules whether DEVON's approval card counts as the paid-run confirmation for Build 07. The presenter b-roll swap waits on the clips reaching the private repository. The local tools address disagreement (172.16.2.1 against 172.16.8.1) is recorded in the EditForge local-tools README and unresolved.
STATUS: Merged, deployed and health checked. Build 07 repointed and read back. Vercel paused. Live browser checks outstanding.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
