# SYS_OPS: the alert lane blackout, and the estate map it forced

Date: 2026-09-05
Status: FINAL for this arc. Closes the arc that began with "install everything
Claude Code" and ended with DEVON able to speak again.
Supersedes: nothing. Extends SYS_OPS_n8n-cloud-to-vps-migration_v1_2026-08-31.md
with what the migration looks like six days in.
Related: Context Pill v22 (Drive 1lAHJiEHK6wz9yvAAENbuTU-6NKPfvGNO), Notion
Thread Log 3d268ff5-0db6-8105-96f7-dc992f8b7850, PR #134 (merged 7b73868).

Every claim below is labelled. VERIFIED means read from a live system with the
result shown. RULED means Tee decided it. UNVERIFIED means believed and not
measured.

---

## 1. What actually happened

DEVON stopped writing home on 2026-08-27 and nobody noticed until 2026-09-05,
when a human asked whether he was operationally green. Nine days and eight
hours. The cause was not one failure. It was two, back to back, which is why it
read as one continuous silence.

**Stage one, 2026-08-29 through 2026-08-31. VERIFIED by execution 4700.**

    Execution limit reached. Consider upgrading your plan

n8n Cloud quota exhaustion. The run died at the schedule trigger before any
node fired. This did not just stop the Heartbeat. It stopped all 33 active
workflows on the instance: the Build 02 ledger, the Build 06 event bus, the
approval queue, all four routers, the capture lane, the six TSWS workflows.
Every one of them, silently, for three days.

**Stage two, from 2026-09-01. VERIFIED by execution 5552.**

Quota reset on the billing boundary. Runs completed their four table reads and
died at the send instead, because Gmail OAuth credential vsTKuAilHmpYCc5L had
gone invalid on its own. No password change, no revocation anyone performed.

The handover between the two stages was seamless enough that the newest
execution told a completely different story from the oldest retained one. The
lesson generalises: the newest failure is not the only failure.

## 2. Why nothing caught it

The Heartbeat is the organ whose entire job is noticing. It could not report
its own failure because the thing it uses to report is the thing that broke.

The Error Alarm could not help either. It is wired as the shared error workflow
for the estate, so it fired faithfully on every Heartbeat crash, and then failed
at exactly the same send. Ten of the fourteen errored executions since
2026-09-04 are that cascade: Heartbeat fails, Error Alarm wakes, Error Alarm
fails.

**The one thing that did work was the design that anticipated this.**
`Record Beat` runs parallel to the email lane rather than after it, so the beat
row commits whether or not the send succeeds. The heartbeat log kept a complete,
honest record through all nine days. It was the only witness, and it was the
witness precisely because it does not depend on the alerting channel.

That is the durable rule this arc produced:

> The witness must not depend on the channel it reports through.

## 3. What was changed

**Heartbeat dRgTNLod2s8BAcPg, node Send Pulse.** Gmail node replaced with
`n8n-nodes-base.emailSend` v2.1 on SMTP credential mu7nJRSpkAfkzLdF.
executeOnce, retryOnFail, 3 tries and 5s backoff all preserved.

**Error Alarm XDQXwgFkUhYxoEjG, node Alert Tee.** Same conversion. executeOnce
preserved, no retry, as before.

**Approval Queue syRVj0G47mA1b0Xn, node Email Tee.** Same conversion. This one
matters most and was found last. `Store Pending` runs BEFORE `Email Tee`, so
from roughly 2026-09-01 every high impact request was written to the queue as
pending and the approve and reject links never reached Tee. Requests expire in
72 hours and no decision is a rejection, so those requests died unseen. The gate
did not fail open. It failed silent, which for a governance gate is its own
category of bad.

Credential swap only on all three. No change to the two tap confirmation, the
fail closed sentinel, the node ordering, or the unsigned shift id minting.

**Sticky notes updated on all three** to record what happened and why, per the
house convention that a sticky note which lies is worse than none.

**Repo, merged as 7b73868 via PR #134.** The n8n house conventions reference
named the dead Gmail credential as the standard for outbound mail. Corrected.
`services/devon/vault.py` was NOT changed: it names no mail credential, and its
N8N_HOST is still correct because cloud is still the live instance.
`scripts/estate_reconcile.py` had no references at all.

## 4. Receipts

Not status flags. The actual SMTP transcripts.

**Heartbeat, execution 5600, 2026-09-05T12:23Z:**

    accepted:  ["tdveal74@gmail.com"]
    rejected:  []
    response:  250 2.0.0 OK  1788611002 ... - gsmtp
    messageId: <37fe31db-e60b-549f-0e5e-82bdcddc1995@gmail.com>

`Record Beat` wrote row 35 with emailed "no" at 12:23:21.686, `Send Pulse`
succeeded in 982ms, `Mark Emailed` flipped the same row to "yes" at
12:23:22.815. The receipt chain worked as designed.

That execution also carried the number that measures the outage:
`lastEmailed: 2026-08-27T04:00:24.837Z`.

