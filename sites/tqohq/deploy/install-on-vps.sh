#!/usr/bin/env bash
# install-on-vps.sh: serve the TQO home page from the EditForge VPS, through
# the Caddy edge container that already serves every *.editforge.online site
# on that box.
#
#   bash install-on-vps.sh stage     serve it at https://tqohq-stage.editforge.online only
#   bash install-on-vps.sh live      serve it at https://tqohq.online, send
#                                    www.tqohq.online there, keep the stage address
#   bash install-on-vps.sh rollback  take this script's Caddy block out and put
#                                    the site folder back as it was
#   bash install-on-vps.sh status    change nothing, say what is installed
#
# Run it as root on the VPS. The last line it prints always starts "RESULT:".
#
# What it promises:
#   - Every check runs before anything on the box changes.
#   - The host Caddyfile is rewritten in place, keeping its inode, because the
#     edge mounts it as a single file and would keep reading a replaced one.
#   - The Caddyfile is never printed, never copied anywhere another user can
#     read it, and never sent off the box.
#   - It only moves or deletes a site folder it made itself, and it proves
#     that from a record it keeps beside the Caddyfile, never from a name.
#   - One run at a time: a run that finds another one going stops at once.
#   - A failure after a change puts the box back exactly as it was.
#
# The harness in test/ runs this against a fake root. Its seams are honoured
# only when TQOHQ_TEST_ROOT names a directory holding a .tqohq-fake-root file.

# The awk and sed programs below are single quoted on purpose.
# shellcheck disable=SC2016

set -euo pipefail
shopt -s inherit_errexit
umask 077
export LC_ALL=C

# ---------------------------------------------------------------------------
# What gets installed. Pinned: a change here is a new commit of this script.
# ---------------------------------------------------------------------------
SITE_REPO="tdveal74-cell/Meta-Supreme-Apex-Genesis-"
SITE_COMMIT="64f997279fb430be030c2146e917312266c1fe4f"
RAW_BASE="https://raw.githubusercontent.com/${SITE_REPO}/${SITE_COMMIT}/sites/tqohq"
# path, bytes, sha256
SITE_FILES=(
	"index.html 26486 a00f6ababd65a79b674bae3178889cce099c9464b20f7ae50b0530fc72ba5970"
	"privacy.html 11691 f7ee9cc9166885e4f4b1f675caf31d8819fb38cf60d36ddc5872e958274eb5a9"
	"fonts/atkinson-hyperlegible-next-latin.woff2 33996 18b2a1a39a2fa298b0ba5390aca68462669826c90925656f1c1f6796e0e1bbaf"
	"fonts/OFL-atkinson-hyperlegible-next.txt 4431 aca6a428580965d2297d1b718042dd427c2a9443ece3b0d02d758e161e0c4030"
)
INDEX_SHA256="a00f6ababd65a79b674bae3178889cce099c9464b20f7ae50b0530fc72ba5970"
SITE_LISTING=$'d fonts\nf fonts/OFL-atkinson-hyperlegible-next.txt\nf fonts/atkinson-hyperlegible-next-latin.woff2\nf index.html\nf privacy.html'

STAGE_HOST="tqohq-stage.editforge.online"
APEX_HOST="tqohq.online"
WWW_HOST="www.tqohq.online"

BEGIN_MARK="# BEGIN tqohq managed by install-on-vps.sh"
END_MARK="# END tqohq"
# Written inside the block when the Caddyfile had no line break at its very
# end, so the line break this script adds before its block can come out again
# on rollback.
NEWLINE_NOTE="# The Caddyfile had no line break at its end, so install-on-vps.sh added one before this block; rollback takes it out again."

CTR_CADDYFILE="/etc/caddy/Caddyfile"
CTR_STATIC="/srv/static"
SITE_DIR="tqohq"
PREV_DIR="tqohq.prev"
# A reference to the site folder, or to the previous copy, anywhere in a
# Caddyfile or in Caddy's adapted config. tqohq-other or tqohq.old do not match.
FOLDER_RE="${CTR_STATIC}/${SITE_DIR}"'(\.prev)?([^A-Za-z0-9._-]|$)'
# Beside the Caddyfile: which site folders this installer made, with a
# fingerprint of each.
RECORD_SUFFIX=".tqohq-record"
# Free space wanted on each filesystem the script writes to, in KB.
MIN_FREE_KB=1024

# ---------------------------------------------------------------------------
# Seams. Real commands unless a test root is named and marked.
# ---------------------------------------------------------------------------
DOCKER="docker"
CURL="curl"
GETENT="getent"
IF_INET6="/proc/net/if_inet6"
CERT_WAIT_S=90
TEST_ROOT=""
SEAM_NOTE=""

