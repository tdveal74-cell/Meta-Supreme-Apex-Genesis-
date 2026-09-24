#!/usr/bin/env bash
# Harness for install-on-vps.sh.
#
# Every case builds a fresh fake root: a representative host Caddyfile (other
# sites, reverse proxies, a basic_auth block with a real bcrypt hash, static
# sites, a wildcard, a plain http site), the static folder, and a real Caddy
# 2.10.2 running that Caddyfile on high ports as the "edge". The installer is
# then run through fake-docker, fake-curl and fake-getent, and every claim is
# asserted, never eyeballed.
#
#   bash sites/tqohq/deploy/test/run.sh
#
# Optional environment:
#   TQOHQ_CADDY_TGZ     a local copy of caddy_2.10.2_linux_amd64.tar.gz
#                       (otherwise it is downloaded from GitHub); either way
#                       its sha512 must match the release checksum below
#   TQOHQ_HARNESS_WORK  where to build fake roots (default: a new temp dir)
#   SHELLCHECK          path to shellcheck, when it is not on PATH
#   TQOHQ_SCRIPT_UNDER_TEST  run the cases against another copy of the
#                       installer (used to check the harness catches mutants)
#   TQOHQ_REPO_ROOT     the git checkout holding the pinned site commit
#
# Two cases fill a small tmpfs to prove the disk-full refusals. They need root
# and a kernel that lets this container mount tmpfs; where it cannot, they are
# reported as SKIP rather than passed.
set -euo pipefail
export LC_ALL=C

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
SCRIPT="${TQOHQ_SCRIPT_UNDER_TEST:-$HERE/../install-on-vps.sh}"
REPO_ROOT="${TQOHQ_REPO_ROOT:-$(git -C "$HERE" rev-parse --show-toplevel)}"
SITE_COMMIT=64f997279fb430be030c2146e917312266c1fe4f
CADDY_URL=https://github.com/caddyserver/caddy/releases/download/v2.10.2/caddy_2.10.2_linux_amd64.tar.gz
# From caddy_2.10.2_checksums.txt on the v2.10.2 release.
CADDY_SHA512=747df7ee74de188485157a383633a1a963fd9233b71fbb4a69ddcbcc589ce4e2cc82dacf5dbbe136cb51d17e14c59daeb5d9bc92487610b0f3b93680b2646546
WORKDIR="${TQOHQ_HARNESS_WORK:-$(mktemp -d)}"
mkdir -p "$WORKDIR"
WORKDIR=$(cd -- "$WORKDIR" && pwd)

STAGE=tqohq-stage.editforge.online
APEX=tqohq.online
WWW=www.tqohq.online
BOX_IP=203.0.113.10
ELSEWHERE_IP=191.101.104.238
BEGIN_MARK="# BEGIN tqohq managed by install-on-vps.sh"
END_MARK="# END tqohq"
INDEX_SHA=a00f6ababd65a79b674bae3178889cce099c9464b20f7ae50b0530fc72ba5970
PRIVACY_SHA=f7ee9cc9166885e4f4b1f675caf31d8819fb38cf60d36ddc5872e958274eb5a9
SITE_FILES=(index.html privacy.html fonts/atkinson-hyperlegible-next-latin.woff2 fonts/OFL-atkinson-hyperlegible-next.txt)
PINS="a00f6ababd65a79b674bae3178889cce099c9464b20f7ae50b0530fc72ba5970  index.html
f7ee9cc9166885e4f4b1f675caf31d8819fb38cf60d36ddc5872e958274eb5a9  privacy.html
18b2a1a39a2fa298b0ba5390aca68462669826c90925656f1c1f6796e0e1bbaf  fonts/atkinson-hyperlegible-next-latin.woff2
aca6a428580965d2297d1b718042dd427c2a9443ece3b0d02d758e161e0c4030  fonts/OFL-atkinson-hyperlegible-next.txt"

PASSN=0
FAILN=0
SKIPN=0
FAILED=()
ALL_OUTPUTS=()
PIDS=()

# The block the installer must write for stage mode, byte for byte.
EXPECTED_STAGE_BLOCK=$(
	cat <<'EOF'
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
EOF
)

