# n8n Cloud to VPS migration, pre-flight worklist

    status: pre-flight, nothing migrated
    source: thequietoperator.app.n8n.cloud (n8n Cloud)
    target: the Hostinger VPS srv1936193 (2.25.140.44), n8n.editforge.online,
            currently empty of workflows
    tool: scripts/n8n_migrate.py
    read from the live Cloud estate on 2026-08-31

## What travels and what does not

A workflow export carries nodes, connections and settings. It does not carry
credentials, data tables, or any of the identifiers those things are addressed
by. Four classes of reference break silently on import, because n8n mints new
ids on the target and the imported JSON still names the old ones.

    class                     count on Cloud   what breaks
    credentials                          28    every node that authenticates
    data tables                           9    every dataTable node
    sub-workflow calls           see below     Execute Workflow nodes
    error workflow settings      see below     crash notification routing

None of these produce an import error. They produce a workflow that looks
imported and fails on its first run.

## 1. Credentials, 28 of them

Credentials must be created by hand on the VPS before import, then every node
repointed to the new id. Three groups, in rising order of difficulty.

**API key and header credentials, straightforward.** Recreate with the same
name and paste the secret. The DEVON lanes need these four:

    Devon Capture Key          FYRvkRTOcROEYZ9P   httpHeaderAuth
    Devon Soul Service Token   SFou54MzuKGj3MwV   httpHeaderAuth
    EditForge MCP Token        THqWeT7Fd0kiiGSv   httpHeaderAuth
    Bearer Auth account        uY9QooBk8JVzvDWP   httpBearerAuth

Plus ten generically named header credentials, `Header Auth account` through
`Header Auth account 10`. Those names carry no information about what they
authenticate. Work out what each one is from the nodes that reference it
before you recreate it, or you will recreate ten indistinguishable
credentials and guess at the wiring.

Then the service keys: Pinecone account, Pinecone Api-Key, OpenRouter
account, Airtable Personal Access Token account, Eleven Labs, Cerebras Cloud,
Speechify API, Pexel Header Auth, GitHub, SMTP account.

**OAuth credentials, the real blocker.** Three of them, all Google:

    Gmail account          vsTKuAilHmpYCc5L   gmailOAuth2
    Google Drive account   WMz320icjnur7rDL   googleDriveOAuth2Api
    YouTube account 2      GA3sbYnmJAAo0AVC   youTubeOAuth2Api

OAuth cannot be copied. Each needs a fresh consent flow on the VPS, and the
redirect URI for the VPS host has to be registered in the Google Cloud project
first. See the callback section below. Do this before anything else; it is the
only item on this list with a dependency outside your own estate.

`Notion account` (69GcWnTi2TDh1FAN) is NOT one of these. Its type is
`notionApi`, an internal integration token, not `notionOAuth2Api`. It needs no
redirect URI, just the token pasted like any other API key. Read credential
types rather than names here: several of the names in this estate suggest an
auth model the credential does not use.

## 2. Data tables, 9 of them

Schema and rows both stay behind. Create the table, then decide separately
whether its contents move.

    devon_state_ledger        VYyno7pDWmY6uxBz   34 columns
    approval_queue            u6wzeN5y9LNxROsN   16 columns
    devon_soul_commit_log     U9fnVy19Vc8kvQAw    9 columns
    devon_github_checkpoints  7OT3H8GzyqP5RgmJ    7 columns
    devon_heartbeat_log       Adg1Gd9HML7Q4L3U    6 columns
    devon_build12_feed_log    QeoV4V4dYXXN8dBR    6 columns
    devon_soul_setup          VBW2nTLQcaZ8l74a    4 columns
    tqo_content               tc2lBzham6J65EP7   53 columns
    nco_content               NTUtlcfrvNmS2oau   53 columns

Every column name, type and position is recorded in
`docs/devon/n8n-datatable-schemas.json`, read from the live instance on
2026-08-31. Build the tables from that file rather than from a screen, because
a 34-column and a 53-column table are not things anyone retypes correctly, and
a column missing from the target does not announce itself: the insert node
simply drops that field and the row lands looking complete.

The ledger count in an earlier revision of this document said 33. It is 34.
The types are worth attention too, since most columns are strings but not all:
`terminal` and `human_watched` are booleans, and `intent_level`, `attempts`,
`artifact_count` and `trace_count` are numbers.

