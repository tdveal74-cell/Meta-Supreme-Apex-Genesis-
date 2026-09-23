# The mail channel came back, and the receipt is not the dialog

The SMTP credential died on 2026-09-20 and took every alerting path DEVON has
with it. Tee repaired it on 2026-09-22 and said so in session. This doc is the
check that was run before that was written down as a fact, and the reason the
obvious check would have been the wrong one.

## What was claimed and what was measured

Tee's word was "SMTP credential is fixed". A check was available and cheap, so
it was run rather than recorded on his say-so, which is the first law applied to
the one source that is normally trusted without it.

`DEVON - Heartbeat (Build 13)`, workflow `EEDrp2jLlw2Ssd5b`, execution 798, the
scheduled 22:00:15Z beat, errored after 10.9 seconds. That is the tenth
consecutive failure in the same shape. Execution 805 at 22:25:32Z, run manually,
returned `success` in 0.9 seconds.

A green execution proves nothing here on its own, and this is the part worth
keeping. `Only If Email` returns `[]` when `send_email` is false, so a quiet
beat skips `Send Pulse` entirely and still finishes green: execution 601 on
2026-09-20T10:00:15Z read `success` in 0.165 seconds having sent nothing. Status
alone cannot separate a delivered pulse from a skipped one.

The receipt is the beat row. `devon_heartbeat_log` row 122 carries `beat_at
2026-09-22T22:25:32.599Z` and `emailed: yes`, flipped at 22:25:33.426Z.
`Mark Emailed` hangs off the success output of `Send Pulse` and nowhere else, so
that flip is the send completing. Row 121, the 22:00:15Z beat twenty five
minutes earlier, still reads `emailed: no`. Same workflow, unedited since
2026-09-17T12:30:29Z, same credential id on the node. The credential is the only
variable between the two rows.

That design was written for exactly this. The Heartbeat's own sticky note calls
it receipts, not claims: the row is inserted with `emailed: no` and only a
successful send flips it, so a failed send leaves its alerts NEW and retries on
the next beat. It was built so a mail outage could never read as healthy, and it
is now also the instrument that proves recovery.

## What came back with it

Tee repaired `AgSGuaA2pnZsrZcJ` in place rather than creating a replacement, and
it is still the only credential of type `smtp` on the instance. That matters
more than the Heartbeat itself: all twenty `emailSend` nodes across sixteen
workflows come back on the one fix, rather than one node being rewired while
nineteen stayed dead. `DEVON - Weekly Table Backup` has a sink again instead of
building four CSVs and discarding them, and `OS 29 - Platform Policy Sensor`,
the compliance lane, has its only channel back.

## One number moved under the file

`CLAUDE.md` recorded seven consecutive Heartbeat failures from 2026-09-20T16:00
to 2026-09-22T04:00, accurate when it was written that morning. Three more
landed at 10:00, 16:00 and 22:00, so the outage ran ten runs and ended at
22:25:33Z. A session reading the old line tomorrow would re-diagnose an outage
that is closed. Corrected in place, with the original count kept in the sentence
so the correction is visible rather than silent.

## What this does not prove

Acceptance by an SMTP server is not delivery, so this section first said the
inbox was unconfirmed and left the look to Tee. He asked what to look for, which
made it cheaper to run the check than to describe it. The Gmail thread is there:
subject "DEVON Pulse: all quiet", from and to tdveal74@gmail.com, dated
2026-09-22T22:25:32Z, carrying the labels SENT and INBOX. Its first body line
reads `DEVON PULSE 2026-09-22T22:25:32.599Z`, matching row 122's `beat_at` to
the millisecond, so it is that send and not another. Exactly one such thread
exists in the two day window, which is the right count, because every send from
2026-09-20T16:00 until this one failed.

So the mail path is proven end to end, composed through delivered. What is still
unproven is the SCHEDULE: execution 805 was started by hand, and the unattended
proof is the 2026-09-23T04:00:15Z beat.

Google Drive `NW3vR6nNcMoUkJyJ` is unverified and was not guessed at. The
Precedence Guard's last run, 2026-09-22T11:00:55Z, errored, but that lane
swallows its Drive failure and dies at the send, so `status: error` cannot
separate a dead credential from a live one. `DEVON - _To Delete Auto-Purge`
retains exactly one execution, the 2026-09-20T14:00:56Z clean read that brackets
the death. Nothing readable from here settles it. With mail alive the Guard's
2026-09-23T11:00:55Z run is the first that delivers its own verdict in words,
either a clean duplicate check or the line saying it could not read `_Devon
Core` and this is NOT a clean result.

The Cerebras payment refusal is untouched by any of this and still stops the
content pipeline.

## The merge

`PR #275` merged on Tee's explicit authorization as `67d15ea`, green on all six
checks on `2a5e25a`. Its body ends by saying both credentials are still dead,
true when written and half wrong by merge time; the merge commit records the
recovery rather than editing the body to look prescient.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_the-mail-channel-came-back-and-the-receipt-is-not-the-dialog_v1_2026-09-22-2230.md
DATE: 2026-09-22
DECISIONS: Tee reported the SMTP credential fixed and authorized the merge of PR #275 with "Merge now, record the recovery next". The report was treated as a claim and verified against the lane's own receipt before being written down.
FINDINGS: SMTP AgSGuaA2pnZsrZcJ is live again as of 2026-09-22T22:25:33.426Z, proven by devon_heartbeat_log row 122 flipping emailed to yes off the success output of Send Pulse, with row 121 twenty five minutes earlier still reading no on the same unedited workflow. The credential was repaired in place and is still the only smtp credential on the instance, so all twenty emailSend nodes across sixteen workflows recovered on one fix. A green execution could not have carried this: Only If Email returns an empty array on a quiet beat, and execution 601 read success in 0.165s having sent nothing. The outage ran ten consecutive runs, not the seven recorded that morning.
OPEN: SUPERSEDED by SYS_OPS_two-credentials-closed-and-the-two-claims-i-got-wrong_v1_2026-09-23-2220.md. This key said the scheduled lane was unproven until the 2026-09-23T04:00:15Z beat, which was wrong twice: that beat was inside the 22h send window and could not have sent, and the real proof is execution 890 at 2026-09-23T22:00:15Z, mode trigger, row 128 emailed yes, delivered. The inbox is confirmed: the Gmail thread dated 2026-09-22T22:25:32Z carries INBOX and its first body line matches row 122's beat_at exactly, so acceptance and delivery are both established. Google Drive NW3vR6nNcMoUkJyJ is unverified and cannot be settled from an execution list, because the Precedence Guard swallows its Drive failure and dies at the send. The Cerebras payment refusal still stops the content pipeline.
STATUS: Mail channel recovered and verified. CLAUDE.md corrected on both the failure count and the recovery. PR #275 merged as 67d15ea on Tee's explicit authorization.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
