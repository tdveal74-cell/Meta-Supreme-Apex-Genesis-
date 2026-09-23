# Two credentials closed, and the two claims I got wrong getting there

Both dead credentials are repaired and proven. This doc supersedes
`SYS_OPS_the-mail-channel-came-back-and-the-receipt-is-not-the-dialog_v1_2026-09-22-2230.md`,
whose OPEN key still says the scheduled lane is unproven until the 04:00Z beat.
That was wrong twice over: the 04:00Z beat was never the proof, and the real one
has landed.

## SMTP AgSGuaA2pnZsrZcJ, proven end to end unattended

Tee repaired it in place at about 22:25Z on 2026-09-22. It is still the only
credential of type `smtp` on the instance, so all twenty `emailSend` nodes
across sixteen workflows came back on the one fix.

The proof took three steps, each answering a question the one before it left.

The send path, 2026-09-22T22:25:32Z. Execution 805, run by hand.
`devon_heartbeat_log` row 122 flipped `emailed` to `yes` at 22:25:33.426Z, and
`Mark Emailed` runs only off the success output of `Send Pulse`. Row 121, the
22:00:15Z beat twenty five minutes earlier, still reads `no` on the same
workflow, unedited, same credential id.

Delivery, not just acceptance. The Gmail thread dated 2026-09-22T22:25:32Z
carries `SENT` and `INBOX`, and its first body line reads
`DEVON PULSE 2026-09-22T22:25:32.599Z`, matching row 122 to the millisecond.

The schedule, 2026-09-23T22:00:15Z. Execution 890, `mode: trigger`, success in
2.022s against 0.149s and 0.160s for the two quiet beats before it. Row 128
reads `emailed: yes`, flipped at 22:00:17.062Z, and the email is in the inbox
with the same millisecond match. Nobody touched it.

## Google Drive NW3vR6nNcMoUkJyJ, alive

Settled 2026-09-23T11:00:55Z by `DEVON Precedence Guard` execution 855,
`mode: trigger`, success in 3.136s against 0.52s and 0.98s on the two dead days.

It could not be settled from an execution list, which is why it waited: that
lane swallows its Drive failure and dies at the send, so `status: error` cannot
separate a dead credential from a live one. With mail alive the Guard finally
delivered its own verdict, and the email reads `Scanned 188 files in _Devon
Core` with real file ids and created timestamps. A swallowed failure cannot
produce that.

The eighteen Drive nodes across six workflows are back, including the two that
would have written a false record, both repaired on 2026-09-22 before the
credential returned.

## The two claims I got wrong

Both were filed into project memory and both are corrected there, in the open.

I predicted the 04:00Z beat would send, from `lastEmailed` at 2026-09-19T16:00Z.
My own manual run six hours earlier had already moved it to 2026-09-22T22:25Z.
Never predict from a number your own action changed.

I then filed that the first unattended send was pushed to the 22:00Z beat. True
of the Heartbeat, false of the estate, and committed hours after this repository
says count from the estate, not from the lane. One Gmail search: estate mail
resumed at 2026-09-22T23:35:54Z, seventy minutes after the repair, and seven
messages were delivered before the Heartbeat's own window opened. When a claim
is about the whole channel, read the whole channel.

DEVON caught the second one before I did. Its reflection at 2026-09-23T11:45Z
reads "A correction to my own last note. I wrote that the mail channel is alive,
and it is, but what proved it was a MANUAL run at 22:25Z. That run set
lastEmailed to itself and the send clock is 22h, so beats 124 and 125 both read
emailed no and neither is a relapse. The first unattended send is tonight's
22:00Z beat." That is the instrument reasoning correctly about its own blind
spot, six hours ahead of the session watching it.

## What is still open, and none of it is mine

Cerebras is still refusing. `TQO FINAL V5` took `payment_required` at
2026-09-23T10:20:21Z and the error handler delivered the fault, which is the
loud handler working as ruled on 2026-09-22.

A platform policy change is unjudged. `OS 29 - Platform Policy Sensor` detected
a change on Meta's Content Monetization Policies at 2026-09-23T10:00:27Z and
could not assess it, because the model returned an empty body. The lane found
the change and nobody has read it.

The Guard surfaced two items in `_Devon Core`: one byte-identical duplicate
pair, both named `SYS_LOG_ruling-build01-closure_2026-08-23.md`, and one
unversioned canon file, `CONTEXT-PILL_2026-09-22-2220.md`.

The learning lane has had no new job since 2026-09-16, seven days. DEVON has
raised this in two consecutive reflections and says plainly that its four tables
cannot tell it whether no jobs arrived because none were asked.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_two-credentials-closed-and-the-two-claims-i-got-wrong_v1_2026-09-23-2220.md
DATE: 2026-09-23
DECISIONS: Tee repaired the SMTP credential and reconnected Google Drive, and authorized five merges across this arc: the estate counts and false-write repairs, the mail recovery, the inbox correction, the rate limit rule, and the Drive closure with its correction. He ruled the rate limit lesson worth filing to project memory, and ruled this close-out doc over a one line edit to the superseded one.
FINDINGS: SMTP AgSGuaA2pnZsrZcJ is proven composed through delivered and unattended, by execution 890 at 2026-09-23T22:00:15Z with row 128 emailed yes and the message in the inbox. Google Drive NW3vR6nNcMoUkJyJ is alive, by Precedence Guard execution 855 reading 188 files. Two claims of mine were wrong and are corrected in CLAUDE.md in the open: a prediction from a number my own action had changed, and a lane fact written as an estate fact. DEVON's own reflection made the second correction six hours before I did.
OPEN: Cerebras still refusing, confirmed 2026-09-23T10:20:21Z. A Meta monetization policy change detected at 10:00:27Z is unassessed because the provider is down, and platform policy has no exception path. One duplicate pair and one unversioned canon file in _Devon Core. The learning lane has had no new job for seven days.
STATUS: Both credentials closed and proven. Five PRs merged on Tee's explicit authorization. This doc supersedes the 2026-09-22-2230 one, whose OPEN key is stale.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