Two rulings apply here.

`approval_queue` holds plaintext decision tokens in its `token` column. It is
excluded from the Weekly Table Backup on purpose. It stays excluded here.
Recreate the schema empty. Any pending approval on Cloud gets decided on
Cloud before cutover, never exported.

`devon_state_ledger` is the one table where leaving rows behind has a
consequence. It is keyed by `intent_id`, and the Ledger Janitor cancels jobs
that have been non-terminal past 96 hours. Start the VPS with an empty ledger
and open Cloud jobs simply never terminate on either side.

Ruled 2026-08-31: drain Cloud to terminal states before cutover, rather than
copying non-terminal rows across. The Janitor already cancels anything stuck
past 96 hours, so most of the draining happens on its own if you let Cloud run.
The VPS then starts with a genuinely empty ledger and no half-copied envelope
history. This makes the cutover wait on the slowest open job, which is the
cost of the ruling and is worth naming out loud.

## 3. Sub-workflow and error-workflow references

`Execute Workflow` nodes address their target by workflow id. So does the
`errorWorkflow` setting. Both survive import as text and both point at
workflow ids that do not exist on the VPS.

The TSWS chain is built this way. `TSWS 01 Post-Production Master` drives the
others, and `TSWS 00 Render Job` is a sub-workflow with no trigger of its own.
All six are active. Import the whole chain, then walk every Execute Workflow
node and repoint it.

Error routing is the quieter half. `OS Error Handler` (rqYmaQh91iCce8DJ) is
active with no trigger of its own, which is what an error workflow looks like.
`DEVON Error Alarm` (XDQXwgFkUhYxoEjG) is the same shape, currently inactive.
Workflows naming either one in their settings will import cleanly and then
route crashes nowhere. Nothing will tell you. Check this deliberately.

## 4. Webhook hosts, 6 paths across 5 workflows

Every lane is on `https://thequietoperator.app.n8n.cloud/webhook/...` and
every one of them has an external poster that has to be told the new address.

    devon-ledger             z9j2I8h0RnbDKGBO   POST   x-devon-key
    devon-approve-request    syRVj0G47mA1b0Xn   POST   x-devon-key
    devon-approve-decide     syRVj0G47mA1b0Xn   GET    token in link
    devon-capture            pPIt2cELH2RVZktS   POST   x-devon-key
    devon-inbox              5s6CwWWelffqszQe   POST   x-devon-key
    devon-build12-upstream   VznESplSFCs8ldph   POST   x-devon-key

`devon-approve-decide` is the exception that will bite. Approval emails carry
an absolute callback URL, built at send time and stored in the
`approval_queue.callback_url` column. Emails already sent point at Cloud
permanently. Keep the Cloud instance reachable until every outstanding
approval link has been used or has expired.

A second point on `devon-capture`: this vault entry was wrong until today. It
recorded the lane as unauthenticated, on a ruling that ChatGPT and Grok cannot
attach custom headers. The live workflow has enforced `x-devon-key` since
2026-08-23. Whatever posts to that lane today is already sending the header,
so find out what it is before you assume a poster needs a shim.

Note also that `DEVON Capture Hook` (Cbd24ptTPWch3aZO) is a separate, inactive
workflow that also owns a capture webhook path. `n8n_migrate.py import`
refuses on webhook-path collision, so if these two share a path the tool will
stop and say so. That is the tool working, not a fault.

## 5. Double execution, the thing that actually costs you

32 of the 58 workflows were active on Cloud when this was written. A
reconcile on 2026-09-01 found 31 active, with both the Heartbeat and the
Error Alarm inactive and nothing recording who switched either off or why.
The arithmetic does not let both deactivations postdate the 32 on their
own: either one of the two was already off when this document counted, or
both went off later and some third workflow was switched on, and every
version of that story contains at least one unrecorded switch. Both were
reactivated on 2026-09-01 on Tee's ruling, each the same version
republished unchanged and read back active, so the Heartbeat's timer line
below is current again and the live active count stands at 33.
Thirteen ran on a timer or a poll rather than waiting to be called:

    DEVON Capture Nudge              daily
    DEVON Pipeline Watchdog          every 4 hours
    DEVON Precedence Guard           daily
    DEVON Soul Layer Write-Back      poll
    DEVON _To Delete Auto-Purge      schedule
    DEVON Build 12 Ledger Feeder     poll
    DEVON Duplicate Sweep            daily
    DEVON Heartbeat                  every 6 hours
    DEVON Ledger Janitor             daily 02:30 UTC
    DEVON Monthly Credential Review  monthly
    DEVON Notion Buffer Drain        schedule
    DEVON Soul Committer             poll
    DEVON Weekly Table Backup        weekly, Sun 03:10 UTC