**Approval Queue, execution 5602, 2026-09-05T12:41Z:**

    Email Tee       success, 916ms
    accepted:       ["tdveal74@gmail.com"]
    response:       250 2.0.0 OK  1788612096 ... - gsmtp
    Confirm Queued  success

`Confirm Queued` is the tell. It never ran once during the blackout, because
`Email Tee` threw before reaching it. A real pending row was written into
approval_queue to obtain this proof, titled so it is unmistakably a test. It
expires in 72 hours and no decision is a rejection, which is the correct
outcome.

## 5. The estate map, corrected

Every prior record spoke of one VPS. There are two. VERIFIED by direct read.

**srv1936193, public IP 2.25.140.44.** The n8n box. Six containers, all restart
policy `always`:

| Container | Published |
|---|---|
| n8n-traefik-1 | 0.0.0.0:80, 0.0.0.0:443 |
| n8n-n8n-1 | 127.0.0.1:5678 only |
| n8n-postgres-1 | none, container internal |
| n8n-searxng-1 | none |
| n8n-sandbox-api-1 | none |
| n8n-sandbox-runner-1-1 | none |

n8n on loopback behind traefik is exactly what the migration doc specified.
Postgres is not internet reachable. Tee SSHes here as user `tee`, not root.

**srv1936199.** The EditForge box. editforge web, provider, edge and worker plus
two 1backend containers, all `unless-stopped`.

Both boxes are fully patched as of 2026-09-05 06:09 and 06:47 UTC. Both were
running a kernel that had since been superseded and auto removed, so both
needed a reboot. **Both were rebooted on 2026-09-05 and BOTH were verified by
direct read**, srv1936193 at 14:13:49 UTC and srv1936199 at 14:22:49 UTC. Both
proved reboot safe in practice, not just in theory. cloud-init is held back on
purpose on srv1936193; that is the "1 update could not be installed
automatically" in the MOTD, and it is not a failure.

**Google Cloud project 828264336169 holds three OAuth clients, not one:** Gmail
and Drive created 2026-08-30, n8n Youtube Client created 2026-06-30. Each
carries only the VPS callback. UNRESOLVED: whether cloud's Gmail credential
pointed at one of these or at a different or deleted client. Do not delete an
old client secret until that is known.

## 6. Port 22, closed and then restored

RULED twice on the same day, and the reversal is the interesting part.

Tee ruled "close 22" and both rules on Hostinger firewall 355595 were deleted.
Reading Context Pill v19 to write v20 then surfaced its section B2: the
EditForge deploy dry run "succeeded after TCP 22 was accepted on the Hostinger
firewall". The rule had been created 2026-09-03 at 18:48, thirty one minutes
before v19 was filed. Tee ruled "restore" on that evidence, and TCP 22 from any
is back as rule 1297918.

Tee then read the workflow and settled it properly. VERIFIED, not inferred:
`deploy-hostinger.yml` loads EDITFORGE_VPS_SSH_KEY into an ssh-agent, scps
`scripts/hostinger-tag-swap.sh`, then ssh es twice. Every connection uses
EDITFORGE_VPS_PORT, which defaults to 22. The GHCR image pull is separate and
does not replace the SSH transport.

Because that port is a secret rather than a constant, SSH can still move off 22
without breaking the deploy. The order matters: add the new port to the firewall
and sync, add the sshd Port and confirm a login on it while 22 is still open,
set EDITFORGE_VPS_PORT and run the deploy dry run to green, and only then remove
the 22 rule.

A high port is scanner noise reduction, not security. Key only auth plus
fail2ban is the real hardening.

**The rule this produced:** a port is not a local decision when a pipeline
depends on it. The reason that rule existed lived in the Context Pill, not in
the firewall, and the firewall's own name pointed the right way while its
contents did not.

## 7. The scheduled layer is worse than the mail lane

Found while closing this arc, and not yet resolved.

The claude.ai Routine layer is broadly failing. Of six Routines with a recorded
run, five are FAILED or ABANDONED and one succeeds.

| Routine | Schedule | Last run |
|---|---|---|
| TSWS / Devon thread log drift check | Mon, Thu 14:00 | SUCCEEDED 09-03 |
| DEVON weekly sweep | Sun 13:00 | FAILED 08-30 |
| Weekly data-broker recheck | Mon 13:00 | FAILED 08-31 |
| DEVON Mirror Read | 1st of month 11:00 | ABANDONED 09-01 |
| Devon Morning Briefing | weekdays 12:00 | FAILED 09-04 |
| Supreme Trader Watchlist | weekdays 12:00 | FAILED 09-04 |

Separately, `DEVON Daily Reflection (Build 13)` was not failing at all. It was
**switched off**, user paused, with no ended_reason and no suspension_reason. It
last fired 2026-09-01 at 11:39Z and was disabled within about a day, which is
the same window the Gmail credential died in. Re-enabled 2026-09-05; first fire
2026-09-06 11:35Z.

