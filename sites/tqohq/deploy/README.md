# Putting the TQO home page on the VPS

`install-on-vps.sh` puts the TQO home page (the four files in `sites/tqohq/`
at commit `64f997279fb430be030c2146e917312266c1fe4f`) on the EditForge VPS,
behind the Caddy "edge" container that already serves every
`*.editforge.online` site there. You run it yourself, as root, by pasting one
line into Hostinger's VPS browser terminal. It works in four modes, and the
last line it prints always starts with `RESULT:`.

## The lines to paste

Each line downloads the installer at a fixed commit, checks its fingerprint,
runs it, and deletes the download again. Paste the whole line, press return,
and read the last line.

**Stage** (the test address only):

```
f=$(mktemp) && if curl -fsSL -o "$f" https://raw.githubusercontent.com/tdveal74-cell/Meta-Supreme-Apex-Genesis-/SCRIPT_COMMIT/sites/tqohq/deploy/install-on-vps.sh && echo "SCRIPT_SHA256  $f" | sha256sum -c --quiet >/dev/null 2>&1; then bash "$f" stage; else echo "RESULT: NOT DONE, nothing on the box was changed, because the installer could not be downloaded from GitHub, or it did not match its pinned fingerprint."; fi; rm -f "$f"
```

**Live** (only after the DNS for tqohq.online and www.tqohq.online points at the VPS):

```
f=$(mktemp) && if curl -fsSL -o "$f" https://raw.githubusercontent.com/tdveal74-cell/Meta-Supreme-Apex-Genesis-/SCRIPT_COMMIT/sites/tqohq/deploy/install-on-vps.sh && echo "SCRIPT_SHA256  $f" | sha256sum -c --quiet >/dev/null 2>&1; then bash "$f" live; else echo "RESULT: NOT DONE, nothing on the box was changed, because the installer could not be downloaded from GitHub, or it did not match its pinned fingerprint."; fi; rm -f "$f"
```

**Rollback** (take it all back out):

```
f=$(mktemp) && if curl -fsSL -o "$f" https://raw.githubusercontent.com/tdveal74-cell/Meta-Supreme-Apex-Genesis-/SCRIPT_COMMIT/sites/tqohq/deploy/install-on-vps.sh && echo "SCRIPT_SHA256  $f" | sha256sum -c --quiet >/dev/null 2>&1; then bash "$f" rollback; else echo "RESULT: NOT DONE, nothing on the box was changed, because the installer could not be downloaded from GitHub, or it did not match its pinned fingerprint."; fi; rm -f "$f"
```

**Status** (changes nothing, just looks):

```
f=$(mktemp) && if curl -fsSL -o "$f" https://raw.githubusercontent.com/tdveal74-cell/Meta-Supreme-Apex-Genesis-/SCRIPT_COMMIT/sites/tqohq/deploy/install-on-vps.sh && echo "SCRIPT_SHA256  $f" | sha256sum -c --quiet >/dev/null 2>&1; then bash "$f" status; else echo "RESULT: NOT DONE, nothing on the box was changed, because the installer could not be downloaded from GitHub, or it did not match its pinned fingerprint."; fi; rm -f "$f"
```

Before the lines are handed to you, `SCRIPT_COMMIT` is replaced with the
commit that holds this script, and `SCRIPT_SHA256` with the sha256 of the
script at that commit. A line that still says either will refuse and change
nothing. The fingerprint check means that whatever GitHub answers, an error
page, an empty file or a different script, is never run: only the exact
script that was reviewed.

## The plan

1. The DNS record `tqohq-stage.editforge.online` points at the VPS.
2. You paste the **stage** line. The page goes up at
   https://tqohq-stage.editforge.online, marked so search engines skip it.
3. You check it on your iPhone.
4. On your go, the DNS for `tqohq.online` and `www.tqohq.online` moves to the
   VPS.
5. You paste the **live** line. The page goes up at https://tqohq.online,
   `www.tqohq.online` sends visitors there, and the stage address keeps
   working.

Keep the `tqohq-stage.editforge.online` DNS record after launch. The live
line serves the stage address too and checks its DNS like the others, so
without that record the live line refuses, and the page cannot be updated
until the record is back.

## What each mode does

**stage**. Checks the box first, then downloads the four site files, checks
each one's size and fingerprint against the ones pinned in the script, puts
them in the site folder, adds one block to the Caddyfile for
`tqohq-stage.editforge.online`, has Caddy check and reload it, and then makes
sure every other site on the box still answers. It refuses if tqohq.online is
already live, because stage would take it offline.