# The block the installer must write for live mode, byte for byte.
EXPECTED_LIVE_BLOCK=$(
	cat <<'EOF'
# BEGIN tqohq managed by install-on-vps.sh
# The TQO home page: four files from tdveal74-cell/Meta-Supreme-Apex-Genesis- at commit 64f997279fb430be030c2146e917312266c1fe4f.
# install-on-vps.sh rewrites everything between these marker lines on every run; change the script, not this block.
tqohq.online {
	root * /srv/static/tqohq
	encode zstd gzip
	header {
		X-Content-Type-Options "nosniff"
		Referrer-Policy "strict-origin-when-cross-origin"
		Permissions-Policy "camera=(), microphone=(), geolocation=()"
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
www.tqohq.online {
	redir https://tqohq.online{uri} permanent
}
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
EOF
)

# ---------------------------------------------------------------------------
# Reporting.
# ---------------------------------------------------------------------------
t() {
	local desc="$1"
	shift
	if "$@" >/dev/null 2>&1; then
		PASSN=$((PASSN + 1))
		printf '    PASS  %s\n' "$desc"
	else
		FAILN=$((FAILN + 1))
		FAILED+=("$CASE: $desc")
		printf '    FAIL  %s\n' "$desc"
	fi
}

skip() {
	SKIPN=$((SKIPN + 1))
	printf '    SKIP  %s\n' "$1"
}

eq() { [[ "$1" == "$2" ]]; }
has() { grep -q -F -- "$2" "$1"; }
hasnt() { ! grep -q -F -- "$2" "$1"; }
same_file() { cmp -s -- "$1" "$2"; }

show_run() {
	printf '  $ install-on-vps.sh %s   (exit %s)\n' "$1" "$RC"
	sed -e "s#$WORKDIR#<work>#g" -e 's/^/  | /' "$OUT"
}

cleanup() {
	set +e
	if [[ -n "${S:-}" && -d "${S:-}" ]]; then
		"$HERE/fake-docker" __stop-edge >/dev/null 2>&1
	fi
	for p in "${PIDS[@]}"; do
		kill "$p" 2>/dev/null
	done
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# One-time setup.
# ---------------------------------------------------------------------------
echo "== setup"
echo "work folder: $WORKDIR"

tgz="${TQOHQ_CADDY_TGZ:-$WORKDIR/caddy.tgz}"
if [[ ! -f "$tgz" ]]; then
	curl -fsSL -o "$tgz" "$CADDY_URL"
fi
if [[ "$(sha512sum <"$tgz" | awk '{print $1}')" != "$CADDY_SHA512" ]]; then
	echo "caddy tarball does not match the v2.10.2 release checksum" >&2
	exit 1
fi
mkdir -p "$WORKDIR/bin"
tar xzf "$tgz" -C "$WORKDIR/bin" caddy
CADDY="$WORKDIR/bin/caddy"
echo "caddy: $("$CADDY" version | cut -d' ' -f1) (tarball sha512 matches the release checksum)"

read -r HTTP_PORT HTTPS_PORT ADMIN_PORT APP_PORT RAW_PORT DEAD_PORT < <(
	python3 - <<'EOF'
import socket
held, ports = [], []
for _ in range(6):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    ports.append(s.getsockname()[1])
    held.append(s)
print(*ports)
EOF
)
echo "ports: http $HTTP_PORT, https $HTTPS_PORT, admin $ADMIN_PORT, app $APP_PORT, raw $RAW_PORT, dead $DEAD_PORT"

BCRYPT=$("$CADDY" hash-password --plaintext "harness-only-$RANDOM-$RANDOM" 2>/dev/null)
[[ "$BCRYPT" == \$2a\$* ]] || {
	echo "could not make a bcrypt hash" >&2
	exit 1
}

mkdir -p "$WORKDIR/app"
echo "app upstream" >"$WORKDIR/app/index.html"
for kind in good corrupt; do
	d="$WORKDIR/rawsrv/$kind/tdveal74-cell/Meta-Supreme-Apex-Genesis-/$SITE_COMMIT/sites/tqohq"
	mkdir -p "$d/fonts"
	for f in "${SITE_FILES[@]}"; do
		git -C "$REPO_ROOT" show "$SITE_COMMIT:sites/tqohq/$f" >"$d/$f"
	done
done
GOOD_DIR="$WORKDIR/rawsrv/good/tdveal74-cell/Meta-Supreme-Apex-Genesis-/$SITE_COMMIT/sites/tqohq"
CORRUPT_INDEX="$WORKDIR/rawsrv/corrupt/tdveal74-cell/Meta-Supreme-Apex-Genesis-/$SITE_COMMIT/sites/tqohq/index.html"
python3 - "$CORRUPT_INDEX" <<'EOF'
import sys
p = sys.argv[1]
b = bytearray(open(p, "rb").read())
b[1000] ^= 0x01
open(p, "wb").write(bytes(b))
EOF
(cd "$GOOD_DIR" && printf '%s\n' "$PINS" | sha256sum -c --quiet) || {
	echo "the files at $SITE_COMMIT do not match the pins" >&2
	exit 1
}
echo "the four files at $SITE_COMMIT match the pinned sha256 values; the corrupt copy of index.html differs by one byte"

# An "older release" of this installer, for the upgrade and double rollback
# case: the same script pinned to a made-up older commit whose index.html
# differs, served by the same local file server.
OLD_COMMIT=0123456789abcdef0123456789abcdef01234567
OLD_DIR="$WORKDIR/rawsrv/good/tdveal74-cell/Meta-Supreme-Apex-Genesis-/$OLD_COMMIT/sites/tqohq"
mkdir -p "$OLD_DIR/fonts"
for f in "${SITE_FILES[@]}"; do
	cp "$GOOD_DIR/$f" "$OLD_DIR/$f"
done
printf '<!-- the older release of this page -->\n' >>"$OLD_DIR/index.html"
OLD_INDEX_SHA=$(sha256sum <"$OLD_DIR/index.html" | awk '{print $1}')
OLD_INDEX_BYTES=$(stat -c %s "$OLD_DIR/index.html")
OLDER_SCRIPT="$WORKDIR/older-install-on-vps.sh"
sed -e "s/^SITE_COMMIT=\"$SITE_COMMIT\"\$/SITE_COMMIT=\"$OLD_COMMIT\"/" \
	-e "s/\"index.html 26486 $INDEX_SHA\"/\"index.html $OLD_INDEX_BYTES $OLD_INDEX_SHA\"/" \
	-e "s/^INDEX_SHA256=\"$INDEX_SHA\"\$/INDEX_SHA256=\"$OLD_INDEX_SHA\"/" \
	"$SCRIPT" >"$OLDER_SCRIPT"
if [[ "$(grep -c -e "$OLD_COMMIT" -e "$OLD_INDEX_SHA" "$OLDER_SCRIPT")" != 3 ]] || grep -q "$INDEX_SHA" "$OLDER_SCRIPT"; then
	echo "could not make the older installer from $SCRIPT" >&2
	exit 1
fi
echo "older release for the upgrade case: commit $OLD_COMMIT, index.html $OLD_INDEX_BYTES bytes"

# What the paste lines in the README download: the installer, and three
# answers that must never reach bash (an HTML page, an empty body, a 404).
mkdir -p "$WORKDIR/rawsrv/paste/good" "$WORKDIR/rawsrv/paste/html" "$WORKDIR/rawsrv/paste/empty"
cp "$SCRIPT" "$WORKDIR/rawsrv/paste/good/install-on-vps.sh"
printf '<!DOCTYPE html>\n<html><body><h1>Rate limited</h1></body></html>\n' >"$WORKDIR/rawsrv/paste/html/install-on-vps.sh"
: >"$WORKDIR/rawsrv/paste/empty/install-on-vps.sh"
SCRIPT_SHA=$(sha256sum <"$SCRIPT" | awk '{print $1}')

(cd "$WORKDIR/app" && exec python3 -m http.server --bind 127.0.0.1 "$APP_PORT") >"$WORKDIR/app.log" 2>&1 &
PIDS+=($!)
(cd "$WORKDIR/rawsrv" && exec python3 -m http.server --bind 127.0.0.1 "$RAW_PORT") >"$WORKDIR/raw.log" 2>&1 &
PIDS+=($!)
for _ in $(seq 1 50); do
	if curl --noproxy '*' -fsS -o /dev/null "http://127.0.0.1:$APP_PORT/" 2>/dev/null && curl --noproxy '*' -fsS -o /dev/null "http://127.0.0.1:$RAW_PORT/" 2>/dev/null; then
		break
	fi
	sleep 0.1
done

echo
echo "== static checks"
if bash -n "$SCRIPT"; then echo "bash -n install-on-vps.sh: ok"; else echo "bash -n install-on-vps.sh: FAILED"; FAILN=$((FAILN + 1)); fi
for f in run.sh fake-docker fake-curl fake-getent; do
	if bash -n "$HERE/$f"; then echo "bash -n test/$f: ok"; else echo "bash -n test/$f: FAILED"; FAILN=$((FAILN + 1)); fi
done
SC="${SHELLCHECK:-$(command -v shellcheck || true)}"
if [[ -n "$SC" && -x "$SC" ]]; then
	if "$SC" "$SCRIPT"; then
		echo "shellcheck $("$SC" --version | sed -n 's/^version: //p') install-on-vps.sh: clean"
	else
		echo "shellcheck install-on-vps.sh: FINDINGS above"
		FAILN=$((FAILN + 1))
	fi
else
	echo "shellcheck: not available here, not run"
fi

# ---------------------------------------------------------------------------
# Per case.
# ---------------------------------------------------------------------------
new_case() {
	if [[ -n "${S:-}" && -d "${S:-}" ]]; then
		"$HERE/fake-docker" __stop-edge
	fi
	CASE="$1"
	echo
	echo "== $CASE"
	C="$WORKDIR/cases/$CASE"
	R="$C/root"
	S="$C/state"
	RUN_N=0
	rm -rf "$C"
	mkdir -p "$R/opt/editforge/app" "$R/opt/devon/static/meta" "$R/opt/devon/static/hud" "$R/opt/devon/static/tsws" "$R/proc/net" \
		"$S/tmp" "$S/caddy-data" "$S/caddy-config"
	: >"$R/.tqohq-fake-root"
	echo "<h1>meta</h1>" >"$R/opt/devon/static/meta/index.html"
	echo "<h1>hud</h1>" >"$R/opt/devon/static/hud/index.html"
	echo "<h1>tsws</h1>" >"$R/opt/devon/static/tsws/index.html"
	printf 'name: editforge\n' >"$R/opt/editforge/app/compose.yaml"
	CF="$R/opt/editforge/app/Caddyfile"
	sed -e "s/@@ADMIN_PORT@@/$ADMIN_PORT/" -e "s/@@HTTP_PORT@@/$HTTP_PORT/" -e "s/@@HTTPS_PORT@@/$HTTPS_PORT/" \
		-e "s/@@APP_PORT@@/$APP_PORT/g" -e "s/@@DEAD_PORT@@/$DEAD_PORT/" -e "s#@@BCRYPT@@#$BCRYPT#" \
		"$HERE/Caddyfile.fixture" >"$CF"
	# A case may reshape the fixture before the edge starts on it.
	if [[ -n "${2:-}" ]]; then
		"$2"
	fi
	chmod 640 "$CF"
	printf '%s\n' \
		"00000000000000000000000000000001 01 80 10 80       lo" \
		"20010db8000000000000000000000010 02 40 00 80     eth0" \
		"fe800000000000000000000000000010 02 40 20 80     eth0" >"$R/proc/net/if_inet6"
	printf '%s\n' "$STAGE A $BOX_IP" "$APEX A $ELSEWHERE_IP" "$WWW A $ELSEWHERE_IP" >"$S/dns"
	echo "$BOX_IP" >"$S/public-ip"
	: >"$S/docker.log"
	: >"$S/curl.log"
	: >"$S/unexpected.log"
	export FAKE_ROOT="$R" FAKE_STATE="$S" FAKE_CADDY="$CADDY" FAKE_ADMIN_PORT="$ADMIN_PORT"
	export FAKE_HTTPS_PORT="$HTTPS_PORT" FAKE_HTTP_PORT="$HTTP_PORT" FAKE_RAW_URL="http://127.0.0.1:$RAW_PORT/good"
	export FAKE_DEAD_PORT="$DEAD_PORT"
	unset FAKE_EDGE_COUNT FAKE_VALIDATE_FAIL FAKE_BREAK_HOST FAKE_502_HOST FAKE_WRONG_ROOT FAKE_TLS_DOWN FAKE_DOH_DOWN FAKE_RAW_MODE
	UNDER_TEST="$SCRIPT"
	RUN_TMPDIR=""
	CERT_WAIT=20
	"$HERE/fake-docker" __start-edge
	cp -p "$CF" "$C/pristine.Caddyfile"
	CF_INO=$(stat -c %i "$CF")
	PRISTINE="$C/pristine.snap"
	snap >"$PRISTINE"
}

snap() {
	(
		cd "$R"
		find . -printf '%y %m %i %s %p -> %l\n' | sort
		find . -type f -print0 | sort -z | xargs -0 sha256sum
	)
}

snap_same_as() {
	snap >"$C/now.snap"
	cmp -s "$1" "$C/now.snap"
}

snap_same_ignoring_backups() {
	snap | grep -v 'Caddyfile\.tqohq-backup-' >"$C/now.snap"
	grep -v 'Caddyfile\.tqohq-backup-' "$1" >"$C/then.snap"
	cmp -s "$C/then.snap" "$C/now.snap"
}

run_script() {
	local mode="$1"
	shift
	RUN_N=$((RUN_N + 1))
	OUT="$C/out.$RUN_N.$mode"
	DOCKER_MARK=$(wc -l <"$S/docker.log")
	CURL_MARK=$(wc -l <"$S/curl.log")
	set +e
	env "$@" TQOHQ_TEST_ROOT="$R" TQOHQ_DOCKER="$HERE/fake-docker" TQOHQ_CURL="$HERE/fake-curl" \
		TQOHQ_GETENT="$HERE/fake-getent" TMPDIR="${RUN_TMPDIR:-$S/tmp}" TQOHQ_CERT_WAIT_S="$CERT_WAIT" \
		bash "$UNDER_TEST" "$mode" >"$OUT" 2>&1
	RC=$?
	set -e
	after_run "$mode"
}

after_run() {
	ALL_OUTPUTS+=("$OUT")
	show_run "$1"
	LAST=$(tail -n 1 "$OUT")
	t "the last line starts with RESULT:" eq "${LAST:0:7}" "RESULT:"
	t "exactly one RESULT line" eq "$(grep -c '^RESULT:' "$OUT")" 1
	t "its private temp folder is gone" eq "$(find "${RUN_TMPDIR:-$S/tmp}" -mindepth 1 | wc -l)" 0
	t "no fake saw an unexpected call" eq "$(wc -l <"$S/unexpected.log")" 0
}

docker_calls_since_mark() { tail -n "+$((DOCKER_MARK + 1))" "$S/docker.log"; }
reloads_since_mark() { docker_calls_since_mark | grep -c 'caddy reload' || true; }

CA() { echo "$S/caddy-data/caddy/pki/authorities/local/root.crt"; }
# Real curl straight at the local caddy, independent of the fakes.
lc() {
	local host="$1"
	shift
	curl --noproxy '*' -sS --cacert "$(CA)" --resolve "$host:$HTTPS_PORT:127.0.0.1" "$@"
}
code_of() { lc "$1" -o /dev/null -w '%{http_code}' "https://$1:$HTTPS_PORT${2:-/}" 2>/dev/null || true; }
http_code_of() { curl --noproxy '*' -sS -o /dev/null -w '%{http_code}' --resolve "$1:$HTTP_PORT:127.0.0.1" "http://$1:$HTTP_PORT/" 2>/dev/null || true; }
body_sha() { { lc "$1" "https://$1:$HTTPS_PORT${2:-/}" 2>/dev/null || true; } | sha256sum | awk '{print $1}'; }
headers_of() { { lc "$1" -D - -o /dev/null "${@:3}" "https://$1:$HTTPS_PORT${2:-/}" 2>/dev/null || true; } | tr -d '\r'; }
header_is() { grep -qix -F -- "$2" <<<"$1"; }

block_of() { awk -v b="$BEGIN_MARK" -v e="$END_MARK" '$0 == b { on = 1 } on { print } $0 == e { on = 0 }' "$1"; }
outside_block() { awk -v b="$BEGIN_MARK" -v e="$END_MARK" '$0 == b { on = 1 } !on { print } $0 == e { on = 0 }' "$1"; }
count_line() { grep -cx -F -- "$2" "$1" || true; }
backups() { find "$R/opt/editforge/app" -maxdepth 1 -name 'Caddyfile.tqohq-backup-*' | sort; }

other_sites_as_before() {
	[[ "$(code_of meta.editforge.online)" == 200 ]] &&
		[[ "$(code_of hud.editforge.online)" == 200 ]] &&
		[[ "$(code_of tsws.editforge.online)" == 200 ]] &&
		[[ "$(code_of editforge.online)" == 200 ]] &&
		[[ "$(code_of rakazo.editforge.online)" == 200 ]] &&
		[[ "$(code_of tqohr.editforge.online)" == 200 ]] &&
		[[ "$(code_of www.tqohr.editforge.online)" == 200 ]] &&
		[[ "$(code_of studio-private.editforge.online)" == 401 ]] &&
		[[ "$(code_of x.preview.editforge.online)" == 200 ]] &&
		[[ "$(code_of upstream-down.editforge.online)" == 502 ]] &&
		[[ "$(http_code_of plain.editforge.online)" == 200 ]]
}

site_files_match_pins() { (cd "$R/opt/devon/static/tqohq" && printf '%s\n' "$PINS" | sha256sum -c --quiet); }
no_build_leftovers() { eq "$(find "$R/opt/devon/static" -maxdepth 1 -name '.tqohq-*' | wc -l)" 0; }
block_is_fmt_clean() {
	block_of "$CF" >"$C/block.check"
	"$CADDY" fmt "$C/block.check" >"$C/block.fmt" 2>/dev/null
	cmp -s "$C/block.check" "$C/block.fmt"
}
all_backups_mode_600() {
	local b
	while read -r b; do
		[[ -z "$b" ]] && continue
		[[ "$(stat -c %a "$b")" == 600 ]] || return 1
	done < <(backups)
}

RECORD_OF() { echo "$R/opt/editforge/app/Caddyfile.tqohq-record"; }
# The entries in the installer's record, "name" only, sorted, one line.
record_names() { { grep -v '^#' "$(RECORD_OF)" 2>/dev/null || true; } | awk '{print $1}' | sort | tr '\n' ' '; }
# The fingerprint the record holds for a folder, recomputed here independently
# from the folder itself.
fingerprint() { (cd "$1" && { find . -mindepth 1 -printf '%y %P\n'; find . -type f -exec sha256sum -- {} +; } | sort) | sha256sum | awk '{print $1}'; }
record_sum_of() { awk -v n="$1" '$1 == n { print $2 }' "$(RECORD_OF)" 2>/dev/null || true; }
index_sha_of() { sha256sum <"$R/opt/devon/static/$1/index.html" | awk '{print $1}'; }
edge_reload() { "$HERE/fake-docker" exec 4f1e0c2a9b7d caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null 2>&1; }

# Run the installer in the background (its own temp folder), for the cases
# that act while it is still going.
start_bg() {
	local mode="$1" tmp="$2"
	shift 2
	RUN_N=$((RUN_N + 1))
	BG_OUT="$C/out.$RUN_N.$mode"
	mkdir -p "$tmp"
	env "$@" TQOHQ_TEST_ROOT="$R" TQOHQ_DOCKER="$HERE/fake-docker" TQOHQ_CURL="$HERE/fake-curl" TQOHQ_GETENT="$HERE/fake-getent" \
		TMPDIR="$tmp" TQOHQ_CERT_WAIT_S="$CERT_WAIT" bash "$UNDER_TEST" "$mode" >"$BG_OUT" 2>&1 &
	BGPID=$!
}
wait_for_cert_wait() {
	for _ in $(seq 1 300); do
		if grep -q "https://$STAGE/" "$S/curl.log" || ! kill -0 "$BGPID" 2>/dev/null; then break; fi
		sleep 0.1
	done
}

# Mount a small tmpfs, for the disk-full cases. Fails when this container
# may not mount.
small_tmpfs() { mkdir -p "$1" && mount -t tmpfs -o "size=$2" tmpfs "$1" 2>/dev/null; }

# ---------------------------------------------------------------------------
# Cases.
# ---------------------------------------------------------------------------
new_case A-fresh-stage-install
t "before: every other site answers as the fixture says" other_sites_as_before
t "before: the stage name is not served" eq "$(code_of "$STAGE")" 000
run_script stage
t "exit 0" eq "$RC" 0
t "RESULT says DONE with a valid certificate" has "$OUT" "RESULT: DONE, the stage page is installed at https://$STAGE and all 11 other sites still answer, with a valid certificate"
t "exactly one BEGIN and one END marker" eq "$(count_line "$CF" "$BEGIN_MARK") $(count_line "$CF" "$END_MARK")" "1 1"
t "the block is exactly the expected stage block" eq "$(block_of "$CF")" "$EXPECTED_STAGE_BLOCK"
t "every byte outside the block is the original file" eq "$(outside_block "$CF" | sha256sum)" "$(sha256sum <"$C/pristine.Caddyfile")"
t "the Caddyfile keeps its inode" eq "$(stat -c %i "$CF")" "$CF_INO"
t "the Caddyfile keeps its mode" eq "$(stat -c %a "$CF")" 640
t "one backup, mode 600, identical to the original" eq "$(backups | wc -l) $(stat -c %a "$(backups | head -n 1)") $(sha256sum <"$(backups | head -n 1)")" "1 600 $(sha256sum <"$C/pristine.Caddyfile")"
t "the installer's record is beside the Caddyfile, mode 600" eq "$(stat -c %a "$(RECORD_OF)")" 600
t "the record names the site folder only" eq "$(record_names)" "tqohq "
t "the record's fingerprint is the site folder's" eq "$(record_sum_of tqohq)" "$(fingerprint "$R/opt/devon/static/tqohq")"
t "the four site files match the pins" site_files_match_pins
t "site folder is exactly the four files" eq "$(cd "$R/opt/devon/static/tqohq" && find . -mindepth 1 | sort | tr '\n' ' ')" "./fonts ./fonts/OFL-atkinson-hyperlegible-next.txt ./fonts/atkinson-hyperlegible-next-latin.woff2 ./index.html ./privacy.html "
t "site folder 755, files 644" eq "$(stat -c %a "$R/opt/devon/static/tqohq" "$R/opt/devon/static/tqohq/fonts" "$R/opt/devon/static/tqohq/index.html" | tr '\n' ' ')" "755 755 644 "
t "no tqohq.prev on a first install" test ! -e "$R/opt/devon/static/tqohq.prev"
t "no build leftovers in the static folder" no_build_leftovers
t "the other static sites are untouched" eq "$(grep -E ' \./opt/devon/static/(meta|hud|tsws)' "$PRISTINE")" "$(snap | grep -E ' \./opt/devon/static/(meta|hud|tsws)')"
t "the block is caddy fmt clean" block_is_fmt_clean
t "served: / is index.html (sha256)" eq "$(body_sha "$STAGE" /)" "$INDEX_SHA"
t "served: /index.html is index.html" eq "$(body_sha "$STAGE" /index.html)" "$INDEX_SHA"
t "served: /privacy.html is privacy.html" eq "$(body_sha "$STAGE" /privacy.html)" "$PRIVACY_SHA"
t "served: the woff2 and the licence answer 200" eq "$(code_of "$STAGE" /fonts/atkinson-hyperlegible-next-latin.woff2) $(code_of "$STAGE" /fonts/OFL-atkinson-hyperlegible-next.txt)" "200 200"
t "served: anything else is 404" eq "$(code_of "$STAGE" /nope) $(code_of "$STAGE" /fonts/nope.woff2) $(code_of "$STAGE" /check.mjs) $(code_of "$STAGE" /README.md) $(code_of "$STAGE" /fonts/)" "404 404 404 404 404"
H=$(headers_of "$STAGE" /)
t "headers: nosniff" header_is "$H" "X-Content-Type-Options: nosniff"
t "headers: Referrer-Policy" header_is "$H" "Referrer-Policy: strict-origin-when-cross-origin"
t "headers: Permissions-Policy" header_is "$H" "Permissions-Policy: camera=(), microphone=(), geolocation=()"
t "headers: stage carries X-Robots-Tag noindex" header_is "$H" "X-Robots-Tag: noindex, nofollow"
t "headers: html cache is short" header_is "$H" "Cache-Control: public, max-age=300"
t "headers: no Content-Security-Policy header to fight the pages' meta CSP" hasnt <(printf '%s' "$H") "Content-Security-Policy"
HF=$(headers_of "$STAGE" /fonts/atkinson-hyperlegible-next-latin.woff2)
t "headers: font cache is long" header_is "$HF" "Cache-Control: public, max-age=31536000, immutable"
t "headers: woff2 is font/woff2" header_is "$HF" "Content-Type: font/woff2"
t "headers: a 404 carries no long cache" hasnt <(headers_of "$STAGE" /fonts/nope.woff2) "max-age=31536000"
t "encode: gzip when asked" header_is "$(headers_of "$STAGE" / -H 'Accept-Encoding: gzip')" "Content-Encoding: gzip"
t "encode: zstd when asked" header_is "$(headers_of "$STAGE" / -H 'Accept-Encoding: zstd')" "Content-Encoding: zstd"
t "after: every other site answers exactly as before" other_sites_as_before
t "the certificate verifies against the edge's CA" eq "$(lc "$STAGE" -o /dev/null -w '%{ssl_verify_result}' "https://$STAGE:$HTTPS_PORT/")" 0
AFTER_A="$C/after-a.snap"
snap >"$AFTER_A"
cp -p "$CF" "$C/after-a.Caddyfile"

echo "  -- B: the same stage run again"
run_script stage
t "exit 0" eq "$RC" 0
t "RESULT says nothing needed changing" has "$OUT" "RESULT: DONE, nothing needed changing, because stage was already installed exactly like this"
t "Caddyfile bytes identical to after the first run" same_file "$CF" "$C/after-a.Caddyfile"
t "still exactly one block" eq "$(count_line "$CF" "$BEGIN_MARK") $(count_line "$CF" "$END_MARK")" "1 1"
t "the whole fake root is unchanged (no new backup, no tqohq.prev)" snap_same_as "$AFTER_A"
t "no reload happened" eq "$(reloads_since_mark)" 0

echo "  -- C: status after stage"
run_script status
t "exit 0" eq "$RC" 0
t "RESULT says stage is installed and working" has "$OUT" "RESULT: Stage is installed and working at https://$STAGE with a valid certificate."
t "status changed nothing in the fake root" snap_same_as "$AFTER_A"
t "status ran no validate and no reload" eq "$(docker_calls_since_mark | grep -c -E 'caddy (validate|reload)' || true)" 0

echo "  -- D: live while tqohq.online still points elsewhere"
run_script live
t "exit 1" eq "$RC" 1
t "RESULT refuses and names the DNS problem" has "$OUT" "RESULT: NOT DONE, nothing on the box was changed, because $APEX points at $ELSEWHERE_IP, not at this box ($BOX_IP), so its DNS has to move first."
t "nothing changed in the fake root" snap_same_as "$AFTER_A"
t "only the read-only check of the current file ran, no reload" eq "$(docker_calls_since_mark | grep -c 'caddy validate' || true) $(reloads_since_mark)" "1 0"
t "the site files were never downloaded" eq "$(tail -n "+$((CURL_MARK + 1))" "$S/curl.log" | grep -c raw.githubusercontent.com || true)" 0

echo "  -- E: live with the A records moved but a stray AAAA on www"
printf '%s\n' "$STAGE A $BOX_IP" "$APEX A $BOX_IP" "$WWW A $BOX_IP" "$WWW AAAA 2a02:4780:1:2::99" >"$S/dns"
run_script live
t "exit 1" eq "$RC" 1
t "RESULT refuses and names the AAAA record" has "$OUT" "because $WWW also has an IPv6 (AAAA) record, 2a02:4780:1:2::99, that is not this box, so that AAAA record has to be deleted first."
t "nothing changed in the fake root" snap_same_as "$AFTER_A"

echo "  -- F: live once DNS points at the box (the apex AAAA is this box's own IPv6)"
printf '%s\n' "$STAGE A $BOX_IP" "$APEX A $BOX_IP" "$WWW A $BOX_IP" "$APEX AAAA 2001:db8::10" >"$S/dns"
run_script live
t "exit 0" eq "$RC" 0
t "RESULT says tqohq.online is live" has "$OUT" "RESULT: DONE, tqohq.online now serves the TQO page from this box, www.tqohq.online sends visitors to it, the stage address still works, and all 11 other sites still answer, with a valid certificate"
t "exactly one block" eq "$(count_line "$CF" "$BEGIN_MARK") $(count_line "$CF" "$END_MARK")" "1 1"
t "the block is exactly the expected live block" eq "$(block_of "$CF")" "$EXPECTED_LIVE_BLOCK"
t "every byte outside the block is still the original file" eq "$(outside_block "$CF" | sha256sum)" "$(sha256sum <"$C/pristine.Caddyfile")"
t "the Caddyfile keeps its inode" eq "$(stat -c %i "$CF")" "$CF_INO"
t "the block is caddy fmt clean" block_is_fmt_clean
t "two backups now, all mode 600" eq "$(backups | wc -l)" 2
t "every backup is mode 600" all_backups_mode_600
t "the site files were already current, so no tqohq.prev" test ! -e "$R/opt/devon/static/tqohq.prev"
t "served: tqohq.online / is index.html" eq "$(body_sha "$APEX" /)" "$INDEX_SHA"
t "served: tqohq.online has no X-Robots-Tag" hasnt <(headers_of "$APEX" /) "X-Robots-Tag"
HW=$(headers_of "$WWW" /some/path?x=1)
t "served: www answers 301" grep -q '^HTTP/[0-9.]* 301' <<<"$HW"
t "served: www redirects to https://tqohq.online with the path kept" header_is "$HW" "Location: https://tqohq.online/some/path?x=1"
t "served: stage still serves the page" eq "$(body_sha "$STAGE" /)" "$INDEX_SHA"
t "served: stage still carries noindex" header_is "$(headers_of "$STAGE" /)" "X-Robots-Tag: noindex, nofollow"
t "after: every other site answers exactly as before" other_sites_as_before
AFTER_F="$C/after-f.snap"
snap >"$AFTER_F"

echo "  -- G: stage while live is installed"
run_script stage
t "exit 1" eq "$RC" 1
t "RESULT refuses to take tqohq.online offline" has "$OUT" "because tqohq.online is live from this box, and stage mode would take it offline"
t "nothing changed in the fake root" snap_same_as "$AFTER_F"

echo "  -- H: rollback from live"
run_script rollback
t "exit 0" eq "$RC" 0
t "RESULT says the block and files are gone" has "$OUT" "RESULT: DONE, the tqohq Caddy block and site files are gone and all 11 other sites still answer."
t "RESULT says tqohq.online is no longer served here and its DNS must move back" has "$OUT" "still answer. tqohq.online is no longer served from this box, so its DNS has to move back to where it was before."
t "the installer's record is gone with the folder" test ! -e "$(RECORD_OF)"
t "the Caddyfile is the exact pre-install bytes" same_file "$CF" "$C/pristine.Caddyfile"
t "the Caddyfile keeps its inode" eq "$(stat -c %i "$CF")" "$CF_INO"
t "no tqohq and no tqohq.prev left" test ! -e "$R/opt/devon/static/tqohq" -a ! -e "$R/opt/devon/static/tqohq.prev"
t "apart from the three backups, the fake root is exactly as before the first install" snap_same_ignoring_backups "$PRISTINE"
t "three backups kept, all mode 600" eq "$(backups | wc -l)" 3
t "every backup is mode 600" all_backups_mode_600
t "served: the stage name is gone" eq "$(code_of "$STAGE")" 000
t "served: tqohq.online is gone" eq "$(code_of "$APEX")" 000
t "after: every other site answers exactly as before" other_sites_as_before
AFTER_H="$C/after-h.snap"
snap >"$AFTER_H"
run_script rollback
t "a second rollback exits 0" eq "$RC" 0
t "and says there is nothing to roll back" has "$OUT" "RESULT: DONE, nothing to roll back, because nothing from this installer is on the box."
t "and changes nothing" snap_same_as "$AFTER_H"

new_case I-corrupted-download
run_script status
t "status on a clean box exits 0" eq "$RC" 0
t "status says nothing is installed" has "$OUT" "RESULT: Nothing from this installer is on the box."
t "status changed nothing" snap_same_as "$PRISTINE"
export FAKE_RAW_URL="http://127.0.0.1:$RAW_PORT/corrupt"
run_script stage
t "exit 1" eq "$RC" 1
t "RESULT refuses and names index.html" has "$OUT" "RESULT: NOT DONE, nothing on the box was changed, because index.html downloaded with the wrong contents (its checksum does not match the pinned one)."
t "nothing changed in the fake root" snap_same_as "$PRISTINE"
t "no Caddy reload was attempted" eq "$(reloads_since_mark)" 0
t "the stage name is not served" eq "$(code_of "$STAGE")" 000

new_case J-validate-fails-after-the-change
export FAKE_VALIDATE_FAIL=with-block
run_script stage
t "exit 1" eq "$RC" 1
t "RESULT says it failed and was put back" has "$OUT" "RESULT: FAILED, and the box was put back exactly as it was, because Caddy rejected the new Caddyfile (its message is on the line above)."
t "Caddy's error line is shown" has "$OUT" "Caddy said: Error: adapting config using caddyfile: parsing caddyfile tokens for 'basic_auth'"
t "the hash in Caddy's error line was hidden" has "$OUT" "after '[hidden]', at /etc/caddy/Caddyfile:57"
t "the Caddyfile is restored byte for byte" same_file "$CF" "$C/pristine.Caddyfile"
t "the Caddyfile keeps its inode" eq "$(stat -c %i "$CF")" "$CF_INO"
t "the whole fake root is exactly as before (backup removed, site folder removed)" snap_same_as "$PRISTINE"
t "no reload was attempted" eq "$(reloads_since_mark)" 0
t "the other sites answer as before" other_sites_as_before

new_case K-another-site-goes-dark
export FAKE_BREAK_HOST=meta.editforge.online
run_script stage
t "exit 1" eq "$RC" 1
t "RESULT names the site that went dark" has "$OUT" "RESULT: FAILED, and the box was put back exactly as it was, because meta.editforge.online stopped answering after the reload."
t "the Caddyfile is restored byte for byte" same_file "$CF" "$C/pristine.Caddyfile"
t "the Caddyfile keeps its inode" eq "$(stat -c %i "$CF")" "$CF_INO"
t "the whole fake root is exactly as before" snap_same_as "$PRISTINE"
t "Caddy was reloaded twice: the change, then the restore" eq "$(reloads_since_mark)" 2
t "meta.editforge.online answers again" eq "$(code_of meta.editforge.online)" 200
t "the stage name is not served" eq "$(code_of "$STAGE")" 000
t "the other sites answer as before" other_sites_as_before

new_case K2-new-address-serves-the-wrong-page
export FAKE_WRONG_ROOT=1
run_script stage
t "exit 1" eq "$RC" 1
t "RESULT says the new address did not serve the page, and it was put back" has "$OUT" "RESULT: FAILED, and the box was put back exactly as it was, because the new address did not serve the TQO page: $STAGE (HTTP 200)."
t "the Caddyfile is restored byte for byte" same_file "$CF" "$C/pristine.Caddyfile"
t "the whole fake root is exactly as before" snap_same_as "$PRISTINE"
t "Caddy was reloaded twice: the change, then the restore" eq "$(reloads_since_mark)" 2
t "the stage name is not served" eq "$(code_of "$STAGE")" 000
t "the other sites answer as before" other_sites_as_before

new_case L-box-already-broken
export FAKE_VALIDATE_FAIL=always
run_script stage
t "exit 1" eq "$RC" 1
t "RESULT refuses because the box is already broken" has "$OUT" "because the Caddyfile on the box is already invalid before any change"
t "the hash in Caddy's error line was hidden" has "$OUT" "after '[hidden]'"
t "nothing changed in the fake root" snap_same_as "$PRISTINE"

new_case M-pending-edit-on-disk
printf 'pending.editforge.online {\n\trespond "not loaded yet" 200\n}\n' >>"$CF"
snap >"$PRISTINE"
run_script stage
t "exit 1" eq "$RC" 1
t "RESULT refuses because disk and running config differ" has "$OUT" "because the Caddyfile on disk holds changes Caddy is not running yet, and a reload would apply those as well."
t "nothing changed in the fake root" snap_same_as "$PRISTINE"
t "no reload was attempted" eq "$(reloads_since_mark)" 0

new_case N-edge-container-count
export FAKE_EDGE_COUNT=2
run_script stage
t "two edges: exit 1" eq "$RC" 1
t "two edges: RESULT names the count" has "$OUT" "because 2 running EditForge edge containers were found where exactly one was expected."
export FAKE_EDGE_COUNT=0
run_script stage
t "no edge: exit 1" eq "$RC" 1
t "no edge: RESULT says none was found" has "$OUT" "because no running EditForge edge container was found (compose project editforge, service edge)."
t "nothing changed in the fake root" snap_same_as "$PRISTINE"

new_case O-caddyfile-replaced-under-a-running-edge
# What a past sed -i does: a new file at the same path, while the edge's
# single-file mount still reads the old inode.
sed -i '1i # edited earlier with sed -i, which writes a new file' "$CF"
snap >"$PRISTINE"
run_script stage
t "exit 1" eq "$RC" 1
t "RESULT says the edge reads a different copy" has "$OUT" "because the edge container is reading a different copy of the Caddyfile than the one on disk"
t "nothing changed in the fake root" snap_same_as "$PRISTINE"

new_case P-a-folder-this-installer-did-not-make
# A tqohq folder was already on the box before the installer ever ran. Stage
# used to keep it as tqohq.prev, a later install deleted it, and rollback
# removed it while saying the block was gone. Now nothing touches it.
mkdir -p "$R/opt/devon/static/tqohq"
echo "<h1>an older page someone else put here</h1>" >"$R/opt/devon/static/tqohq/index.html"
chmod 755 "$R/opt/devon/static/tqohq"
OLD_SHA=$(sha256sum <"$R/opt/devon/static/tqohq/index.html")
OLD_INO=$(stat -c %i "$R/opt/devon/static/tqohq")
snap >"$PRISTINE"
run_script status
t "status exits 0" eq "$RC" 0
t "status does not call the folder this installer's site files" has "$OUT" "RESULT: Not installed, and a tqohq folder this installer did not make is on the box, so the stage and live lines will refuse until someone has looked at it; send this line to Claude."
run_script stage
t "stage exits 1" eq "$RC" 1
t "RESULT refuses and names the folder" has "$OUT" "RESULT: NOT DONE, nothing on the box was changed, because a folder $R/opt/devon/static/tqohq is already on the box and this installer did not make it (or it was changed after it did), and installing would replace it"
t "nothing changed in the fake root" snap_same_as "$PRISTINE"
t "no reload was attempted" eq "$(reloads_since_mark)" 0
run_script rollback
t "rollback exits 0" eq "$RC" 0
t "rollback says there is nothing to roll back and the folder was left" has "$OUT" "RESULT: DONE, nothing to roll back: there is no tqohq block in the Caddyfile, and the tqohq folder on the box was not made by this installer (or was changed after it was), so it was left as it is."
t "rollback does not claim a block or site files are gone" hasnt "$OUT" "block and site files are gone"
t "the folder is still there, the same folder with the same page" eq "$(sha256sum <"$R/opt/devon/static/tqohq/index.html") $(stat -c %i "$R/opt/devon/static/tqohq")" "$OLD_SHA $OLD_INO"
t "nothing changed in the fake root" snap_same_as "$PRISTINE"

new_case P2-a-previous-copy-this-installer-did-not-make
mkdir -p "$R/opt/devon/static/tqohq.prev"
echo "notes someone keeps here" >"$R/opt/devon/static/tqohq.prev/NOTES.txt"
snap >"$PRISTINE"
run_script stage
t "stage exits 1" eq "$RC" 1
t "RESULT refuses and names tqohq.prev" has "$OUT" "because a folder $R/opt/devon/static/tqohq.prev is already on the box and this installer did not make it (or it was changed after it did), and installing could delete it"
t "nothing changed in the fake root" snap_same_as "$PRISTINE"

new_case P3-upgrade-then-rollback-twice
# An older release of this installer put its page up; this one replaces it,
# keeps the older copy, and rollback puts that copy back. A second rollback
# then removes what this installer left, and a third finds nothing.
snap >"$PRISTINE"
UNDER_TEST="$OLDER_SCRIPT"
run_script stage
UNDER_TEST="$SCRIPT"
t "the older release installs (exit 0)" eq "$RC" 0
t "it serves the older page" eq "$(body_sha "$STAGE" /)" "$OLD_INDEX_SHA"
OLDER_INO=$(stat -c %i "$R/opt/devon/static/tqohq")
OLDER_FP=$(fingerprint "$R/opt/devon/static/tqohq")
t "the record holds the older copy's fingerprint" eq "$(record_sum_of tqohq)" "$OLDER_FP"
run_script stage
t "this release replaces it (exit 0)" eq "$RC" 0
t "RESULT says DONE" has "$OUT" "RESULT: DONE, the stage page is installed at https://$STAGE and all 11 other sites still answer, with a valid certificate"
t "the older copy is kept as tqohq.prev (same folder)" eq "$(index_sha_of tqohq.prev) $(stat -c %i "$R/opt/devon/static/tqohq.prev")" "$OLD_INDEX_SHA $OLDER_INO"
t "the new copy matches the pins" site_files_match_pins
t "the record names both folders with their fingerprints" eq "$(record_names) $(record_sum_of tqohq.prev) $(record_sum_of tqohq)" "tqohq tqohq.prev  $OLDER_FP $(fingerprint "$R/opt/devon/static/tqohq")"
t "served: the pinned page" eq "$(body_sha "$STAGE" /)" "$INDEX_SHA"
run_script rollback
t "rollback exits 0" eq "$RC" 0
t "RESULT says the previous copy is back" has "$OUT" "RESULT: DONE, the tqohq Caddy block is gone, the previous copy of the site files is back in place, and all 11 other sites still answer."
t "tqohq is the older copy again (same folder)" eq "$(index_sha_of tqohq) $(stat -c %i "$R/opt/devon/static/tqohq")" "$OLD_INDEX_SHA $OLDER_INO"
t "no tqohq.prev left" test ! -e "$R/opt/devon/static/tqohq.prev"
t "the record now names the older copy as the site folder" eq "$(record_names) $(record_sum_of tqohq)" "tqohq  $OLDER_FP"
t "the Caddyfile is the exact pre-install bytes" same_file "$CF" "$C/pristine.Caddyfile"
run_script status
t "status says only this installer's files are left" has "$OUT" "RESULT: Not installed: there is no tqohq block in the Caddyfile, though site files from an earlier run of this installer are still on disk."
run_script rollback
t "a second rollback exits 0" eq "$RC" 0
t "and says there was no block, and what it removed" has "$OUT" "RESULT: DONE, there was no tqohq Caddy block, the site files this installer left on the box are gone, and all 11 other sites still answer."
t "apart from the backups, the fake root is exactly as before the first install" snap_same_ignoring_backups "$PRISTINE"
AFTER_P3="$C/after-p3.snap"
snap >"$AFTER_P3"
run_script rollback
t "a third rollback finds nothing" has "$OUT" "RESULT: DONE, nothing to roll back, because nothing from this installer is on the box."
t "and changes nothing" snap_same_as "$AFTER_P3"

new_case P4-site-files-changed-after-install
run_script stage
t "stage exits 0" eq "$RC" 0
echo "<!-- edited by hand -->" >>"$R/opt/devon/static/tqohq/index.html"
EDITED_SHA=$(index_sha_of tqohq)
AFTER_EDIT="$C/after-edit.snap"
snap >"$AFTER_EDIT"
run_script stage
t "stage again refuses: the folder is no longer what the installer made" has "$OUT" "because a folder $R/opt/devon/static/tqohq is already on the box and this installer did not make it (or it was changed after it did)"
t "and changes nothing" snap_same_as "$AFTER_EDIT"
run_script rollback
t "rollback exits 0" eq "$RC" 0
t "rollback takes the block out and says it left the folder" has "$OUT" "RESULT: DONE, the tqohq Caddy block is gone and all 11 other sites still answer. The folder $R/opt/devon/static/tqohq was left as it is, because this installer did not make it (or it was changed after it did)."
t "the edited folder is still there, as edited" eq "$(index_sha_of tqohq)" "$EDITED_SHA"
t "the Caddyfile is the exact pre-install bytes" same_file "$CF" "$C/pristine.Caddyfile"
t "no record is left claiming the edited folder" test ! -e "$(RECORD_OF)"

new_case Q-interrupted-mid-run
export FAKE_TLS_DOWN="$STAGE"
CERT_WAIT=40
RUN_N=$((RUN_N + 1))
OUT="$C/out.$RUN_N.stage"
DOCKER_MARK=0
TQOHQ_TEST_ROOT="$R" TQOHQ_DOCKER="$HERE/fake-docker" TQOHQ_CURL="$HERE/fake-curl" TQOHQ_GETENT="$HERE/fake-getent" \
	TMPDIR="$S/tmp" TQOHQ_CERT_WAIT_S="$CERT_WAIT" bash "$SCRIPT" stage >"$OUT" 2>&1 &
BGPID=$!
for _ in $(seq 1 300); do
	if grep -q "https://$STAGE/" "$S/curl.log" || ! kill -0 "$BGPID" 2>/dev/null; then break; fi
	sleep 0.1
done
sleep 1
kill -TERM "$BGPID" 2>/dev/null || true
set +e
wait "$BGPID"
RC=$?
set -e
after_run "stage (sent SIGTERM while it waited for the certificate)"
t "exit 130" eq "$RC" 130
t "RESULT says it was interrupted and put back" has "$OUT" "RESULT: FAILED, and the box was put back exactly as it was, because the script was interrupted while checking the new address answers."
t "the Caddyfile is restored byte for byte" same_file "$CF" "$C/pristine.Caddyfile"
t "the whole fake root is exactly as before" snap_same_as "$PRISTINE"
t "the stage name is not served any more" eq "$(code_of "$STAGE")" 000
t "the other sites answer as before" other_sites_as_before

new_case R-hangup-ignored-and-certificate-pending
export FAKE_TLS_DOWN="$STAGE"
CERT_WAIT=6
RUN_N=$((RUN_N + 1))
OUT="$C/out.$RUN_N.stage"
TQOHQ_TEST_ROOT="$R" TQOHQ_DOCKER="$HERE/fake-docker" TQOHQ_CURL="$HERE/fake-curl" TQOHQ_GETENT="$HERE/fake-getent" \
	TMPDIR="$S/tmp" TQOHQ_CERT_WAIT_S="$CERT_WAIT" bash "$SCRIPT" stage >"$OUT" 2>&1 &
BGPID=$!
for _ in $(seq 1 300); do
	if grep -q "https://$STAGE/" "$S/curl.log" || ! kill -0 "$BGPID" 2>/dev/null; then break; fi
	sleep 0.1
done
kill -HUP "$BGPID" 2>/dev/null || true
set +e
wait "$BGPID"
RC=$?
set -e
after_run "stage (sent SIGHUP, and the stage name has no certificate yet)"
t "exit 0: the hangup did not stop it" eq "$RC" 0
t "RESULT says installed, certificate still being issued" has "$OUT" "RESULT: DONE, the stage page is installed at https://$STAGE and all 11 other sites still answer, but the certificate for $STAGE is still being issued, so wait five minutes before opening https://$STAGE on your iPhone, and run the status line if it still warns."
t "the page was proven over a connection opened for another site" grep -q -- "-H Host:\\\\ $STAGE" "$S/curl.log"
t "the site is actually served" eq "$(body_sha "$STAGE" /)" "$INDEX_SHA"
t "one block" eq "$(count_line "$CF" "$BEGIN_MARK")" 1
run_script status
t "status while the certificate is pending says so, not that the page is broken" has "$OUT" "RESULT: Stage is installed, but the certificate for $STAGE is still being issued, so wait five minutes and paste the status line again."
unset FAKE_TLS_DOWN
CERT_WAIT=20
run_script status
t "status once the certificate exists says working" has "$OUT" "RESULT: Stage is installed and working"

new_case S-seams-cannot-be-triggered-by-accident
RUN_N=$((RUN_N + 1))
OUT="$C/out.$RUN_N.status"
DOCKER_MARK=$(wc -l <"$S/docker.log")
CURL_MARK=$(wc -l <"$S/curl.log")
set +e
env -u TQOHQ_TEST_ROOT TQOHQ_DOCKER="$HERE/fake-docker" TQOHQ_CURL="$HERE/fake-curl" TQOHQ_GETENT="$HERE/fake-getent" \
	TMPDIR="$S/tmp" bash "$SCRIPT" status >"$OUT" 2>&1
RC=$?
set -e
after_run "status (fake commands named, but no TQOHQ_TEST_ROOT)"
t "exit 1" eq "$RC" 1
t "it says the test settings were ignored" has "$OUT" "- note: TQOHQ_ test settings are ignored outside a test root"
t "the fake docker was never called" eq "$(wc -l <"$S/docker.log")" "$DOCKER_MARK"
t "the fake curl was never called" eq "$(wc -l <"$S/curl.log")" "$CURL_MARK"
t "RESULT is a plain could-not-check" grep -q '^RESULT: Could not check, because ' "$OUT"
RUN_N=$((RUN_N + 1))
OUT="$C/out.$RUN_N.stage"
mkdir -p "$C/not-a-test-root"
set +e
TQOHQ_TEST_ROOT="$C/not-a-test-root" TQOHQ_DOCKER="$HERE/fake-docker" TMPDIR="$S/tmp" bash "$SCRIPT" stage >"$OUT" 2>&1
RC=$?
set -e
after_run "stage (TQOHQ_TEST_ROOT names a folder with no marker)"
t "exit 2" eq "$RC" 2
t "RESULT refuses to run" has "$OUT" "RESULT: NOT DONE, nothing on the box was changed, because TQOHQ_TEST_ROOT is set but does not name a test root; unset it and paste the line again."
t "the fake docker was never called" eq "$(wc -l <"$S/docker.log")" "$DOCKER_MARK"
t "nothing changed in the fake root" snap_same_as "$PRISTINE"

new_case T-real-github-download
export FAKE_RAW_MODE=real
RAW_LOG_MARK=$(wc -l <"$WORKDIR/raw.log")
run_script stage
t "the local file server was not asked for anything" eq "$(wc -l <"$WORKDIR/raw.log")" "$RAW_LOG_MARK"
if [[ "$RC" == 1 ]] && grep -q 'could not be downloaded from GitHub' "$OUT"; then
	skip "raw.githubusercontent.com was not reachable from here, so the real download was not proven"
else
	t "exit 0 with the files fetched from raw.githubusercontent.com at the pinned commit" eq "$RC" 0
	t "the four files it placed match the pins" site_files_match_pins
fi

new_case SP1-output-cut-off-part-way
# Tee's terminal is not the only way output can go away: a piped stdout whose
# reader stops. The first write after that raised SIGPIPE, which killed bash
# before its undo ran and left a block that was never validated or reloaded.
# Now the writes fail quietly and the run finishes on its own.
RUN_N=$((RUN_N + 1))
OUT="$C/out.$RUN_N.stage"
DOCKER_MARK=$(wc -l <"$S/docker.log")
set +e
env TQOHQ_TEST_ROOT="$R" TQOHQ_DOCKER="$HERE/fake-docker" TQOHQ_CURL="$HERE/fake-curl" TQOHQ_GETENT="$HERE/fake-getent" \
	TMPDIR="$S/tmp" TQOHQ_CERT_WAIT_S="$CERT_WAIT" bash "$UNDER_TEST" stage 2>&1 |
	{
		while IFS= read -r line; do
			printf '%s\n' "$line"
			if [[ "$line" == *"site files in place"* ]]; then break; fi
		done
	} >"$OUT"
RCS=("${PIPESTATUS[@]}")
set -e
RC="${RCS[0]}"
show_run "stage, with its output cut off after the first change"
ALL_OUTPUTS+=("$OUT")
t "the output really was cut off after the first change" eq "$(tail -n 1 "$OUT")" "- site files in place at $R/opt/devon/static/tqohq"
t "the closed pipe did not kill it: exit 0, not 141" eq "$RC" 0
t "the install finished: exactly one block" eq "$(count_line "$CF" "$BEGIN_MARK") $(count_line "$CF" "$END_MARK")" "1 1"
t "the block is exactly the expected stage block" eq "$(block_of "$CF")" "$EXPECTED_STAGE_BLOCK"
t "Caddy was reloaded once, onto the new block" eq "$(reloads_since_mark)" 1
t "served: the stage page" eq "$(body_sha "$STAGE" /)" "$INDEX_SHA"
t "one backup, and the record" eq "$(backups | wc -l) $(record_names)" "1 tqohq "
t "no build leftovers" no_build_leftovers
t "its private temp folder is gone (it held a copy of the Caddyfile)" eq "$(find "$S/tmp" -mindepth 1 | wc -l)" 0
t "no fake saw an unexpected call" eq "$(wc -l <"$S/unexpected.log")" 0
t "the other sites answer as before" other_sites_as_before

add_neighbour_on_the_folder() {
	printf '\ntqohq.editforge.online {\n\troot * /srv/static/tqohq\n\tfile_server\n}\n' >>"$CF"
}
new_case NB1-another-site-serves-the-folder add_neighbour_on_the_folder
NB_BEFORE="$(code_of tqohq.editforge.online) $(body_sha tqohq.editforge.online /)"
run_script stage
t "exit 1" eq "$RC" 1
t "RESULT refuses: another site serves the folder" has "$OUT" "RESULT: NOT DONE, nothing on the box was changed, because another site in the Caddyfile already serves /srv/static/tqohq, and installing or rolling back would replace its files."
t "nothing changed in the fake root" snap_same_as "$PRISTINE"
t "the neighbour answers exactly as before, not with the TQO page" eq "$(code_of tqohq.editforge.online) $(body_sha tqohq.editforge.online /)" "$NB_BEFORE"

add_neighbour_through_a_snippet() {
	printf '\n(static_site) {\n\troot * /srv/static/{args[0]}\n\tfile_server\n}\n\ntqohq.editforge.online {\n\timport static_site tqohq\n}\n' >>"$CF"
}
new_case NB2-another-site-serves-the-folder-through-a-snippet add_neighbour_through_a_snippet
t "the fixture never spells the folder out" hasnt "$CF" "/srv/static/tqohq"
run_script stage
t "exit 1" eq "$RC" 1
t "RESULT refuses: another site serves the folder (seen in Caddy's adapted config)" has "$OUT" "because another site in the Caddyfile already serves /srv/static/tqohq, and installing or rolling back would replace its files."
t "nothing changed in the fake root" snap_same_as "$PRISTINE"

add_comment_about_the_folder() {
	printf '\n# The old landing page was served from /srv/static/tqohq; ask before reusing it.\n' >>"$CF"
}
new_case NB3-the-folder-mentioned-in-a-comment add_comment_about_the_folder
# Nothing serves the folder, so only the text check can see this. A note in
# the Caddyfile about the folder is a reason to ask first, the same way a
# note naming one of the three hosts already is.
run_script stage
t "exit 1" eq "$RC" 1
t "RESULT refuses on the mention" has "$OUT" "because another site in the Caddyfile already serves /srv/static/tqohq, and installing or rolling back would replace its files."
t "nothing changed in the fake root" snap_same_as "$PRISTINE"

add_site_for_two_of_the_names() {
	printf '\ntqohq-stage.editforge.online, tqohq.online {\n\trespond "someone else" 200\n}\n' >>"$CF"
}
new_case X-two-of-the-names-already-served add_site_for_two_of_the_names
# Two names at once: the check used to take the first of the list through a
# pipe into head, which could break the pipe and stop the run for the wrong
# reason.
run_script stage
t "exit 1" eq "$RC" 1
t "RESULT names the first name taken" has "$OUT" "RESULT: NOT DONE, nothing on the box was changed, because the Caddyfile already mentions $STAGE outside this script's block, and two blocks for one name would clash."
t "nothing changed in the fake root" snap_same_as "$PRISTINE"
run_script status
t "status names both, readably" has "$OUT" "RESULT: Not installed by this script, but the Caddyfile serves $STAGE and $APEX some other way; send this line to Claude."

new_case LK-one-run-at-a-time
# The phone drops, the run carries on unseen, and the line gets pasted again.
export FAKE_TLS_DOWN="$STAGE"
CERT_WAIT=8
start_bg stage "$S/tmp-first"
FIRST_PID=$BGPID
FIRST_OUT=$BG_OUT
wait_for_cert_wait
run_script stage
t "a second stage run while the first is going: exit 1" eq "$RC" 1
t "it says another run is going and to paste the status line" has "$OUT" "RESULT: NOT DONE, nothing on the box was changed, because another run of this installer is still going on the box, so wait a minute and then paste the status line."
t "it changed nothing and reloaded nothing" eq "$(reloads_since_mark) $(backups | wc -l)" "0 1"
t "it never asked docker to run anything in the edge" eq "$(docker_calls_since_mark | grep -c '^exec' || true)" 0
run_script status
t "status while the first run is going: exit 1" eq "$RC" 1
t "status says the same" has "$OUT" "RESULT: Could not check, because another run of this installer is still going on the box, so wait a minute and then paste the status line."
set +e
wait "$FIRST_PID"
RC=$?
set -e
OUT="$FIRST_OUT"
RUN_TMPDIR="$S/tmp-first"
after_run "stage (the first run, left to finish)"
RUN_TMPDIR=""
t "the first run finished: exit 0" eq "$RC" 0
t "and its RESULT is right" has "$OUT" "RESULT: DONE, the stage page is installed at https://$STAGE and all 11 other sites still answer, but the certificate for $STAGE is still being issued"
t "exactly one block, one backup" eq "$(count_line "$CF" "$BEGIN_MARK") $(backups | wc -l)" "1 1"
unset FAKE_TLS_DOWN
CERT_WAIT=20
run_script status
t "once it is done, status works again" has "$OUT" "RESULT: Stage is installed and working"

new_case G3-another-site-changes-its-answer
# Not dark, just different: the proxy behind rakazo answers 502 after the
# reload where it answered 200. That used to pass as "still answers".
export FAKE_502_HOST=rakazo.editforge.online
run_script stage
t "exit 1" eq "$RC" 1
t "RESULT names the site and both answers, and it was put back" has "$OUT" "RESULT: FAILED, and the box was put back exactly as it was, because rakazo.editforge.online answered HTTP 502 after the reload, where it answered 200 before."
t "the whole fake root is exactly as before" snap_same_as "$PRISTINE"
t "Caddy was reloaded twice: the change, then the restore" eq "$(reloads_since_mark)" 2
t "rakazo answers 200 again" eq "$(code_of rakazo.editforge.online)" 200
t "the other sites answer as before" other_sites_as_before

new_case W-some-sites-already-dark
# Two sites give no answer before the script runs. The RESULT must not count
# them in "all".
export FAKE_TLS_DOWN="hud.editforge.online rakazo.editforge.online"
run_script stage
t "exit 0" eq "$RC" 0
t "RESULT counts 9 of 11 and names the two that were already dark" has "$OUT" "RESULT: DONE, the stage page is installed at https://$STAGE and 9 of the 11 other sites still answer as before (hud.editforge.online and rakazo.editforge.online did not answer before this ran either), with a valid certificate"
t "it does not say all" hasnt "$OUT" "all 9 other sites"

add_strict_sni_host() {
	awk -v p="$HTTPS_PORT" '{ print } $0 == "\tskip_install_trust" { print "\tservers :" p " {"; print "\t\tstrict_sni_host on"; print "\t}" }' "$CF" >"$C/cf.tmp"
	cat "$C/cf.tmp" >"$CF"
}
new_case SN1-strict-sni-host-and-a-pending-certificate add_strict_sni_host
t "the fixture switches strict_sni_host on" grep -q 'strict_sni_host on' "$CF"
export FAKE_TLS_DOWN="$STAGE"
CERT_WAIT=6
run_script stage
t "exit 0: a late certificate is not a failed install" eq "$RC" 0
t "RESULT says installed, the page could not be fetched yet" has "$OUT" "RESULT: DONE, the stage page is installed at https://$STAGE and all 11 other sites still answer, but $STAGE could not be fetched yet because its certificate is still being issued, so run the status line in five minutes."
t "the Host-header fallback really gets 421 on this server" eq "$(curl --noproxy '*' -sS -k -o /dev/null -w '%{http_code}' -H "Host: $STAGE" --resolve "editforge.online:$HTTPS_PORT:127.0.0.1" "https://editforge.online:$HTTPS_PORT/" 2>/dev/null || true)" 421
t "one block" eq "$(count_line "$CF" "$BEGIN_MARK")" 1
run_script status
t "status says the page could not be fetched yet, and to wait" has "$OUT" "RESULT: Stage is installed, but $STAGE could not be fetched yet, most likely because its certificate is still being issued, so wait five minutes and paste the status line again."
unset FAKE_TLS_DOWN
CERT_WAIT=20
run_script status
t "status once the certificate exists says working" has "$OUT" "RESULT: Stage is installed and working at https://$STAGE with a valid certificate."

new_case CR2-the-file-saved-with-crlf-after-install
run_script stage
t "stage exits 0" eq "$RC" 0
sed 's/$/\r/' "$CF" >"$C/crlf.tmp"
cat "$C/crlf.tmp" >"$CF"
edge_reload
t "the edge runs the CRLF file and still serves the stage page" eq "$(body_sha "$STAGE" /)" "$INDEX_SHA"
run_script status
t "status still finds the block" has "$OUT" "- Caddy block: present, for $STAGE"
t "and says stage is working" has "$OUT" "RESULT: Stage is installed and working"
run_script rollback
t "rollback exits 0" eq "$RC" 0
t "RESULT says the block and files are gone" has "$OUT" "RESULT: DONE, the tqohq Caddy block and site files are gone and all 11 other sites still answer."
t "no marker line is left" eq "$(grep -c 'tqohq managed by install-on-vps.sh' "$CF" || true)" 0
sed 's/$/\r/' "$C/pristine.Caddyfile" >"$C/pristine-crlf.Caddyfile"
t "the Caddyfile is the original, in its CRLF form, byte for byte" same_file "$CF" "$C/pristine-crlf.Caddyfile"
t "served: the stage name is gone" eq "$(code_of "$STAGE")" 000
t "the other sites answer as before" other_sites_as_before

strip_final_newline() {
	printf '%s' "$(cat "$CF")" >"$C/cf.tmp"
	cat "$C/cf.tmp" >"$CF"
}
new_case NL1-no-line-break-at-the-end strip_final_newline
t "the fixture ends without a line break" eq "$(tail -c 1 "$CF" | wc -l)" 0
run_script stage
t "stage exits 0" eq "$RC" 0
t "the block records the line break it added" eq "$(count_line "$CF" "# The Caddyfile had no line break at its end, so install-on-vps.sh added one before this block; rollback takes it out again.")" 1
t "everything before the block is the original, plus that one line break" eq "$(head -c "$(stat -c %s "$C/pristine.Caddyfile")" "$CF" | sha256sum) $(tail -c +"$(($(stat -c %s "$C/pristine.Caddyfile") + 1))" "$CF" | head -c 1 | od -An -c | tr -d ' ')" "$(sha256sum <"$C/pristine.Caddyfile") \\n"
t "the block is caddy fmt clean" block_is_fmt_clean
run_script rollback
t "rollback exits 0" eq "$RC" 0
t "the Caddyfile is the exact original bytes, with no line break added" same_file "$CF" "$C/pristine.Caddyfile"
run_script stage
t "stage again exits 0" eq "$RC" 0
printf '%s\n' "$STAGE A $BOX_IP" "$APEX A $BOX_IP" "$WWW A $BOX_IP" >"$S/dns"
run_script live
t "live over it exits 0" eq "$RC" 0
t "the live block still records the added line break" eq "$(count_line "$CF" "# The Caddyfile had no line break at its end, so install-on-vps.sh added one before this block; rollback takes it out again.")" 1
run_script rollback
t "rollback from live exits 0" eq "$RC" 0
t "the Caddyfile is the exact original bytes again" same_file "$CF" "$C/pristine.Caddyfile"
t "apart from the backups, the fake root is exactly as before" snap_same_ignoring_backups "$PRISTINE"

new_case V-dns-lookup-services-down
export FAKE_DOH_DOWN=1
run_script stage
t "exit 1" eq "$RC" 1
t "RESULT refuses because the AAAA check could not run" has "$OUT" "RESULT: NOT DONE, nothing on the box was changed, because the IPv6 (AAAA) records for $STAGE could not be checked (neither DNS lookup service answered), so paste the line again in a few minutes."
t "nothing changed in the fake root" snap_same_as "$PRISTINE"
printf '%s\n' "$STAGE A $BOX_IP" "$APEX A $BOX_IP" "$WWW A $BOX_IP" >"$S/dns"
run_script live
t "live refuses the same way" has "$OUT" "because the IPv6 (AAAA) records for $APEX could not be checked (neither DNS lookup service answered)"
t "nothing changed in the fake root" snap_same_as "$PRISTINE"

new_case VS-caddy-check-gives-no-answer
# What a full temporary disk, or a docker exec that fails, looks like: the
# check fails and says nothing. That is not an invalid Caddyfile.
export FAKE_VALIDATE_FAIL=silent
run_script stage
t "exit 1" eq "$RC" 1
t "RESULT says the check gave no answer" has "$OUT" "RESULT: NOT DONE, nothing on the box was changed, because Caddy's check of the current Caddyfile failed without saying why, which means docker exec did not work or $S/tmp is full, not that the Caddyfile is wrong."
t "it does not blame the Caddyfile" hasnt "$OUT" "already invalid"
t "it prints no empty Caddy said line" hasnt "$OUT" "Caddy said:"
t "nothing changed in the fake root" snap_same_as "$PRISTINE"

new_case DF1-temporary-disk-full
if small_tmpfs "$C/fulltmp" 64k; then
	mkdir "$C/fulltmp/tmp"
	dd if=/dev/zero of="$C/fulltmp/filler" bs=1k count=128 2>/dev/null || true
	RUN_TMPDIR="$C/fulltmp/tmp"
	run_script stage
	RUN_TMPDIR=""
	t "exit 1" eq "$RC" 1
	t "RESULT says the temporary disk is full" has "$OUT" "RESULT: NOT DONE, nothing on the box was changed, because there is not enough free disk space in $C/fulltmp/tmp (0 KB free, at least 1024 KB are needed), so space has to be cleared there first."
	t "it does not blame the Caddyfile" hasnt "$OUT" "already invalid"
	t "nothing changed in the fake root" snap_same_as "$PRISTINE"
	umount "$C/fulltmp"
else
	skip "DF1: this container may not mount a tmpfs, so a full temporary disk was not tried"
fi

new_case DF2-static-disk-nearly-full
"$HERE/fake-docker" __stop-edge
cp -a "$R/opt/devon/static" "$C/static.save"
if small_tmpfs "$R/opt/devon/static" 512k; then
	cp -a "$C/static.save/." "$R/opt/devon/static/"
	"$HERE/fake-docker" __start-edge
	snap >"$PRISTINE"
	run_script stage
	t "exit 1" eq "$RC" 1
	t "RESULT says the static folder's disk is short of space" has "$OUT" "RESULT: NOT DONE, nothing on the box was changed, because there is not enough free disk space in $R/opt/devon/static ("
	t "nothing changed in the fake root" snap_same_as "$PRISTINE"
	"$HERE/fake-docker" __stop-edge
	umount "$R/opt/devon/static"
else
	skip "DF2: this container may not mount a tmpfs, so a nearly full static disk was not tried"
fi
"$HERE/fake-docker" __start-edge

new_case U-the-paste-lines
# The one line Tee pastes, exactly as the README gives it, with only the
# GitHub address pointed at the local file server and the two placeholders
# filled in. Under bash and under dash, as a root shell's sh may be either.
mapfile -t PASTE < <(grep '^f=\$(mktemp)' "$HERE/../README.md")
t "the README has four paste lines" eq "${#PASTE[@]}" 4
t "they differ only in the mode" eq "$(printf '%s\n' "${PASTE[@]}" | sed -E 's/bash "\$f" (stage|live|rollback|status);/bash "$f" MODE;/' | sort -u | wc -l)" 1
t "each checks the installer's sha256 before running it" eq "$(printf '%s\n' "${PASTE[@]}" | grep -c 'echo "SCRIPT_SHA256  $f" | sha256sum -c --quiet')" 4
STATUS_LINE=$(printf '%s\n' "${PASTE[@]}" | grep 'bash "$f" status;')
GH_URL="https://raw.githubusercontent.com/tdveal74-cell/Meta-Supreme-Apex-Genesis-/SCRIPT_COMMIT/sites/tqohq/deploy/install-on-vps.sh"
t "the status line downloads from the pinned-commit address" grep -q -F -- "$GH_URL" <<<"$STATUS_LINE"
paste_run() { # paste_run SHELL VARIANT SHA
	local line="${STATUS_LINE//"$GH_URL"/"http://127.0.0.1:$RAW_PORT/paste/$2/install-on-vps.sh"}"
	line="${line//SCRIPT_SHA256/$3}"
	RUN_N=$((RUN_N + 1))
	OUT="$C/out.$RUN_N.paste-$1-$2"
	set +e
	env no_proxy=127.0.0.1 NO_PROXY=127.0.0.1 TQOHQ_TEST_ROOT="$R" TQOHQ_DOCKER="$HERE/fake-docker" TQOHQ_CURL="$HERE/fake-curl" \
		TQOHQ_GETENT="$HERE/fake-getent" TMPDIR="$S/tmp" TQOHQ_CERT_WAIT_S="$CERT_WAIT" "$1" -c "$line" >"$OUT" 2>&1
	RC=$?
	set -e
	after_run "the status paste line under $1, download: $2"
}
NOT_FETCHED="RESULT: NOT DONE, nothing on the box was changed, because the installer could not be downloaded from GitHub, or it did not match its pinned fingerprint."
for sh in bash dash; do
	if ! command -v "$sh" >/dev/null 2>&1; then
		skip "$sh is not installed here, so the paste lines were not run under it"
		continue
	fi
	paste_run "$sh" good "$SCRIPT_SHA"
	t "$sh, the real installer: it runs, and status answers" has "$OUT" "RESULT: Nothing from this installer is on the box."
	paste_run "$sh" good SCRIPT_SHA256
	t "$sh, the placeholder never filled in: refused, nothing run" eq "$(tail -n 1 "$OUT")" "$NOT_FETCHED"
	paste_run "$sh" good "$(printf 'x' | sha256sum | awk '{print $1}')"
	t "$sh, the wrong fingerprint: refused, nothing run" eq "$(tail -n 1 "$OUT")" "$NOT_FETCHED"
	paste_run "$sh" html "$SCRIPT_SHA"
	t "$sh, an HTML page answered 200: refused, never handed to bash" eq "$(tail -n 1 "$OUT")" "$NOT_FETCHED"
	t "$sh, an HTML page answered 200: no syntax error from bash" hasnt "$OUT" "syntax error"
	paste_run "$sh" empty "$SCRIPT_SHA"
	t "$sh, an empty 200: refused" eq "$(tail -n 1 "$OUT")" "$NOT_FETCHED"
	paste_run "$sh" missing "$SCRIPT_SHA"
	t "$sh, a 404: refused" eq "$(tail -n 1 "$OUT")" "$NOT_FETCHED"
done
t "none of the paste runs changed the fake root" snap_same_as "$PRISTINE"

# ---------------------------------------------------------------------------
echo
echo "== Z: the Caddyfile never reached the output"
LEAKS=0
for o in "${ALL_OUTPUTS[@]}"; do
	if grep -q -F -- "$BCRYPT" "$o" || grep -q -F -- "fixture-only-marker-7f3a9c" "$o" ||
		grep -q -F -- "reverse_proxy 127.0.0.1" "$o" || grep -q -F -- 'basic_auth {' "$o" ||
		grep -q -F -- "$BEGIN_MARK" "$o"; then
		LEAKS=$((LEAKS + 1))
		echo "    leak in $o"
	fi
done
CASE=Z
t "no run printed the bcrypt hash, the fixture's marker comment, a fixture directive or a block line (${#ALL_OUTPUTS[@]} runs scanned)" eq "$LEAKS" 0
t "the hash really is in the fixture, so the scan can find it" grep -q -F -- "$BCRYPT" "$WORKDIR/cases/A-fresh-stage-install/pristine.Caddyfile"

echo
echo "== summary: $PASSN passed, $FAILN failed, $SKIPN skipped"
if ((FAILN)); then
	printf '  failed: %s\n' "${FAILED[@]}"
	exit 1
fi