Timer-driven workflows need nobody to call them. The moment the same one is
active on both instances it runs twice per interval, against the same Drive,
the same Airtable, the same Pinecone index. The Soul Committer is the sole
writer to `devon-soul` and commits one record per approved request. Two of
them means one proposal producing two commits, which breaks the one proposal
per intent rule outright. The Ledger Janitor cancels jobs. Two of them means
two cancellations of the same job. Duplicate Sweep and _To Delete Auto-Purge
both move files.

`n8n_migrate.py import` always imports inactive, for exactly this reason. That
default is a safety property. Do not override it to save clicks.

## Order of work

1. Register the VPS OAuth redirect URI in Google Cloud, per the callback
   section below. Nothing else proceeds until this is done, and it is the only
   step that waits on a third party.
2. Create all 28 credentials on the VPS. Record the new id beside the old one.
3. Create all 9 data tables. `approval_queue` empty, always.
4. Let Cloud drain to terminal states, per the ruling above. Check the ledger
   for non-terminal rows and wait them out rather than copying them.
5. `n8n_migrate.py export` from Cloud, then `inspect` the export. Inspect
   reports credentials by id, webhook paths, data tables and active states.
   Read that report against this document before importing anything.
6. `n8n_migrate.py import` to the VPS. Everything lands inactive.
7. Repoint, per workflow: credential ids, data table ids, Execute Workflow
   targets, error workflow settings.
8. Activate one lane at a time, and deactivate its Cloud twin in the same
   sitting. Never leave a timer-driven workflow active on both.
9. Repoint external posters to the VPS webhook host, lane by lane.
10. Keep Cloud reachable until outstanding approval links have expired.

## What this document does not tell you

It is built from workflow metadata: names, descriptions, active states,
trigger counts, webhook paths and auth, plus the credential and data table
inventories. It is not built from node-level inspection of all 58 workflows.
So the credential-to-node and table-to-node mappings, and the exact set of
Execute Workflow and errorWorkflow references, are named here as classes of
problem rather than enumerated. `n8n_migrate.py inspect` enumerates them from
a real export. Run it before you trust any count in this file.

The migration itself has not been attempted. Direct egress to both
`thequietoperator.app.n8n.cloud` and `n8n.editforge.online` is blocked from
the agent sandbox, so the tool runs on your machine, not here.

## The OAuth callback URL

n8n on the VPS runs behind Traefik, which terminates TLS on 443 and proxies to
the n8n container on 127.0.0.1:5678. The n8n OAuth callback path is fixed, so
the redirect URI is the host plus that path:

    https://n8n.editforge.online/rest/oauth2-credential/callback

Register that exact string in the Google Cloud project that owns the OAuth
client, under APIs and Services, Credentials, the OAuth 2.0 Client ID, then
Authorised redirect URIs. Google matches redirect URIs literally: scheme, host,
path and the absence of a trailing slash all have to agree, and a mismatch
fails at consent time with redirect_uri_mismatch rather than at save time.

Two things to check rather than assume.

First, whether the three Google credentials share one OAuth client. Open each
credential in n8n and compare the Client ID. One shared client means one
redirect URI covers all three. Three different clients means three separate
Google Cloud entries, possibly in three different projects.

Second, the host itself. The URL above is derived from DNS (n8n.editforge.online
resolves to 2.25.140.44, which is srv1936193) and from the Traefik container
publishing 443. It has not been fetched, because this sandbox has no egress to
that host. The authoritative value is printed by n8n itself: open any OAuth2
credential on the VPS and copy the OAuth Redirect URL it displays. If that
string differs from the one above, n8n is right and this document is wrong.