**live**. The same, but the block serves `tqohq.online`, sends
`www.tqohq.online` to it, and keeps the stage address. Before it changes
anything it looks up all three names and refuses unless they point at this
box, so Caddy is never asked for a certificate it cannot get.

**rollback**. Takes this script's block out of the Caddyfile, and puts the
site folder back the way it was before the last install (the previous copy if
there was one, otherwise no folder at all). It only ever moves or deletes a
folder this installer made; anything else is left where it is, and the RESULT
line says so. It checks the other sites the same way. If tqohq.online was
live, rolling back takes it off this box, and the RESULT line says its DNS has
to move back. Rolling back a second time removes whatever site files this
installer still has on the box.

**status**. Changes nothing. It says whether the block is there and for which
names, whether the site files are the pinned ones and who made them, and
whether each name serves the right page with a valid certificate.

Running stage or live a second time with nothing new to do changes nothing and
says so.

## Reading the RESULT line

| RESULT starts with | What happened | What to do |
|---|---|---|
| `RESULT: DONE` | It worked, and every other site still answers as before. | Open the address it names on your iPhone. |
| `RESULT: DONE ... still being issued` | It worked, but the security certificate for the new name is not ready yet. | Wait five minutes, then open the address. If Safari still warns, paste the status line. |
| `RESULT: DONE ... 9 of the 11 other sites` | It worked. The sites it names were not answering before it ran either. | Open the address. Send the line to Claude about the sites that were already down. |
| `RESULT: NOT DONE, nothing on the box was changed` | It stopped before touching anything. The reason is in the same line. | Nothing is broken. Fix the reason, or send the line to Claude. |
| `RESULT: FAILED, and the box was put back exactly as it was` | Something went wrong after it started changing things, and it undid all of it. | Nothing is broken. Send the whole screen to Claude before trying again. |
| `RESULT: FAILED, and putting the box back did not finish` | It could not undo everything. The line names what is left and where the Caddyfile backup is. | Do not run anything else. Send a screenshot of the whole screen to Claude. |
| `RESULT: Stage is installed and working` or `RESULT: Live is installed and working` | Status looked, and everything is right. | Nothing. |
| `RESULT: Stage is installed, but ... still being issued ... wait five minutes` | Status looked. The page is up, the certificate is not ready yet. | Wait five minutes and paste the status line again. |
| `RESULT: Stage is installed, but ... send this line to Claude` (or `Live is installed, but`) | Status found something wrong: a name not serving the page, or files that are not the pinned ones. | Send the line to Claude. Do not run stage or live again first. |
| `RESULT: Not installed: ... site files from an earlier run` | There is no block, but this installer's files are still in the folder. | Nothing is broken. The stage line installs it again; the rollback line clears the files. |
| `RESULT: Not installed, and a tqohq folder this installer did not make` | Someone else put a folder where the page goes. | Send the line to Claude. Stage and live will refuse until someone has looked. |
| `RESULT: Not installed by this script, but the Caddyfile serves` | Another block in the Caddyfile uses one of these names. | Send the line to Claude. |
| `RESULT: Nothing from this installer is on the box.` | Status looked, and there is nothing of this script's there. | Nothing. |
| `RESULT: Could not check` | Status could not look. | Send the line to Claude. |

**If the screen goes away before a RESULT line appears** (the phone locks, the
browser tab reloads, the connection drops): the script keeps going on its own
and finishes. Reconnect, wait a minute, and paste the **status** line, not the
stage or live line again. If it says another run is still going, wait another
minute and paste the status line again.

Reasons you might see in a NOT DONE line, and what they mean:

- **"points at ..., not at this box"**: the DNS has not moved yet, or has not
  spread yet. Wait a few minutes and paste the line again.
- **"also has an IPv6 (AAAA) record"**: the name has an IPv6 address that is
  not this box. That record has to be deleted in Hostinger's DNS.
- **"the Caddyfile on the box is already invalid"**: the box was broken before
  this script touched it. Send it to Claude; do not change anything.
- **"Caddy's check of the current Caddyfile failed without saying why"**:
  the check itself did not run, usually because a disk is full. The
  Caddyfile is not known to be wrong. Send it to Claude.
- **"there is not enough free disk space"**: the disk it names needs room
  cleared first. Send it to Claude.
- **"another run of this installer is still going"**: an earlier paste is
  still working (perhaps after the screen went away). Wait a minute and paste
  the status line.
- **"a folder ... is already on the box and this installer did not make it"**:
  something else is in the place the page goes, or someone edited the page's
  files by hand after the install. The installer will not replace or delete
  it. Send it to Claude.
- **"another site in the Caddyfile already serves /srv/static/tqohq"**: a
  different site uses the same folder, and installing would change what that
  site shows. Send it to Claude.