UNVERIFIED and worth checking at that first fire: the Reflection Routine binds
to a specific prior session and its prompt opens with "full context is in this
conversation". If that session is gone, enabling it is not sufficient.

A diagnostic run of Devon Morning Briefing was fired manually on 2026-09-05 to
capture the actual error. VERIFIED, session cse_01TJvcVK5z4tZkvR9jP2MG7s:

    session_status  SESSION_STATUS_IDLE
    status_bucket   REVIEW_READY
    rate_limit      allowed
    model           claude-fable-5, effort_level max
    tokens          224,862 used of 1,000,000; 29,156 output
    cost            $8.072114
    12:57:49Z to 13:04:50Z

**It succeeded.** The prompt works, the connectors resolve, the output is
readable and sitting unread. So the failure is not in the Routine's definition.
It is in the scheduled run environment, and the standing hypothesis, that 29 MCP
connectors for a briefing which reads two databases is what breaks it, is
weaker now, not stronger. That was said in advance of the run rather than after
it.

The run produced a second finding nobody was looking for. One morning briefing
costs $8.07 at effort_level max. Weekdays, that is roughly $170 a month for a
scheduled read of Notion and Airtable. Whether that is worth paying is Tee's
call, but it should be a decision rather than an accident.

The better hypothesis to test next, UNVERIFIED: Devon Morning Briefing and
Supreme Trader Watchlist both fire weekdays at 12:00 and both failed on the same
day, 09-04. Two consecutive max effort sessions in one five hour window is a
plausible way to exhaust it. The two Routines that did not collide on a slot,
the drift check on Mon and Thu, are also the ones that succeed.

## 8. Still open

1. CLOSED 2026-09-05. Both VPSs were rebooted and BOTH were VERIFIED by direct
   read, so this item is measured rather than reported.

   srv1936193 at 14:13:49 UTC: uptime 25 minutes, all six containers back on
   their own restart policy. traefik, n8n, postgres, searxng and sandbox-api
   at 25 minutes; sandbox-runner at 22, which is dependency order behind
   sandbox-api, not a fault.

   srv1936199 at 14:22:49 UTC: uptime 34 minutes, load 0.01 0.05 0.02, all six
   containers back. editforge edge, web, worker and provider plus the two
   1backend containers. That also re-confirms the container inventory in
   section 5, which had been recorded from a single read on 2026-09-05 and had
   never been seen survive a restart.

   The restart policies did their job on both boxes with no hand starting, which
   is the first time that has been demonstrated rather than assumed.

   NEW, found while reading the output: **health is only declared on half the
   estate.** srv1936193 reports a health status on postgres and sandbox-api
   only; srv1936199 on web, worker and provider only. The other six containers,
   traefik and n8n itself among them, declare no healthcheck at all, so "Up" is
   the entire signal. A container that is running and not serving is
   indistinguishable from a healthy one, which is the same shape as the failure
   this whole document is about: the Heartbeat was "running" for nine days and
   what it was not doing was arriving. Not fixed here; it is a compose file
   change on each box and Tee's call.
2. The cloud to VPS cutover is on a clock. Burn rate estimated at roughly 120
   executions a day from execution id deltas, about 3,600 a month. If the plan
   caps at 2,500 the wall returns around 2026-09-21. ESTIMATE, not a
   measurement. Read the real cap on n8n's usage page.
3. The n8n MCP connector still points at cloud. Repointing is an account side
   change no agent can make, and it needs an API key minted on the VPS first.
4. Other cloud workflows still carry the dead Gmail credential. Each is a silent
   failure until moved. The Weekly Table Backup is a known one.
5. Whether cloud's Gmail credential pointed at the 2026-08-30 client or a
   deleted one.
6. Five failing Routines. The diagnostic run cleared the prompt and the
   connectors, so the cause is in the scheduled environment. Next test is the
   12:00 weekday collision between Devon Morning Briefing and Supreme Trader
   Watchlist.
7. Whether $8.07 per scheduled briefing at effort_level max is a price worth
   paying, or whether these Routines should drop to a lower effort level.

## 9. Corrections logged against Claude in this arc

Recorded because the pattern matters more than the individual errors.

- "Leave the existing cloud callback in place" was an assumption stated as fact.
  There was never a cloud callback on those clients.
- "SMTP is the fast path" was wrong. That credential was also dead. It was
  labelled untested, and running it is what found out.
- Calling the OAuth consent screen question a "landmine" ranked an unverified
  hypothesis above a measured, known broken alert lane.
- "Updates are already done" was true of srv1936199 and said while the pending
  updates were on srv1936193.
- The first SSH hardening script checked `$HOME`, which resolves to `/root`
  under sudo, and would have missed `/home/tee/.ssh/authorized_keys`.
- "vault.py and the conventions doc both disagree with the estate" was carried
  into a handover, a Context Pill and three check in messages. Only the
  conventions doc was wrong.
- Three Context Pill versions were filed in twenty five minutes because each
  went stale while the next was being written.

The through line: reading found none of this. Running it found all of it.