if [[ -n "${TQOHQ_TEST_ROOT:-}" ]]; then
	if [[ "$TQOHQ_TEST_ROOT" == /* && "$TQOHQ_TEST_ROOT" != "/" && -d "$TQOHQ_TEST_ROOT" && -f "$TQOHQ_TEST_ROOT/.tqohq-fake-root" ]]; then
		TEST_ROOT="${TQOHQ_TEST_ROOT%/}"
		DOCKER="${TQOHQ_DOCKER:-docker}"
		CURL="${TQOHQ_CURL:-curl}"
		GETENT="${TQOHQ_GETENT:-getent}"
		IF_INET6="$TEST_ROOT/proc/net/if_inet6"
		if [[ "${TQOHQ_CERT_WAIT_S:-}" =~ ^[0-9]+$ ]]; then
			CERT_WAIT_S="$TQOHQ_CERT_WAIT_S"
		fi
	else
		printf '%s\n' "RESULT: NOT DONE, nothing on the box was changed, because TQOHQ_TEST_ROOT is set but does not name a test root; unset it and paste the line again."
		exit 2
	fi
elif [[ -n "${TQOHQ_DOCKER:-}${TQOHQ_CURL:-}${TQOHQ_GETENT:-}${TQOHQ_CERT_WAIT_S:-}" ]]; then
	SEAM_NOTE="- note: TQOHQ_ test settings are ignored outside a test root"
fi

# ---------------------------------------------------------------------------
# State for the undo path.
# ---------------------------------------------------------------------------
MODE=""
PHASE="starting"
WORK=""
EDGE_ID=""
CADDYFILE=""
STATIC_SRC=""
CADDYFILE_INODE=""
BEFORE_SUM=""
BLOCK_B=0
BLOCK_E=0
BLOCK_HAS_NL_NOTE=0
ADMIN_ADDR=""
ANCHOR=""
OTHERS_TOTAL=0
OTHERS_ANSWERED=0
DARK_BEFORE=()
LOCK_FD=""
# the installer's record of the folders it made
RECORD=""
RECORD_HAD=0
RECORD_WRITTEN=0
declare -A REC=()
# what is in the static folder now, and whether this installer made it
CUR_EXISTS=0
CUR_OURS=0
CUR_SUM=""
PREV_EXISTS=0
PREV_OURS=0
PREV_SUM=""
RESULT_LINE=""
FAIL_REASON=""
UNDO_DETAIL=""
CHANGED=0
COMMITTED=0
CADDY_WRITTEN=0
RELOAD_TRIED=0
BACKUP_PATH=""
# install side of the site folder
STATIC_NEW=""
PREV_ASIDE=""
PREV_MOVED=0
CUR_TO_PREV=0
NEW_TO_CUR=0
# rollback side of the site folder
CUR_ASIDE=""
CUR_MOVED=0
PREV_RESTORED=0

declare -A BEFORE=()
declare -A PAGE=()
declare -A CERT=()

# Output never stops the script: a closed terminal or a closed pipe makes the
# write fail, and the script carries on (SIGPIPE and SIGHUP are ignored below).
say() { printf '%s\n' "$*" 2>/dev/null || true; }
step() { say "- $*"; }

refuse() {
	if ((CHANGED)); then
		fail "$1"
	fi
	if [[ "$MODE" == status ]]; then
		RESULT_LINE="RESULT: Could not check, because $1."
	else
		RESULT_LINE="RESULT: NOT DONE, nothing on the box was changed, because $1."
	fi
	exit 1
}

fail() {
	FAIL_REASON="$1"
	exit 1
}

on_signal() {
	FAIL_REASON="the script was interrupted while $PHASE"
	exit 130
}

on_exit() {
	local rc=$?
	set +e
	trap - EXIT
	trap '' INT TERM HUP PIPE
	if ((!COMMITTED && CHANGED)); then
		((rc == 0)) && rc=1
		step "putting the box back as it was"
		if undo_all; then
			RESULT_LINE="RESULT: FAILED, and the box was put back exactly as it was, because ${FAIL_REASON:-the script stopped unexpectedly while $PHASE}."
		else
			RESULT_LINE="RESULT: FAILED, and putting the box back did not finish, so do not run anything else and send a screenshot of this screen to Claude; the failure was that ${FAIL_REASON:-the script stopped unexpectedly while $PHASE}. ${UNDO_DETAIL}"
			RESULT_LINE="${RESULT_LINE% }"
		fi
	elif [[ -z "$RESULT_LINE" ]]; then
		((rc == 0)) && rc=1
		if [[ "$MODE" == status ]]; then
			RESULT_LINE="RESULT: Could not check, because ${FAIL_REASON:-the script stopped unexpectedly while $PHASE}."
		else
			RESULT_LINE="RESULT: NOT DONE, nothing on the box was changed, because ${FAIL_REASON:-the script stopped unexpectedly while $PHASE}."
		fi
	fi
	if [[ -n "$WORK" && -d "$WORK" ]]; then
		rm -rf -- "$WORK"
	fi
	say "$RESULT_LINE"
	exit "$rc"
}

trap on_exit EXIT
trap on_signal INT TERM
# A dropped phone connection must not stop the script half way: it finishes,
# and the status line can be run afterwards.
trap '' HUP
# Nor may output that nobody reads any more. With SIGPIPE at its default, the
# first write after the reader of a piped stdout went away killed bash before
# the undo ran, and left the box half changed. Ignored, that write just fails.
trap '' PIPE

# ---------------------------------------------------------------------------
# Small helpers.
# ---------------------------------------------------------------------------
sha256_of() { sha256sum <"$1" | awk '{print $1}'; }

edge() { "$DOCKER" exec "$EDGE_ID" "$@"; }

is_ipv4() {
	local a b c d
	[[ "$1" =~ ^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})$ ]] || return 1
	a=${BASH_REMATCH[1]} b=${BASH_REMATCH[2]} c=${BASH_REMATCH[3]} d=${BASH_REMATCH[4]}
	((10#$a <= 255 && 10#$b <= 255 && 10#$c <= 255 && 10#$d <= 255))
}

# "a", "a and b", "a, b and c"
join_and() {
	local out="" i
	for ((i = 1; i <= $#; i++)); do
		if ((i == 1)); then
			out="${!i}"
		elif ((i == $#)); then
			out+=" and ${!i}"
		else
			out+=", ${!i}"
		fi
	done
	printf '%s' "$out"
}

# Free space, in KB, that the filesystem holding $1 gives an ordinary user
# (root may have a little more; being short of that is already a problem).
free_kb() { stat -f -c '%a %S' -- "$1" 2>/dev/null | awk 'NF == 2 { printf "%.0f\n", int($1 * $2 / 1024) }'; }

need_space() {
	local kb
	kb=$(free_kb "$1") || kb=""
	if [[ ! "$kb" =~ ^[0-9]+$ ]]; then
		refuse "the free disk space in $1 could not be measured"
	fi
	if ((kb < MIN_FREE_KB)); then
		refuse "there is not enough free disk space in $1 ($kb KB free, at least $MIN_FREE_KB KB are needed), so space has to be cleared there first"
	fi
}

# A fingerprint of a folder: every name in it with its type, and the sha256 of
# every file, so any added, removed or edited file changes it.
tree_sum() {
	(
		cd -- "$1" || exit 1
		{
			find . -mindepth 1 -printf '%y %P\n'
			find . -type f -exec sha256sum -- {} +
		} | sort
	) | sha256sum | awk '{print $1}'
}

# Caddy's own error line, with anything that looks like a password hash or a
# long secret replaced. Never the file.
caddy_error_line() {
	local line
	line=$(grep -E '^Error:' "$1" | tail -n 1 || true)
	if [[ -z "$line" ]]; then
		line=$(awk 'NF' "$1" | tail -n 1 || true)
	fi
	line=$(printf '%s' "$line" | sed -E \
		-e 's/\$2[abxy]?\$[0-9]{2}\$[./A-Za-z0-9]{20,}/[hidden]/g' \
		-e 's/\$argon2[a-z]*\$[^ ",]*/[hidden]/g' \
		-e 's/[A-Za-z0-9+\/=._$-]{40,}/[hidden]/g')
	printf '%s' "${line:0:300}"
}

# Flatten JSON into sorted-comparable "path=value" lines. Objects give
# ".key", arrays "[n]". Empty containers print {} or []. Caddy's adapter
# output and its admin API's /config/ carry the same config with object keys
# in a different order (measured on 2.10.2), so they are compared flattened
# and sorted, never byte for byte. < > & and \/ are decoded
# as well, in case an encoder ever escapes them differently.
JSON_FLATTEN_AWK='
function path(   p, k) {
	p = ""
	for (k = 1; k <= d; k++) {
		if (T[k] == "o") p = p "." K[k]; else p = p "[" I[k] "]"
	}
	return p
}
function member() { if (d > 0) N[d]++ }
{ buf = buf $0 "\n" }
END {
	s = buf; n = length(s); i = 1; d = 0; want_key = 0
	while (i <= n) {
		c = substr(s, i, 1)
		if (c == " " || c == "\t" || c == "\n" || c == "\r") { i++; continue }
		if (c == "{" || c == "[") {
			member()
			d++; T[d] = (c == "{") ? "o" : "a"; I[d] = 0; N[d] = 0; K[d] = ""
			want_key = (c == "{")
			i++; continue
		}
		if (c == "}" || c == "]") {
			empty = (N[d] == 0)
			d--
			if (empty) print path() "=" ((c == "}") ? "{}" : "[]")
			want_key = 0
			i++; continue
		}
		if (c == ",") {
			if (T[d] == "a") I[d]++; else want_key = 1
			i++; continue
		}
		if (c == ":") { want_key = 0; i++; continue }
		if (c == "\"") {
			j = i + 1; str = ""
			while (j <= n) {
				ch = substr(s, j, 1)
				if (ch == "\\") { str = str substr(s, j, 2); j += 2; continue }
				if (ch == "\"") break
				str = str ch; j++
			}
			i = j + 1
			gsub(/\\u003[cC]/, "<", str)
			gsub(/\\u003[eE]/, ">", str)
			gsub(/\\u0026/, "\\&", str)
			gsub(/\\\//, "/", str)
			if (d > 0 && T[d] == "o" && want_key) { K[d] = str; continue }
			member()
			print path() "=\"" str "\""
			continue
		}
		j = i
		while (j <= n) {
			ch = substr(s, j, 1)
			if (ch == "," || ch == "}" || ch == "]" || ch == " " || ch == "\t" || ch == "\n" || ch == "\r") break
			j++
		}
		member()
		print path() "=" substr(s, i, j - i)
		i = j
	}
}'

json_flatten() { awk "$JSON_FLATTEN_AWK" | sort; }

# From flattened Caddy JSON, the sites Caddy serves on its HTTP and HTTPS
# ports, as "scheme host" lines. Only top level route host matchers count.
SITES_AWK='
function val(line) { sub(/^[^=]*="/, "", line); sub(/"$/, "", line); return line }
function srv(line) { sub(/^\.apps\.http\.servers\./, "", line); sub(/\.(listen|routes)\[.*$/, "", line); return line }
/^\.apps\.http\.http_port=[0-9]+$/ { hp = substr($0, index($0, "=") + 1); next }
/^\.apps\.http\.https_port=[0-9]+$/ { hsp = substr($0, index($0, "=") + 1); next }
/^\.apps\.http\.servers\.[^.]+\.listen\[[0-9]+\]="/ {
	s = srv($0); port = val($0); sub(/^.*:/, "", port); L[s] = L[s] " " port; next
}
/^\.apps\.http\.servers\.[^.]+\.routes\[[0-9]+\]\.match\[[0-9]+\]\.host\[[0-9]+\]="/ {
	s = srv($0); H[s] = H[s] " " val($0); next
}
END {
	if (hp == "") hp = 80
	if (hsp == "") hsp = 443
	for (s in H) {
		np = split(L[s], ports, " ")
		nh = split(H[s], hosts, " ")
		for (a = 1; a <= np; a++) for (b = 1; b <= nh; b++) {
			if (ports[a] == hsp) print "https " tolower(hosts[b])
			else if (ports[a] == hp) print "http " tolower(hosts[b])
		}
	}
}'

IPV6_HEX_AWK='
function expand(a,   head, tail, hn, tn, fill, out, x, H, Tl) {
	a = tolower(a)
	if (a ~ /[^0-9a-f:]/) return ""
	x = index(a, "::")
	if (x) { head = substr(a, 1, x - 1); tail = substr(a, x + 2) } else { head = a; tail = "" }
	hn = (head == "") ? 0 : split(head, H, ":")
	tn = (tail == "") ? 0 : split(tail, Tl, ":")
	if (!x && hn != 8) return ""
	fill = 8 - hn - tn
	if (fill < 0) return ""
	out = ""
	for (x = 1; x <= hn; x++) out = out sprintf("%4s", H[x])
	for (x = 1; x <= fill; x++) out = out "0000"
	for (x = 1; x <= tn; x++) out = out sprintf("%4s", Tl[x])
	gsub(/ /, "0", out)
	return (length(out) == 32) ? out : ""
}
{ print expand($1) }'

ipv6_hex() { printf '%s\n' "$1" | awk "$IPV6_HEX_AWK"; }

# ---------------------------------------------------------------------------
# Preflight. Nothing here changes the box.
# ---------------------------------------------------------------------------
preflight_basics() {
	PHASE="checking the basics"
	local missing=() cmd
	if ((BASH_VERSINFO[0] < 4)); then
		refuse "it needs bash 4 or newer"
	fi
	if [[ "$(id -u)" != 0 ]]; then
		refuse "it must run as root, so log in as root in the Hostinger terminal and paste the line again"
	fi
	for cmd in "$DOCKER" "$CURL" sha256sum awk sed grep stat mktemp cmp find sort head tail tr flock; do
		if ! command -v "$cmd" >/dev/null 2>&1; then
			missing+=("$cmd")
		fi
	done
	if [[ "$MODE" == stage || "$MODE" == live ]] && ! command -v "$GETENT" >/dev/null 2>&1; then
		missing+=("$GETENT")
	fi
	if ((${#missing[@]})); then
		refuse "these commands are missing on the box: ${missing[*]}"
	fi
	# Everything below keeps its working copies here. A full disk would make
	# those copies empty, and Caddy's answers with them, so check it first
	# rather than blame the Caddyfile later.
	need_space "${TMPDIR:-/tmp}"
	WORK=$(mktemp -d "${TMPDIR:-/tmp}/tqohq-install.XXXXXXXX") || refuse "a private temporary folder could not be made in ${TMPDIR:-/tmp}"
	chmod 700 "$WORK"
}

find_edge() {
	PHASE="finding the edge container"
	local out ids=()
	if ! out=$("$DOCKER" ps --filter "label=com.docker.compose.project=editforge" --filter "label=com.docker.compose.service=edge" --format '{{.ID}}' 2>/dev/null); then
		refuse "docker did not answer, so the edge container could not be found"
	fi
	mapfile -t ids < <(printf '%s\n' "$out" | awk 'NF')
	if ((${#ids[@]} == 0)); then
		refuse "no running EditForge edge container was found (compose project editforge, service edge)"
	fi
	if ((${#ids[@]} > 1)); then
		refuse "${#ids[@]} running EditForge edge containers were found where exactly one was expected"
	fi
	EDGE_ID="${ids[0]}"
	if [[ ! "$EDGE_ID" =~ ^[0-9a-f]{12,64}$ ]]; then
		refuse "docker gave an edge container id this script does not recognise"
	fi
	step "found the edge container ${EDGE_ID:0:12}"
}

find_mounts() {
	PHASE="reading the edge container's mounts"
	local out type src dst
	if ! out=$("$DOCKER" inspect --format '{{range .Mounts}}{{.Type}}{{"\t"}}{{.Source}}{{"\t"}}{{.Destination}}{{"\n"}}{{end}}' "$EDGE_ID" 2>/dev/null); then
		refuse "docker could not describe the edge container's mounts"
	fi
	CADDYFILE=""
	STATIC_SRC=""
	while IFS=$'\t' read -r type src dst; do
		if [[ "$type" == bind && "$dst" == "$CTR_CADDYFILE" ]]; then
			CADDYFILE="$src"
		fi
		if [[ "$type" == bind && "$dst" == "$CTR_STATIC" ]]; then
			STATIC_SRC="${src%/}"
		fi
	done <<<"$out"
	if [[ -z "$CADDYFILE" ]]; then
		refuse "the edge container does not mount $CTR_CADDYFILE from a host file"
	fi
	if [[ -z "$STATIC_SRC" ]]; then
		refuse "the edge container does not mount $CTR_STATIC from a host folder"
	fi
	if [[ "$CADDYFILE" != /* || ! -f "$CADDYFILE" ]]; then
		refuse "the Caddyfile the edge mounts, $CADDYFILE, is not a file on this box"
	fi
	if [[ ! -w "$CADDYFILE" ]]; then
		refuse "the Caddyfile the edge mounts, $CADDYFILE, cannot be written"
	fi
	if [[ "$STATIC_SRC" != /* || "$STATIC_SRC" == "" || ! -d "$STATIC_SRC" ]]; then
		refuse "the static folder the edge mounts, $STATIC_SRC, is not a folder on this box"
	fi
	if [[ -n "$TEST_ROOT" ]]; then
		if [[ "$CADDYFILE" != "$TEST_ROOT"/* || "$STATIC_SRC" != "$TEST_ROOT"/* ]]; then
			refuse "test mode was handed a path outside the test root"
		fi
	fi
	local p
	for p in "$STATIC_SRC/$SITE_DIR" "$STATIC_SRC/$PREV_DIR"; do
		if [[ -L "$p" || (-e "$p" && ! -d "$p") ]]; then
			refuse "$p exists but is not a plain folder"
		fi
	done
	RECORD="$CADDYFILE$RECORD_SUFFIX"
	if [[ -L "$RECORD" || (-e "$RECORD" && ! -f "$RECORD") ]]; then
		refuse "$RECORD exists but is not a plain file"
	fi
	step "Caddyfile: $CADDYFILE"
	step "static folder: $STATIC_SRC"
}

# One run at a time. Two runs at once each checked a box the other was
# changing, and the second one's RESULT could be wrong. The lock is on the
# Caddyfile itself, which every run of this script opens anyway, so nothing
# new is left on the box; it goes when the run ends, however it ends.
take_lock() {
	PHASE="making sure no other run of this installer is going"
	if ! { exec {LOCK_FD}<"$CADDYFILE"; } 2>/dev/null; then
		refuse "the Caddyfile could not be opened to take this installer's lock"
	fi
	if ! flock -n "$LOCK_FD"; then
		refuse "another run of this installer is still going on the box, so wait a minute and then paste the status line"
	fi
}

# The filesystems this run writes to need room, so a full disk stops it before
# any change instead of half way through one.
check_space() {
	PHASE="checking free disk space"
	need_space "$(dirname -- "$CADDYFILE")"
	if [[ "$MODE" == stage || "$MODE" == live ]]; then
		need_space "$STATIC_SRC"
	fi
}

check_container_view() {
	PHASE="checking the edge container reads the same Caddyfile"
	local host_ino ctr_ino host_sum ctr_sum
	host_ino=$(stat -L -c %i -- "$CADDYFILE")
	if ! ctr_ino=$(edge stat -L -c %i "$CTR_CADDYFILE" 2>/dev/null); then
		refuse "the Caddyfile could not be looked at from inside the edge container"
	fi
	ctr_ino=$(printf '%s' "$ctr_ino" | tr -d '[:space:]')
	host_sum=$(sha256_of "$CADDYFILE")
	if ! ctr_sum=$(edge cat "$CTR_CADDYFILE" 2>/dev/null | sha256sum | awk '{print $1}'); then
		refuse "the Caddyfile could not be read from inside the edge container"
	fi
	if [[ "$host_ino" != "$ctr_ino" || "$host_sum" != "$ctr_sum" ]]; then
		refuse "the edge container is reading a different copy of the Caddyfile than the one on disk, so a reload would not see any change; the edge needs a restart by someone who has checked why first"
	fi
}

validate_current() {
	PHASE="checking the current Caddyfile"
	if ! edge caddy validate --config "$CTR_CADDYFILE" --adapter caddyfile >"$WORK/validate.out" 2>&1; then
		# Caddy always says why a Caddyfile is invalid. No words at all means
		# the check itself did not run or its answer was lost, which says
		# nothing about the Caddyfile.
		if ! grep -q '[^[:space:]]' "$WORK/validate.out" 2>/dev/null; then
			refuse "Caddy's check of the current Caddyfile failed without saying why, which means docker exec did not work or ${TMPDIR:-/tmp} is full, not that the Caddyfile is wrong"
		fi
		say "Caddy said: $(caddy_error_line "$WORK/validate.out")"
		refuse "the Caddyfile on the box is already invalid before any change (Caddy's message is on the line above), so it needs fixing first"
	fi
	step "the current Caddyfile is valid"
}

check_running_matches_disk() {
	PHASE="comparing Caddy's running config with the Caddyfile"
	local listen host port
	if ! edge caddy adapt --config "$CTR_CADDYFILE" --adapter caddyfile >"$WORK/adapted.json" 2>"$WORK/adapt.err" || [[ ! -s "$WORK/adapted.json" ]]; then
		refuse "Caddy could not turn the current Caddyfile into its running form, although it had just checked it as valid"
	fi
	json_flatten <"$WORK/adapted.json" >"$WORK/adapted.flat"
	if grep -qx '\.admin\.disabled=true' "$WORK/adapted.flat"; then
		refuse "Caddy's admin endpoint is switched off in the Caddyfile, so Caddy cannot be reloaded without a restart"
	fi
	listen=$(sed -n 's/^\.admin\.listen="\(.*\)"$/\1/p' "$WORK/adapted.flat")
	listen="${listen:-localhost:2019}"
	case "$listen" in
	unix/* | unixgram/*) refuse "Caddy's admin endpoint is on a socket this script cannot read" ;;
	esac
	listen="${listen#tcp/}"
	host="${listen%:*}"
	port="${listen##*:}"
	# busybox wget may try ::1 for "localhost", while Caddy binds its admin
	# listener to 127.0.0.1; Caddy accepts 127.0.0.1 as a Host for a loopback
	# admin address.
	case "$host" in
	"" | localhost | 0.0.0.0 | "[::]" | "::") host="127.0.0.1" ;;
	esac
	ADMIN_ADDR="$host:$port"
	if ! edge wget -q -O - "http://$ADMIN_ADDR/config/" >"$WORK/running.json" 2>/dev/null || [[ ! -s "$WORK/running.json" ]]; then
		refuse "Caddy's running config could not be read inside the edge container"
	fi
	json_flatten <"$WORK/running.json" >"$WORK/running.flat"
	if ! cmp -s "$WORK/adapted.flat" "$WORK/running.flat"; then
		refuse "the Caddyfile on disk holds changes Caddy is not running yet, and a reload would apply those as well"
	fi
	step "Caddy is running exactly what the Caddyfile says"
}

# ---------------------------------------------------------------------------
# The Caddyfile and this script's block in it.
# ---------------------------------------------------------------------------
read_caddyfile() {
	PHASE="reading the Caddyfile"
	local begins ends nb ne
	cat -- "$CADDYFILE" >"$WORK/caddyfile.before" || refuse "the Caddyfile could not be read"
	CADDYFILE_INODE=$(stat -L -c %i -- "$CADDYFILE")
	BEFORE_SUM=$(sha256_of "$WORK/caddyfile.before")
	# The marker lines are matched with any trailing spaces or carriage
	# return, so a file an editor later saved with CRLF line ends still has
	# its block found, and removed.
	begins=$(awk -v m="$BEGIN_MARK" '{ sub(/[ \t\r]+$/, "") } $0 == m { print NR }' "$WORK/caddyfile.before")
	ends=$(awk -v m="$END_MARK" '{ sub(/[ \t\r]+$/, "") } $0 == m { print NR }' "$WORK/caddyfile.before")
	nb=$(printf '%s' "$begins" | awk 'NF' | wc -l)
	ne=$(printf '%s' "$ends" | awk 'NF' | wc -l)
	if ((nb == 0 && ne == 0)); then
		BLOCK_B=0
		BLOCK_E=0
	elif ((nb == 1 && ne == 1 && begins < ends)); then
		BLOCK_B=$begins
		BLOCK_E=$ends
	else
		refuse "the Caddyfile holds a damaged tqohq block (its BEGIN and END marker lines do not pair up)"
	fi
	BLOCK_HAS_NL_NOTE=0
	if ((BLOCK_B)) && awk -v b="$BLOCK_B" -v e="$BLOCK_E" -v m="$NEWLINE_NOTE" \
		'NR > b && NR < e { sub(/[ \t\r]+$/, ""); if ($0 == m) f = 1 } END { exit !f }' "$WORK/caddyfile.before"; then
		BLOCK_HAS_NL_NOTE=1
	fi
	awk -v b="$BLOCK_B" -v e="$BLOCK_E" 'b == 0 || NR < b || NR > e' "$WORK/caddyfile.before" >"$WORK/outside"
}

# Site names inside this script's current block, one per line.
block_hosts() {
	if ((BLOCK_B == 0)); then
		return 0
	fi
	awk -v b="$BLOCK_B" -v e="$BLOCK_E" 'NR > b && NR < e { sub(/[ \t\r]+$/, ""); if ($0 ~ /^[^ \t#][^ \t]* \{$/) print $1 }' "$WORK/caddyfile.before"
}

block_has_host() {
	local names
	names=$(block_hosts)
	grep -qx -F -- "$1" <<<"$names"
}

# The names this script serves that the Caddyfile mentions outside its block.
names_outside() {
	local h pattern
	for h in "$STAGE_HOST" "$APEX_HOST" "$WWW_HOST"; do
		pattern="(^|[^A-Za-z0-9.-])${h//./\\.}([^A-Za-z0-9.-]|$)"
		if grep -Eiq -- "$pattern" "$WORK/outside"; then
			printf '%s\n' "$h"
		fi
	done
}

# Refuse when a name this script serves is mentioned outside its own block.
check_no_conflict() {
	PHASE="checking the Caddyfile for other uses of these names"
	local h
	# The whole list, then its first line: a reader that stops early would
	# break the pipe under names_outside and fail this for the wrong reason.
	h=$(names_outside)
	h="${h%%$'\n'*}"
	if [[ -n "$h" ]]; then
		refuse "the Caddyfile already mentions $h outside this script's block, and two blocks for one name would clash"
	fi
	check_folder_free
}

# Refuse when another site serves the site folder or the previous copy.
# Installing replaces that folder and rollback removes it, so the other site
# would silently start serving the TQO page, or nothing. Two views: the text
# outside this script's block (which also catches a mention in a comment),
# and Caddy's adapted config, where snippets, {args} and {$ENV} are already
# expanded, so a site that reaches the folder through an import is seen too.
# This script's own block roots each page site there once.
check_folder_free() {
	PHASE="checking no other site serves the tqohq folder"
	local own n_cur n_prev
	if grep -Eq -- "$FOLDER_RE" "$WORK/outside"; then
		refuse "another site in the Caddyfile already serves $CTR_STATIC/$SITE_DIR, and installing or rolling back would replace its files"
	fi
	own=$(block_hosts | grep -cvx -F -- "$WWW_HOST" || true)
	n_cur=$(grep -cE -- "\\.root=\"${CTR_STATIC}/${SITE_DIR}([^A-Za-z0-9._\"-][^\"]*)?\"\$" "$WORK/adapted.flat" || true)
	n_prev=$(grep -cE -- "\\.root=\"${CTR_STATIC}/${SITE_DIR}\\.prev([^A-Za-z0-9._\"-][^\"]*)?\"\$" "$WORK/adapted.flat" || true)
	if ((n_cur > own || n_prev > 0)); then
		refuse "another site in the Caddyfile already serves $CTR_STATIC/$SITE_DIR, and installing or rolling back would replace its files"
	fi
}

render_site() {
	local host="$1" robots="$2"
	printf '%s {\n' "$host"
	printf '\troot * %s/%s\n' "$CTR_STATIC" "$SITE_DIR"
	printf '\tencode zstd gzip\n'
	printf '\theader {\n'
	printf '\t\tX-Content-Type-Options "nosniff"\n'
	printf '\t\tReferrer-Policy "strict-origin-when-cross-origin"\n'
	printf '\t\tPermissions-Policy "camera=(), microphone=(), geolocation=()"\n'
	if [[ "$robots" == noindex ]]; then
		printf '\t\tX-Robots-Tag "noindex, nofollow"\n'
	fi
	printf '\t}\n'
	printf '\t@tqohq_fonts path /fonts/atkinson-hyperlegible-next-latin.woff2 /fonts/OFL-atkinson-hyperlegible-next.txt\n'
	printf '\thandle @tqohq_fonts {\n'
	printf '\t\theader Cache-Control "public, max-age=31536000, immutable"\n'
	printf '\t\tfile_server\n'
	printf '\t}\n'
	printf '\t@tqohq_pages path / /index.html /privacy.html\n'
	printf '\thandle @tqohq_pages {\n'
	printf '\t\theader Cache-Control "public, max-age=300"\n'
	printf '\t\tfile_server\n'
	printf '\t}\n'
	printf '\thandle {\n'
	printf '\t\trespond "Not found" 404\n'
	printf '\t}\n'
	printf '}\n'
}

# render_block stage|live NEWLINE_ADDED(0|1)
render_block() {
	printf '%s\n' "$BEGIN_MARK"
	printf '# The TQO home page: four files from %s at commit %s.\n' "$SITE_REPO" "$SITE_COMMIT"
	printf '# install-on-vps.sh rewrites everything between these marker lines on every run; change the script, not this block.\n'
	if [[ "${2:-0}" == 1 ]]; then
		printf '%s\n' "$NEWLINE_NOTE"
	fi
	if [[ "$1" == live ]]; then
		render_site "$APEX_HOST" index
		printf '%s {\n' "$WWW_HOST"
		printf '\tredir https://%s{uri} permanent\n' "$APEX_HOST"
		printf '}\n'
	fi
	render_site "$STAGE_HOST" noindex
	printf '%s\n' "$END_MARK"
}

# Build the new Caddyfile in $WORK/caddyfile.after: the old bytes with this
# script's block replaced where it stands, appended when absent, or removed
# ("none"). Bytes outside the block are never touched, with one exception
# that is undone: a file with no line break at its very end gets one before
# the appended block, the block says so, and removing the block takes that
# line break out again.
build_after() {
	local want="$1" before="$WORK/caddyfile.before" after="$WORK/caddyfile.after" nl_added=0 size
	if ((BLOCK_B == 0)); then
		if [[ "$want" != none && -s "$before" && "$(tail -c 1 -- "$before" | wc -l)" -eq 0 ]]; then
			nl_added=1
		fi
	else
		nl_added=$BLOCK_HAS_NL_NOTE
	fi
	: >"$WORK/block"
	if [[ "$want" != none ]]; then
		render_block "$want" "$nl_added" >"$WORK/block"
	fi
	if ((BLOCK_B == 0)); then
		cat -- "$before" >"$after"
		if [[ "$want" != none ]]; then
			if ((nl_added)); then
				printf '\n' >>"$after"
			fi
			cat -- "$WORK/block" >>"$after"
		fi
	else
		head -n "$((BLOCK_B - 1))" -- "$before" >"$WORK/head"
		tail -n "+$((BLOCK_E + 1))" -- "$before" >"$WORK/tail"
		# Only when the block is still the end of the file: anything someone
		# added after it needs that line break.
		if [[ "$want" == none ]] && ((nl_added)) && [[ ! -s "$WORK/tail" && -s "$WORK/head" && "$(tail -c 1 -- "$WORK/head" | wc -l)" -eq 1 ]]; then
			size=$(stat -c %s -- "$WORK/head")
			head -c "$((size - 1))" -- "$WORK/head" >"$WORK/head.trimmed"
			mv -f -- "$WORK/head.trimmed" "$WORK/head"
		fi
		cat -- "$WORK/head" "$WORK/block" "$WORK/tail" >"$after"
	fi
}

write_caddyfile() {
	PHASE="writing the Caddyfile"
	local stamp now_ino
	if [[ "$(sha256_of "$CADDYFILE")" != "$BEFORE_SUM" || "$(stat -L -c %i -- "$CADDYFILE")" != "$CADDYFILE_INODE" ]]; then
		fail "the Caddyfile changed while this script was running"
	fi
	stamp=$(date -u +%Y%m%dT%H%M%SZ)
	BACKUP_PATH="$CADDYFILE.tqohq-backup-$stamp"
	if [[ -e "$BACKUP_PATH" ]]; then
		BACKUP_PATH="$BACKUP_PATH-$$"
	fi
	CHANGED=1
	if ! (umask 077 && cat -- "$WORK/caddyfile.before" >"$BACKUP_PATH"); then
		fail "the Caddyfile backup could not be saved"
	fi
	chmod 600 -- "$BACKUP_PATH"
	if ! cmp -s -- "$WORK/caddyfile.before" "$BACKUP_PATH"; then
		fail "the Caddyfile backup did not read back the same"
	fi
	step "backup saved: $BACKUP_PATH"
	CADDY_WRITTEN=1
	if ! cat -- "$WORK/caddyfile.after" >"$CADDYFILE"; then
		fail "the new Caddyfile could not be written"
	fi
	now_ino=$(stat -L -c %i -- "$CADDYFILE")
	if [[ "$now_ino" != "$CADDYFILE_INODE" ]]; then
		fail "the Caddyfile was replaced by a new file instead of being rewritten in place"
	fi
	if ! cmp -s -- "$WORK/caddyfile.after" "$CADDYFILE"; then
		fail "the Caddyfile did not read back as written"
	fi
	if [[ "$(edge cat "$CTR_CADDYFILE" 2>/dev/null | sha256sum | awk '{print $1}')" != "$(sha256_of "$WORK/caddyfile.after")" ]]; then
		fail "the edge container does not see the new Caddyfile"
	fi
	step "Caddyfile rewritten in place (same inode)"
}

validate_and_reload() {
	PHASE="validating the new Caddyfile"
	if ! edge caddy validate --config "$CTR_CADDYFILE" --adapter caddyfile >"$WORK/validate.out" 2>&1; then
		say "Caddy said: $(caddy_error_line "$WORK/validate.out")"
		fail "Caddy rejected the new Caddyfile (its message is on the line above)"
	fi
	step "the new Caddyfile is valid"
	PHASE="reloading Caddy"
	RELOAD_TRIED=1
	if ! edge caddy reload --config "$CTR_CADDYFILE" --adapter caddyfile >"$WORK/reload.out" 2>&1; then
		say "Caddy said: $(caddy_error_line "$WORK/reload.out")"
		fail "Caddy refused to load the new configuration (its message is on the line above)"
	fi
	step "Caddy reloaded"
}

undo_caddyfile() {
	cat -- "$WORK/caddyfile.before" >"$CADDYFILE" || return 1
	cmp -s -- "$WORK/caddyfile.before" "$CADDYFILE" || return 1
	[[ "$(stat -L -c %i -- "$CADDYFILE")" == "$CADDYFILE_INODE" ]] || return 1
	if ((RELOAD_TRIED)); then
		edge caddy validate --config "$CTR_CADDYFILE" --adapter caddyfile >/dev/null 2>&1 || return 1
		edge caddy reload --config "$CTR_CADDYFILE" --adapter caddyfile >/dev/null 2>&1 || return 1
	fi
	return 0
}

# ---------------------------------------------------------------------------
# The site folder.
# ---------------------------------------------------------------------------
safe_rm_tree() {
	case "$1" in
	"$STATIC_SRC/$SITE_DIR" | "$STATIC_SRC/.tqohq-"*) rm -rf -- "$1" ;;
	*) return 1 ;;
	esac
}

site_is_current() {
	local dir="$1" listing entry name bytes sum
	[[ -d "$dir" && ! -L "$dir" ]] || return 1
	listing=$(cd -- "$dir" && find . -mindepth 1 -printf '%y %P\n' | sort)
	[[ "$listing" == "$SITE_LISTING" ]] || return 1
	for entry in "${SITE_FILES[@]}"; do
		read -r name bytes sum <<<"$entry"
		[[ "$(stat -c %s -- "$dir/$name")" == "$bytes" ]] || return 1
		[[ "$(sha256_of "$dir/$name")" == "$sum" ]] || return 1
	done
	return 0
}

download_site() {
	PHASE="downloading the site files"
	local entry name bytes sum got
	mkdir -p -- "$WORK/site/fonts"
	for entry in "${SITE_FILES[@]}"; do
		read -r name bytes sum <<<"$entry"
		if ! "$CURL" -fsSL --proto '=https' --tlsv1.2 --retry 2 --connect-timeout 15 --max-time 120 -o "$WORK/site/$name" "$RAW_BASE/$name" 2>/dev/null; then
			refuse "$name could not be downloaded from GitHub"
		fi
		got=$(stat -c %s -- "$WORK/site/$name")
		if [[ "$got" != "$bytes" ]]; then
			refuse "$name downloaded at $got bytes where $bytes were expected"
		fi
		if [[ "$(sha256_of "$WORK/site/$name")" != "$sum" ]]; then
			refuse "$name downloaded with the wrong contents (its checksum does not match the pinned one)"
		fi
	done
	step "downloaded the four site files at commit ${SITE_COMMIT:0:12}, sizes and checksums match"
}

install_site() {
	PHASE="putting the site files in place"
	local entry name bytes sum
	CHANGED=1
	STATIC_NEW=$(mktemp -d "$STATIC_SRC/.tqohq-new.XXXXXXXX") || fail "a folder for the new site files could not be made"
	mkdir -- "$STATIC_NEW/fonts" || fail "the fonts folder could not be made"
	for entry in "${SITE_FILES[@]}"; do
		read -r name bytes sum <<<"$entry"
		cp -- "$WORK/site/$name" "$STATIC_NEW/$name" || fail "$name could not be copied into place"
		chmod 644 -- "$STATIC_NEW/$name"
	done
	chmod 755 -- "$STATIC_NEW" "$STATIC_NEW/fonts"
	site_is_current "$STATIC_NEW" || fail "the new site folder did not check out after copying"
	if [[ -e "$STATIC_SRC/$PREV_DIR" ]]; then
		PREV_ASIDE="$STATIC_SRC/.tqohq-prev-old.$$.$RANDOM"
		mv -T -- "$STATIC_SRC/$PREV_DIR" "$PREV_ASIDE" || fail "the older previous copy could not be moved aside"
		PREV_MOVED=1
	fi
	if [[ -e "$STATIC_SRC/$SITE_DIR" ]]; then
		mv -T -- "$STATIC_SRC/$SITE_DIR" "$STATIC_SRC/$PREV_DIR" || fail "the current site folder could not be kept as $PREV_DIR"
		CUR_TO_PREV=1
	fi
	mv -T -- "$STATIC_NEW" "$STATIC_SRC/$SITE_DIR" || fail "the new site folder could not be moved into place"
	STATIC_NEW=""
	NEW_TO_CUR=1
	step "site files in place at $STATIC_SRC/$SITE_DIR"
}

# Rollback's side of the site folder. Only folders this installer made are
# touched: its current copy is taken away, and its previous copy put back in
# its place. A folder it did not make is left exactly where it is.
remove_site() {
	PHASE="putting the previous site folder back"
	CHANGED=1
	if ((CUR_OURS)); then
		CUR_ASIDE="$STATIC_SRC/.tqohq-removed.$$.$RANDOM"
		mv -T -- "$STATIC_SRC/$SITE_DIR" "$CUR_ASIDE" || fail "the site folder could not be moved aside"
		CUR_MOVED=1
	fi
	if ((PREV_OURS)) && [[ ! -e "$STATIC_SRC/$SITE_DIR" ]]; then
		mv -T -- "$STATIC_SRC/$PREV_DIR" "$STATIC_SRC/$SITE_DIR" || fail "the previous site folder could not be put back"
		PREV_RESTORED=1
	fi
}

# ---------------------------------------------------------------------------
# The record of which site folders this installer made. It lives beside the
# Caddyfile, outside the static folder Caddy serves, readable by root only.
# A folder counts as this installer's when its fingerprint is the one the
# record holds for it, or when it holds exactly the pinned files (then there
# is nothing in it that a download cannot bring back).
# ---------------------------------------------------------------------------
read_record() {
	PHASE="reading this installer's record"
	local name sum extra
	REC=()
	RECORD_HAD=0
	: >"$WORK/record.before"
	if [[ ! -e "$RECORD" ]]; then
		return 0
	fi
	RECORD_HAD=1
	cat -- "$RECORD" >"$WORK/record.before" || refuse "this installer's record, $RECORD, could not be read"
	while read -r name sum extra; do
		case "$name" in
		"" | "#"*) continue ;;
		esac
		if [[ ("$name" != "$SITE_DIR" && "$name" != "$PREV_DIR") || ! "$sum" =~ ^[0-9a-f]{64}$ || -n "$extra" ]]; then
			refuse "this installer's record, $RECORD, is damaged, so it cannot tell which site folders this installer made"
		fi
		REC["$name"]="$sum"
	done <"$WORK/record.before"
}

inspect_folders() {
	PHASE="checking who made the site folders"
	local name path sum ours
	CUR_EXISTS=0 CUR_OURS=0 CUR_SUM=""
	PREV_EXISTS=0 PREV_OURS=0 PREV_SUM=""
	for name in "$SITE_DIR" "$PREV_DIR"; do
		path="$STATIC_SRC/$name"
		if [[ ! -e "$path" ]]; then
			continue
		fi
		sum=$(tree_sum "$path") || refuse "the folder $path could not be read"
		ours=0
		if [[ -n "${REC[$name]:-}" && "${REC[$name]}" == "$sum" ]] || site_is_current "$path"; then
			ours=1
		fi
		if [[ "$name" == "$SITE_DIR" ]]; then
			CUR_EXISTS=1 CUR_OURS=$ours CUR_SUM=$sum
		else
			PREV_EXISTS=1 PREV_OURS=$ours PREV_SUM=$sum
		fi
	done
}

# stage and live replace the site folder and may delete the previous copy, so
# both have to be this installer's own.
check_folders_ours() {
	if ((CUR_EXISTS && !CUR_OURS)); then
		refuse "a folder $STATIC_SRC/$SITE_DIR is already on the box and this installer did not make it (or it was changed after it did), and installing would replace it, so someone has to look at it first; send this line to Claude"
	fi
	if ((PREV_EXISTS && !PREV_OURS)); then
		refuse "a folder $STATIC_SRC/$PREV_DIR is already on the box and this installer did not make it (or it was changed after it did), and installing could delete it, so someone has to look at it first; send this line to Claude"
	fi
}

# new_record NAME SUM [NAME SUM]: the record as it should read afterwards, in
# $WORK/record.after (empty when no folder of this installer's is left).
new_record() {
	: >"$WORK/record.after"
	if (($# == 0)); then
		return 0
	fi
	{
		printf '# install-on-vps.sh keeps this file: the site folders in %s it made, each with a fingerprint of its files, so it never moves or deletes a folder someone else put there. Do not edit it.\n' "$STATIC_SRC"
		while (($# >= 2)); do
			printf '%s %s\n' "$1" "$2"
			shift 2
		done
	} >"$WORK/record.after"
}

record_unchanged() { cmp -s -- "$WORK/record.before" "$WORK/record.after"; }

write_record() {
	PHASE="updating this installer's record"
	CHANGED=1
	RECORD_WRITTEN=1
	if [[ -s "$WORK/record.after" ]]; then
		if ! (umask 077 && cat -- "$WORK/record.after" >"$RECORD"); then
			fail "this installer's record could not be written"
		fi
		chmod 600 -- "$RECORD"
		if ! cmp -s -- "$WORK/record.after" "$RECORD"; then
			fail "this installer's record did not read back as written"
		fi
	else
		rm -f -- "$RECORD" || fail "this installer's record could not be removed"
	fi
}

undo_record() {
	if ((RECORD_HAD)); then
		cat -- "$WORK/record.before" >"$RECORD" || return 1
		cmp -s -- "$WORK/record.before" "$RECORD" || return 1
	else
		rm -f -- "$RECORD" || return 1
	fi
	return 0
}

undo_site() {
	local ok=0
	if ((PREV_RESTORED)); then
		mv -T -- "$STATIC_SRC/$SITE_DIR" "$STATIC_SRC/$PREV_DIR" || ok=1
	fi
	if ((CUR_MOVED)); then
		mv -T -- "$CUR_ASIDE" "$STATIC_SRC/$SITE_DIR" || ok=1
	fi
	if ((NEW_TO_CUR)); then
		safe_rm_tree "$STATIC_SRC/$SITE_DIR" || ok=1
	fi
	if ((CUR_TO_PREV)); then
		mv -T -- "$STATIC_SRC/$PREV_DIR" "$STATIC_SRC/$SITE_DIR" || ok=1
	fi
	if ((PREV_MOVED)); then
		mv -T -- "$PREV_ASIDE" "$STATIC_SRC/$PREV_DIR" || ok=1
	fi
	if [[ -n "$STATIC_NEW" && -e "$STATIC_NEW" ]]; then
		safe_rm_tree "$STATIC_NEW" || ok=1
	fi
	return "$ok"
}

commit_site() {
	if [[ -n "$PREV_ASIDE" && -e "$PREV_ASIDE" ]]; then
		safe_rm_tree "$PREV_ASIDE" || true
	fi
	if [[ -n "$CUR_ASIDE" && -e "$CUR_ASIDE" ]]; then
		safe_rm_tree "$CUR_ASIDE" || true
	fi
}

undo_all() {
	local ok=0
	UNDO_DETAIL=""
	if ((CADDY_WRITTEN)); then
		if undo_caddyfile; then
			rm -f -- "$BACKUP_PATH"
		else
			ok=1
			UNDO_DETAIL+="The Caddyfile could not be fully restored; its backup is $BACKUP_PATH. "
		fi
	elif [[ -n "$BACKUP_PATH" ]]; then
		rm -f -- "$BACKUP_PATH"
	fi
	if ((RECORD_WRITTEN)) && ! undo_record; then
		ok=1
		UNDO_DETAIL+="This installer's record, $RECORD, could not be put back. "
	fi
	if ! undo_site; then
		ok=1
		UNDO_DETAIL+="The site folder under $STATIC_SRC could not be fully restored. "
	fi
	return "$ok"
}

# ---------------------------------------------------------------------------
# DNS. Caddy is only asked for a certificate it can get.
# ---------------------------------------------------------------------------
public_ipv4() {
	local url ip
	for url in https://api.ipify.org https://ipv4.icanhazip.com https://checkip.amazonaws.com; do
		ip=$("$CURL" -4 -fsS --proto '=https' --connect-timeout 5 --max-time 10 "$url" 2>/dev/null | tr -d '[:space:]') || continue
		if is_ipv4 "$ip"; then
			printf '%s\n' "$ip"
			return 0
		fi
	done
	return 1
}

resolve_a() { "$GETENT" ahostsv4 "$1" 2>/dev/null | awk '{print $1}' | sort -u; }

# AAAA records as the public DNS sees them. getent cannot be used for this:
# on a box with no IPv6 address it does not ask for AAAA at all.
resolve_aaaa() {
	local url json
	for url in "https://cloudflare-dns.com/dns-query?name=$1&type=AAAA" "https://dns.google/resolve?name=$1&type=AAAA"; do
		json=$("$CURL" -fsS --proto '=https' --connect-timeout 5 --max-time 10 -H 'accept: application/dns-json' "$url" 2>/dev/null) || continue
		[[ "$json" =~ \"Status\":[[:space:]]*(0|3)[,}] ]] || continue
		grep -o '{[^{}]*}' <<<"$json" | grep -E '"type":[[:space:]]*28[,}]' | grep -o '"data":[[:space:]]*"[^"]*"' | sed -E 's/^"data":[[:space:]]*"//; s/"$//' || true
		return 0
	done
	return 1
}

local_ipv6_hex() {
	if [[ -r "$IF_INET6" ]]; then
		awk '$4 == "00" { print tolower($1) }' "$IF_INET6"
	fi
}

check_dns() {
	PHASE="checking DNS"
	local ip h addrs v6 addr hex local6
	if ! ip=$(public_ipv4); then
		refuse "this box's public IPv4 address could not be found (the address lookup services did not answer)"
	fi
	step "this box's public IPv4 address is $ip"
	local6=$(local_ipv6_hex)
	for h in "$@"; do
		addrs=$(resolve_a "$h") || addrs=""
		if [[ -z "$addrs" ]]; then
			refuse "$h does not resolve to any IPv4 address yet, so its DNS A record has to point at $ip first"
		fi
		if [[ "$addrs" != "$ip" ]]; then
			refuse "$h points at $(printf '%s' "$addrs" | tr '\n' ' '), not at this box ($ip), so its DNS has to move first"
		fi
		# A stray AAAA sends IPv6 visitors, and Let's Encrypt, somewhere else,
		# and tqohq.online is a Hostinger Builder site until its DNS moves. A
		# check that could not run is not a pass.
		if ! v6=$(resolve_aaaa "$h"); then
			refuse "the IPv6 (AAAA) records for $h could not be checked (neither DNS lookup service answered), so paste the line again in a few minutes"
		fi
		for addr in $v6; do
			hex=$(ipv6_hex "$addr")
			if [[ -z "$hex" ]] || ! grep -qx -F -- "$hex" <<<"$local6"; then
				refuse "$h also has an IPv6 (AAAA) record, $addr, that is not this box, so that AAAA record has to be deleted first"
			fi
		done
		step "$h points at this box"
	done
}

# ---------------------------------------------------------------------------
# Probes, all from this box to 127.0.0.1, never through a proxy.
# ---------------------------------------------------------------------------
probe_code() {
	local scheme="$1" host="$2" port=443 code
	if [[ "$scheme" == http ]]; then
		port=80
	fi
	if [[ "$host" == \*.* ]]; then
		host="tqohq-probe.${host#\*.}"
	fi
	code=$("$CURL" -sS -k --noproxy '*' --connect-timeout 5 --max-time 10 -o /dev/null -w '%{http_code}' --resolve "$host:$port:127.0.0.1" "$scheme://$host/" 2>/dev/null) || true
	if [[ ! "$code" =~ ^[0-9]{3}$ ]]; then
		code="000"
	fi
	printf '%s\n' "$code"
}

list_sites() {
	awk "$SITES_AWK" "$WORK/adapted.flat" | sort -u | while read -r scheme host; do
		case "$host" in
		*"{"* | *":"* | *"/"*) continue ;;
		"$STAGE_HOST" | "$APEX_HOST" | "$WWW_HOST") continue ;;
		esac
		if [[ "$host" == *"*"* && ("$host" != \*.* || "${host#\*.}" == *"*"*) ]]; then
			continue
		fi
		printf '%s %s\n' "$scheme" "$host"
	done
}

probe_before() {
	PHASE="checking the other sites before any change"
	local scheme host code total=0 answered=0
	list_sites >"$WORK/sites"
	DARK_BEFORE=()
	while read -r scheme host; do
		code=$(probe_code "$scheme" "$host")
		BEFORE["$scheme $host"]="$code"
		total=$((total + 1))
		if [[ "$code" != 000 ]]; then
			answered=$((answered + 1))
			if [[ -z "$ANCHOR" && "$scheme" == https && "$host" != \** ]]; then
				ANCHOR="$host"
			fi
		else
			DARK_BEFORE+=("$host")
		fi
	done <"$WORK/sites"
	if ((total > 0 && answered == 0)); then
		refuse "none of the $total other sites in the Caddyfile answered a check from this box, so the check that protects them cannot work"
	fi
	OTHERS_TOTAL=$total
	OTHERS_ANSWERED=$answered
	step "other sites answering before the change: $answered of $total"
}

# Every other site must answer with the same status code as before the
# change. Only "no answer at all" counted once, so a site that went from 200
# to 502, or to 404, passed and the RESULT still said every site answered.
probe_after() {
	PHASE="checking the other sites after the reload"
	local scheme host code was tries dark=() changed=() msg
	while read -r scheme host; do
		was="${BEFORE["$scheme $host"]}"
		if [[ "$was" == 000 ]]; then
			continue
		fi
		code=$(probe_code "$scheme" "$host")
		tries=0
		while [[ "$code" != "$was" && "$tries" -lt 3 ]]; do
			sleep 2
			code=$(probe_code "$scheme" "$host")
			tries=$((tries + 1))
		done
		if [[ "$code" == 000 ]]; then
			dark+=("$host")
		elif [[ "$code" != "$was" ]]; then
			changed+=("$host answered HTTP $code after the reload, where it answered $was before")
		fi
	done <"$WORK/sites"
	if ((${#dark[@]})); then
		fail "${dark[*]} stopped answering after the reload"
	fi
	if ((${#changed[@]})); then
		msg=$(printf '%s; ' "${changed[@]}")
		fail "${msg%; }"
	fi
	step "other sites answering as before after the change: $OTHERS_ANSWERED of $OTHERS_TOTAL"
}

# How the RESULT line talks about the other sites.
others_phrase() {
	if ((OTHERS_ANSWERED == OTHERS_TOTAL)); then
		printf 'all %s other sites still answer' "$OTHERS_TOTAL"
	else
		printf '%s of the %s other sites still answer as before (%s did not answer before this ran either)' \
			"$OTHERS_ANSWERED" "$OTHERS_TOTAL" "$(join_and "${DARK_BEFORE[@]}")"
	fi
}

# https_get strict|insecure HOST [SNI_HOST] -> "rc code redirect_url"; body in $WORK/body
https_get() {
	local verify="$1" host="$2" sni="${3:-$2}" out rc=0 args=()
	if [[ "$verify" == insecure ]]; then
		args+=(-k)
	fi
	if [[ "$sni" != "$host" ]]; then
		args+=(-H "Host: $host")
	fi
	rm -f -- "$WORK/body"
	out=$("$CURL" -sS ${args[@]+"${args[@]}"} --noproxy '*' --connect-timeout 5 --max-time 15 -o "$WORK/body" -w '%{http_code} %{redirect_url}' --resolve "$sni:443:127.0.0.1" "https://$sni/" 2>/dev/null) || rc=$?
	if [[ -z "$out" ]]; then
		out="000"
	fi
	printf '%s %s\n' "$rc" "$out"
}

# Is this the answer HOST should give? The page hosts serve index.html,
# www sends a permanent redirect to the apex.
answer_ok() {
	local host="$1" code="$2" loc="$3"
	if [[ "$host" == "$WWW_HOST" ]]; then
		[[ "$code" == 301 && "$loc" == "https://$APEX_HOST/" ]]
		return
	fi
	[[ "$code" == 200 && -f "$WORK/body" && "$(sha256_of "$WORK/body")" == "$INDEX_SHA256" ]]
}

prove_hosts() {
	PHASE="checking the new address answers"
	local deadline h rc code loc
	deadline=$(($(date +%s) + CERT_WAIT_S))
	for h in "$@"; do
		CERT["$h"]=pending
		PAGE["$h"]=unknown
		while :; do
			read -r rc code loc < <(https_get strict "$h")
			if [[ "$rc" == 0 ]]; then
				CERT["$h"]=valid
				if answer_ok "$h" "$code" "${loc:-}"; then PAGE["$h"]=ok; else PAGE["$h"]="bad $code"; fi
				break
			fi
			if [[ "${PAGE["$h"]}" == unknown ]]; then
				read -r rc code loc < <(https_get insecure "$h")
				if [[ "$rc" == 0 ]]; then
					if answer_ok "$h" "$code" "${loc:-}"; then PAGE["$h"]=ok; else PAGE["$h"]="bad $code"; fi
				fi
			fi
			if [[ "${PAGE["$h"]}" == bad* ]] || (($(date +%s) >= deadline)); then
				break
			fi
			sleep 3
		done
		if [[ "${PAGE["$h"]}" == unknown && -n "$ANCHOR" ]]; then
			# No TLS for this name yet. Ask Caddy for it by Host header over a
			# connection opened for a site that already has a certificate.
			# 421 Misdirected Request is Caddy refusing to answer one name on a
			# connection opened for another (strict_sni_host, which client_auth
			# anywhere on the server also switches on). That says nothing about
			# the page, so the page stays unknown and the certificate pending.
			read -r rc code loc < <(https_get insecure "$h" "$ANCHOR")
			if [[ "$rc" == 0 && "$code" != 421 ]]; then
				if answer_ok "$h" "$code" "${loc:-}"; then PAGE["$h"]=ok; else PAGE["$h"]="bad $code"; fi
			fi
		fi
		step "$h: page ${PAGE["$h"]%% *}, certificate ${CERT["$h"]}"
	done
}

# ---------------------------------------------------------------------------
# Modes.
# ---------------------------------------------------------------------------
preflight_edge() {
	preflight_basics
	if [[ -n "$SEAM_NOTE" ]]; then
		say "$SEAM_NOTE"
	fi
	if [[ -n "$TEST_ROOT" ]]; then
		step "TEST MODE against the fake root $TEST_ROOT"
	fi
	find_edge
	find_mounts
	take_lock
	check_container_view
}

run_install() {
	local want="$MODE" hosts=() h caddy_same=0 site_same=0 record_same=0 new_sum bad=() pending=() unknown=()
	if [[ "$want" == live ]]; then
		hosts=("$APEX_HOST" "$WWW_HOST" "$STAGE_HOST")
	else
		hosts=("$STAGE_HOST")
	fi
	preflight_edge
	check_space
	validate_current
	check_running_matches_disk
	read_caddyfile
	if [[ "$want" == stage ]] && block_has_host "$APEX_HOST"; then
		refuse "tqohq.online is live from this box, and stage mode would take it offline; run the live line to update it, or the rollback line to remove it"
	fi
	check_no_conflict
	read_record
	inspect_folders
	check_folders_ours
	check_dns "${hosts[@]}"
	download_site
	build_after "$want"
	if cmp -s -- "$WORK/caddyfile.before" "$WORK/caddyfile.after"; then
		caddy_same=1
	fi
	if site_is_current "$STATIC_SRC/$SITE_DIR"; then
		site_same=1
	fi
	# The record afterwards: the site folder, and the folder it replaces kept
	# as the previous copy. A previous copy that is not replaced stays listed.
	if ((site_same)); then
		if ((PREV_EXISTS)); then
			new_record "$SITE_DIR" "$CUR_SUM" "$PREV_DIR" "$PREV_SUM"
		else
			new_record "$SITE_DIR" "$CUR_SUM"
		fi
	else
		new_sum=$(tree_sum "$WORK/site") || refuse "the downloaded site files could not be read back"
		if ((CUR_EXISTS)); then
			new_record "$SITE_DIR" "$new_sum" "$PREV_DIR" "$CUR_SUM"
		else
			new_record "$SITE_DIR" "$new_sum"
		fi
	fi
	if record_unchanged; then
		record_same=1
	fi
	probe_before
	if ((site_same)); then
		step "site files already current, left as they are"
	else
		install_site
	fi
	if ((!record_same)); then
		write_record
	fi
	if ((caddy_same)); then
		step "Caddyfile already holds this exact block, left as it is"
	else
		write_caddyfile
		validate_and_reload
		probe_after
	fi
	prove_hosts "${hosts[@]}"
	for h in "${hosts[@]}"; do
		case "${PAGE["$h"]}" in
		ok) ;;
		unknown) unknown+=("$h") ;;
		*) bad+=("$h (HTTP ${PAGE["$h"]#bad })") ;;
		esac
		if [[ "${CERT["$h"]}" != valid ]]; then
			pending+=("$h")
		fi
	done
	if ((${#bad[@]})); then
		fail "the new address did not serve the TQO page: ${bad[*]}"
	fi
	commit_site
	COMMITTED=1
	PHASE="done"
	local where="https://$STAGE_HOST"
	if [[ "$want" == live ]]; then
		where="https://$APEX_HOST"
	fi
	if ((caddy_same && site_same && record_same)); then
		RESULT_LINE="RESULT: DONE, nothing needed changing, because $want was already installed exactly like this"
	elif [[ "$want" == live ]]; then
		RESULT_LINE="RESULT: DONE, tqohq.online now serves the TQO page from this box, www.tqohq.online sends visitors to it, the stage address still works, and $(others_phrase)"
	else
		RESULT_LINE="RESULT: DONE, the stage page is installed at $where and $(others_phrase)"
	fi
	if ((${#unknown[@]})); then
		RESULT_LINE+=", but ${unknown[*]} could not be fetched yet because its certificate is still being issued, so run the status line in five minutes."
	elif ((${#pending[@]})); then
		RESULT_LINE+=", but the certificate for ${pending[*]} is still being issued, so wait five minutes before opening $where on your iPhone, and run the status line if it still warns."
	else
		RESULT_LINE+=", with a valid certificate; open $where on your iPhone to check it."
	fi
}

run_rollback() {
	local had_block=0 had_apex=0 what=""
	preflight_edge
	check_space
	validate_current
	check_running_matches_disk
	read_caddyfile
	read_record
	inspect_folders
	if ((BLOCK_B)); then
		had_block=1
	fi
	if block_has_host "$APEX_HOST"; then
		had_apex=1
	fi
	if ((!had_block && !CUR_OURS && !PREV_OURS)); then
		COMMITTED=1
		if ((CUR_EXISTS || PREV_EXISTS)); then
			RESULT_LINE="RESULT: DONE, nothing to roll back: there is no tqohq block in the Caddyfile, and the tqohq folder on the box was not made by this installer (or was changed after it was), so it was left as it is."
		else
			RESULT_LINE="RESULT: DONE, nothing to roll back, because nothing from this installer is on the box."
		fi
		return 0
	fi
	if ((CUR_OURS || PREV_OURS)); then
		check_folder_free
	fi
	probe_before
	if ((had_block)); then
		build_after none
		write_caddyfile
		validate_and_reload
	fi
	remove_site
	# The record afterwards: the previous copy, now back in place, or a
	# previous copy that could not go back because a folder this installer
	# did not make is in its place. Nothing else is this installer's.
	if ((PREV_RESTORED)); then
		new_record "$SITE_DIR" "$PREV_SUM"
	elif ((PREV_OURS)); then
		new_record "$PREV_DIR" "$PREV_SUM"
	else
		new_record
	fi
	if ! record_unchanged; then
		write_record
	fi
	probe_after
	commit_site
	COMMITTED=1
	PHASE="done"
	if ((had_block)); then
		if ((PREV_RESTORED)); then
			what="the tqohq Caddy block is gone, the previous copy of the site files is back in place,"
		elif ((CUR_MOVED)); then
			what="the tqohq Caddy block and site files are gone"
		else
			what="the tqohq Caddy block is gone"
		fi
	else
		if ((CUR_MOVED && PREV_RESTORED)); then
			what="there was no tqohq Caddy block, the site files this installer left on the box are gone, the previous copy is back in place,"
		elif ((PREV_RESTORED)); then
			what="there was no tqohq Caddy block, the previous copy of the site files is back in place,"
		else
			what="there was no tqohq Caddy block, the site files this installer left on the box are gone,"
		fi
	fi
	RESULT_LINE="RESULT: DONE, $what and $(others_phrase)."
	if ((CUR_EXISTS && !CUR_OURS)); then
		RESULT_LINE+=" The folder $STATIC_SRC/$SITE_DIR was left as it is, because this installer did not make it (or it was changed after it did)."
	fi
	if ((PREV_EXISTS && !PREV_OURS)); then
		RESULT_LINE+=" The folder $STATIC_SRC/$PREV_DIR was left as it is, because this installer did not make it (or it was changed after it did)."
	fi
	if ((had_apex)); then
		RESULT_LINE+=" tqohq.online is no longer served from this box, so its DNS has to move back to where it was before."
	fi
}

# For status: a site that already answers over HTTPS, to ask for a new name by
# Host header while that name has no certificate yet. Read only.
status_anchor() {
	local scheme host code
	ANCHOR=""
	if ! edge caddy adapt --config "$CTR_CADDYFILE" --adapter caddyfile >"$WORK/adapted.json" 2>/dev/null; then
		return 0
	fi
	json_flatten <"$WORK/adapted.json" >"$WORK/adapted.flat"
	list_sites >"$WORK/sites"
	while read -r scheme host; do
		if [[ "$scheme" != https || "$host" == \** ]]; then
			continue
		fi
		code=$(probe_code "$scheme" "$host")
		if [[ "$code" != 000 ]]; then
			ANCHOR="$host"
			return 0
		fi
	done <"$WORK/sites"
}

run_status() {
	local hosts=() h files="missing" prev="no" backups state problems=() names=() elsewhere hint="send this line to Claude" only_waiting=1
	CERT_WAIT_S=0
	preflight_edge
	read_caddyfile
	read_record
	inspect_folders
	mapfile -t hosts < <(block_hosts)
	mapfile -t names < <(names_outside)
	elsewhere=$(join_and "${names[@]}")
	if site_is_current "$STATIC_SRC/$SITE_DIR"; then
		files="current (commit ${SITE_COMMIT:0:12})"
	elif ((CUR_EXISTS && CUR_OURS)); then
		files="an older copy this installer made, not the pinned files"
	elif ((CUR_EXISTS)); then
		files="present, but not made by this installer"
	fi
	if ((PREV_EXISTS && PREV_OURS)); then
		prev="yes"
	elif ((PREV_EXISTS)); then
		prev="a tqohq.prev folder is there, but not made by this installer"
	fi
	backups=$(find "$(dirname -- "$CADDYFILE")" -maxdepth 1 -name "$(basename -- "$CADDYFILE").tqohq-backup-*" | wc -l)
	if ((BLOCK_B)); then
		step "Caddy block: present, for ${hosts[*]:-no names}"
	else
		step "Caddy block: not present"
	fi
	if [[ -n "$elsewhere" ]]; then
		step "the Caddyfile also mentions $elsewhere outside this script's block"
	fi
	step "site files: $files"
	step "previous copy kept for rollback: $prev"
	step "Caddyfile backups next to it: $backups"
	if ((BLOCK_B == 0)); then
		COMMITTED=1
		if [[ -n "$elsewhere" ]]; then
			RESULT_LINE="RESULT: Not installed by this script, but the Caddyfile serves $elsewhere some other way; send this line to Claude."
		elif ((CUR_EXISTS && !CUR_OURS || PREV_EXISTS && !PREV_OURS)); then
			RESULT_LINE="RESULT: Not installed, and a tqohq folder this installer did not make is on the box, so the stage and live lines will refuse until someone has looked at it; send this line to Claude."
		elif ((CUR_EXISTS || PREV_EXISTS)); then
			RESULT_LINE="RESULT: Not installed: there is no tqohq block in the Caddyfile, though site files from an earlier run of this installer are still on disk."
		else
			RESULT_LINE="RESULT: Nothing from this installer is on the box."
		fi
		return 0
	fi
	if [[ -n "$elsewhere" ]]; then
		problems+=("the Caddyfile also mentions $elsewhere outside this script's block")
		only_waiting=0
	fi
	if ! site_is_current "$STATIC_SRC/$SITE_DIR"; then
		problems+=("the site files are not the pinned ones")
		only_waiting=0
	fi
	if [[ "$(sha256_of "$CADDYFILE")" != "$BEFORE_SUM" ]]; then
		problems+=("the Caddyfile changed while this was reading it")
		only_waiting=0
	fi
	status_anchor
	prove_hosts "${hosts[@]}"
	for h in "${hosts[@]}"; do
		case "${PAGE["$h"]}" in
		ok)
			if [[ "${CERT["$h"]}" != valid ]]; then
				problems+=("the certificate for $h is still being issued")
			fi
			;;
		unknown)
			problems+=("$h could not be fetched yet, most likely because its certificate is still being issued")
			;;
		*)
			problems+=("$h does not serve the TQO page (HTTP ${PAGE["$h"]#bad })")
			only_waiting=0
			;;
		esac
	done
	state="stage"
	if block_has_host "$APEX_HOST"; then
		state="live"
	fi
	COMMITTED=1
	if ((only_waiting)); then
		hint="wait five minutes and paste the status line again"
	fi
	if ((${#problems[@]})); then
		RESULT_LINE="RESULT: ${state^} is installed, but $(printf '%s; ' "${problems[@]}" | sed 's/; $//'), so $hint."
	elif [[ "$state" == live ]]; then
		RESULT_LINE="RESULT: Live is installed and working: tqohq.online serves the right page, www.tqohq.online sends visitors to it, and the stage address still works."
	else
		RESULT_LINE="RESULT: Stage is installed and working at https://$STAGE_HOST with a valid certificate."
	fi
}

main() {
	MODE="${1:-}"
	case "$MODE" in
	stage | live) run_install ;;
	rollback) run_rollback ;;
	status) run_status ;;
	*)
		RESULT_LINE="RESULT: NOT DONE, nothing on the box was changed, because the mode must be one of stage, live, rollback or status."
		exit 2
		;;
	esac
}

main "$@"