- **"the IPv6 (AAAA) records ... could not be checked"**: the DNS lookup
  services did not answer. Paste the line again in a few minutes.
- **"the Caddyfile on disk holds changes Caddy is not running yet"**: someone
  edited the Caddyfile without reloading. Reloading now would switch on their
  edit too, so it stopped. Send it to Claude.
- **"the edge container is reading a different copy of the Caddyfile"**: the
  file on disk was replaced at some point, and the edge still reads the old
  one. Send it to Claude.
- **"downloaded with the wrong contents"**: a site file from GitHub did not
  match its pinned fingerprint. Paste the line again later; if it repeats,
  send it to Claude.
- **"tqohq.online is live from this box, and stage mode would take it
  offline"**: you pasted the stage line after going live. Nothing changed. To
  update the live page use the live line.

## What it never does

- It never prints the Caddyfile, never copies it anywhere another user can
  read, and never sends it off the box. Only Caddy's one error line is shown,
  with anything that looks like a password hash hidden.
- It never edits anything in the Caddyfile outside its own block, which sits
  between `# BEGIN tqohq managed by install-on-vps.sh` and `# END tqohq`. The
  one exception is put back: if the Caddyfile has no line break at its very
  end, one is added before the block, the block says so in a comment, and
  rollback takes it out again.
- It never moves, replaces or deletes a site folder it did not make. A
  folder in the way is a reason to stop, not something to clear.
- It never runs twice at once. A second paste while one is going stops at
  once and says so.
- It never restarts a container. It asks Caddy to reload, which keeps every
  site up.
- It never replaces the Caddyfile with a new file. The edge mounts that one
  file, and would go on reading the old copy, so the script rewrites it in
  place and checks the file is still the same one afterwards.

## Where things live on the box

The script reads these from the edge container itself rather than assuming
them. On 2026-09-23 the compose file said:

- the Caddyfile: `/opt/editforge/app/Caddyfile`. Before each change the script
  saves a copy beside it, `Caddyfile.tqohq-backup-<date and time>`, readable by
  root only. A failed run deletes its own copy again, because it put the file
  back.
- the site folder: `/opt/devon/static/tqohq`, seen by Caddy as
  `/srv/static/tqohq`. The copy from before the last install is kept beside it
  as `tqohq.prev`.
