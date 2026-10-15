# Genjutsu on srv1936199: webhook, bucket and keys

Status record for the second half of the Genjutsu arc, 2026-10-15. It follows
`SYS_OPS_tsws-editable-repair-workflows_v1_2026-10-14-2109.md`, which covers the
safeguards and the install. This doc covers what was wired after the install
and what still stands between the app and a first real job.

## Where the app stands

The app runs as the Docker project `genjutsu` on 127.0.0.1:3500 of srv1936199,
built from upstream commit `40fd661` plus the safeguards overlay. Tee ran the
install himself through Termius. He opened the UI on his phone through a
Termius port forward to `http://127.0.0.1:3500` and the Genjutsu page loaded.

## The webhook

Enhancor will not accept a job without a callback URL, though the app polls
Enhancor for the result itself. A one node n8n workflow answers that URL.

- Workflow `H8IdVxtzGd9ZJ3hU`, `Genjutsu - Enhancor Callback Sink`, in Tee's
  personal project. One Webhook node, POST, path `genjutsu-callback`, answers
  at once with no body. No credential.
- `saveDataSuccessExecution`, `saveDataErrorExecution` and
  `saveManualExecutions` are all off, so a callback leaves nothing stored.
- Published on Tee's card answer, 2026-10-15. Read back after publishing:
  `active` true, `versionId` and `activeVersionId` both
  `008999c9-f882-4f85-a2cb-f57158145600`.
- A live POST from the build environment to
  `https://n8n.editforge.online/webhook/genjutsu-callback` returned HTTP 200.
- The workflow description still reads "DRAFT until Tee publishes". It was
  left alone, because editing it would create a new unpublished draft on top
  of the live version.
- It is a public URL with no login. Anyone who finds it can POST to it, and
  all they get is a 200 and an execution that is not saved.

## The bucket

The private uploader now has a real bucket behind it. Until this step it had
only been tested against a stand-in client.

- Cloudflare R2 bucket `genjutsu-media`, private, with an Account API token
  limited to Object Read and Write on that bucket alone. Tee made both in the
  dashboard and saved the keys to his password manager. No key passed through
  a session.
- Tee wrote `MEDIA_BUCKET`, `MEDIA_ENDPOINT`, `MEDIA_REGION=auto`,
  `ENHANCOR_WEBHOOK_URL`, `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` into
  `/opt/genjutsu/src/.env` on the VPS and recreated the container.
- Upload test, run by Tee in the container: it printed
  `PASS 39d4223d64b2dbd65ed37960a2d54/tmphces_r4n.txt`, the tail of the object
  path. That proves the key, the bucket and the upload.
- The upload alone did not prove the signed link opens, because the link is
  computed on the VPS without asking Cloudflare. A second check, also run by
  Tee in the container on 2026-10-15, uploaded a fresh file, fetched its
  signed link and compared the bytes. It printed `PASS link opens 200 True`:
  Cloudflare served the object over the signed GET and the bytes matched what
  was written. That proves the link a provider would be handed actually
  opens, from the VPS. It was not fetched from outside the VPS.
- Each test leaves one small text file under `genjutsu/` in the bucket. The
  two recorded here left two; any other runs were not counted.

## Keys

`REPLICATE_API_TOKEN` and `ENHANCOR_API_KEY` are both unset. Both are paid
services and the original brief ruled out paid generation, so adding either
is a new purchase decision for Tee. With no keys, every billed step refuses
before anything is sent, on top of the grant gate.

## What did not work

- The first install paste lost its line breaks on iOS and left the shell in an
  unfinished heredoc. Nothing ran. The script was delivered again as a file and
  uploaded over Termius SFTP, and that run worked.
- The install script's last check printed `FAIL grant did not refuse`. Run by
  hand, the same command printed the refusal and `exit=1`, and no grant file
  existed. The check is flawed, not the gate. The cause is believed to be
  `grep -q` under `set -o pipefail`, and that is not reproduced.
- Fetching `developers.cloudflare.com/agent-setup/prompt.md` was refused by
  this session's network policy, so nothing from it was run.

## Open

- The Replicate and Enhancor keys, which are a purchase decision.
- Whether to make the grant folder root owned, which is the only setup that
  holds if an agent ever runs as the app user on that box.
- The false FAIL in the install script's last check, if the script is ever
  run again.
- The TSWS repair arc itself stays open. No Episode 1 shot has been repaired,
  because the media has never reached a machine that can run the scripts.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_genjutsu-vps-wiring_v1_2026-10-15-0436.md
DATE: 2026-10-15
DECISIONS: Tee ran the install through Termius, uploaded the TSWS zip to Drive himself, ruled on a card to publish webhook workflow H8IdVxtzGd9ZJ3hU, made the R2 bucket and its scoped token, and wrote the bucket and webhook values into the VPS .env himself.
FINDINGS: The webhook is live and read back with versionId equal to activeVersionId and a POST returning 200. A real upload to genjutsu-media passed with Tee's keys, and its signed link opened with HTTP 200 and matching bytes. The install's grant check false failed while the gate itself refused by hand. An iOS paste of the install script lost its line breaks and ran nothing.
OPEN: Replicate and Enhancor keys unset by choice; root owned grant folder undecided; install script false FAIL unfixed; TSWS Episode 1 repairs not started.
STATUS: DRAFT. App installed with no paid keys. Nothing generated, nothing billed.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