- the installer's record: `Caddyfile.tqohq-record` beside the Caddyfile,
  readable by root only. It lists the site folders this installer made, each
  with a fingerprint of its files (every name and every file's sha256). A
  folder counts as the installer's only when its fingerprint matches, or when
  it holds exactly the pinned files. Rollback removes the record once none of
  the installer's folders is left.

"Put back exactly as it was" covers every file this script writes. Caddy may
keep a certificate it fetched for the new name in its own data volume during a
failed run; that does no harm, and a later run reuses it.

## The Caddy block

Stage writes this, and nothing else:

```
# BEGIN tqohq managed by install-on-vps.sh
# The TQO home page: four files from tdveal74-cell/Meta-Supreme-Apex-Genesis- at commit 64f997279fb430be030c2146e917312266c1fe4f.
# install-on-vps.sh rewrites everything between these marker lines on every run; change the script, not this block.
tqohq-stage.editforge.online {
	root * /srv/static/tqohq
	encode zstd gzip
	header {
		X-Content-Type-Options "nosniff"
		Referrer-Policy "strict-origin-when-cross-origin"
		Permissions-Policy "camera=(), microphone=(), geolocation=()"
		X-Robots-Tag "noindex, nofollow"
	}
	@tqohq_fonts path /fonts/atkinson-hyperlegible-next-latin.woff2 /fonts/OFL-atkinson-hyperlegible-next.txt
	handle @tqohq_fonts {
		header Cache-Control "public, max-age=31536000, immutable"
		file_server
	}
	@tqohq_pages path / /index.html /privacy.html
	handle @tqohq_pages {
		header Cache-Control "public, max-age=300"
		file_server
	}
	handle {
		respond "Not found" 404
	}
}
# END tqohq
```

Live writes the same site for `tqohq.online` without the `X-Robots-Tag` line,
then `www.tqohq.online { redir https://tqohq.online{uri} permanent }`, then the
stage site above, all inside the same two marker lines. The exact bytes of both
blocks are asserted by the harness (`EXPECTED_STAGE_BLOCK` and
`EXPECTED_LIVE_BLOCK` in `test/run.sh`).

No Content-Security-Policy header is sent, so the pages' own meta tags stay the
only policy. The long cache applies to the two font files by name, so a 404
under `/fonts/` is not cached for a year.

## For whoever maintains this

### Order of work

Every check runs before anything changes: root, the commands it needs, at
least 1 MB free in the temporary folder, exactly one running container
labelled `com.docker.compose.project=editforge` and
`com.docker.compose.service=edge`, the Caddyfile and `/srv/static` bind mounts
read from `docker inspect`, the lock (`flock -n` on the Caddyfile itself, so a
second run stops at once and no lock file is left anywhere), at least 1 MB
free beside the Caddyfile and, for stage and live, in the static folder, the
edge seeing the same
Caddyfile (same inode and same bytes from inside), the current Caddyfile
validating, Caddy's running config matching the Caddyfile (flattened JSON from
`caddy adapt` against the admin API's `/config/`), no other block using these
names, no other site reaching `/srv/static/tqohq` or `tqohq.prev` (in the text
outside the block, which also catches a mention in a comment, and in the
adapted config, where snippets and `{args}` are expanded), the site folders being this installer's own by the record, DNS for
every name the new block serves (A records must be exactly this box's public
IPv4, AAAA records must be this box's own IPv6 or absent, and a lookup that
cannot run is a refusal, not a pass), the download and its sizes and sha256s,
and a status code from every other site, probed from the box at `127.0.0.1`
with `--resolve`.

Then: site folder (built as a sibling, swapped in by rename), the record,
backup, Caddyfile rewritten in place, validate, reload, every other site
probed again until it gives the same status code as before (three retries; a
site that answers differently, not only one that goes dark, fails the run),
then the new names fetched and the body of `/` compared with index.html's
sha256. Any failure from the first change on, including Ctrl-C, undoes
everything in reverse. A dropped terminal (SIGHUP) and a closed output pipe
(SIGPIPE) are both ignored, so neither can stop it half way: writes to a
terminal or pipe that is gone just fail, and the run finishes.

When a new name has no certificate yet, TLS to it fails even with `-k`. The
page is then proven by opening a connection for a site that already has a
certificate and asking for the new name in the Host header. A 421 answer to
that means the server has `strict_sni_host` on and will not answer one name on
another's connection, so the page is reported as not fetched yet rather than
wrong. The certificate itself is retried for 90 seconds and then reported as
pending. Status does the same, with a site it finds answering.

### Test seams

`TQOHQ_DOCKER`, `TQOHQ_CURL`, `TQOHQ_GETENT` and `TQOHQ_CERT_WAIT_S` are
honoured only when `TQOHQ_TEST_ROOT` names a directory holding a file called
`.tqohq-fake-root`. Without that they are ignored and a note says so; with
`TQOHQ_TEST_ROOT` set to anything else the script refuses to run. The public
IPv4 lookup and the DNS-over-HTTPS AAAA lookup both go through `curl`, so the
curl seam covers them. In test mode the local IPv6 list is read from
`$TQOHQ_TEST_ROOT/proc/net/if_inet6`.

### The harness

```
bash sites/tqohq/deploy/test/run.sh
```

It needs git, python3, curl and network access to fetch Caddy 2.10.2 (or
`TQOHQ_CADDY_TGZ` pointing at a local copy; the sha512 is checked against the
release either way). Each case builds a fake root with a representative
Caddyfile (reverse proxies, static sites, a wildcard, a plain http site, a
`basic_auth` block with a real bcrypt hash) and runs the real Caddy binary on
high ports as the edge, with Caddy's internal CA, so it never asks Let's
Encrypt for anything. `fake-docker` answers `ps`, `inspect` and `exec` and runs
the real `caddy validate`, `adapt` and `reload`. It models the single-file
bind mount with a hard link taken at start, so a Caddyfile replaced on disk is
not seen by the fake edge, just as on the real box. `fake-curl` sends probes to
that Caddy and the site download to a local file server (or to GitHub in one
case); `fake-getent` answers from a table. The cases also cover output cut off
part way, two runs at once, folders the installer did not make (plain and
reached through a snippet), an upgrade from an older release with two
rollbacks, a site that changes its answer, sites already dark, `strict_sni_host`,
a Caddyfile saved with CRLF after install, one with no final line break, the
DNS lookup services down, a Caddy check that says nothing, full disks (on a
small tmpfs, skipped where the container may not mount one), and the four
paste lines themselves under bash and dash.

What it cannot prove: anything about the real box. It does not know the real
Caddyfile, the real container's `wget` and `stat`, Docker's handling of a
published port on `127.0.0.1`, or a real certificate from Let's Encrypt. Nor
whether the box has `flock` and a `stat` that reads free space (`stat -f`);
the script checks both at run time and refuses without them. Those are listed
as unverified in the handover.
