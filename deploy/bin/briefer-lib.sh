# shellcheck shell=bash
# Shared helpers for the briefer-* deploy scripts. Sourced, not executed.
#
# Layout (all overridable for tests):
#   $BRIEFER_ROOT/bin/                   these scripts (root-owned, installed by bootstrap.sh)
#   $BRIEFER_ROOT/builds/<id>/           extracted release bundles
#   $BRIEFER_ROOT/envs/<env>/current  -> ../../builds/<id>
#   $BRIEFER_DATA/<env>/                 PocketBase data dirs (prod, staging, verify)
#   $BRIEFER_DATA/snapshots/             prod snapshots taken before each promote
#   $BRIEFER_DATA/promotions.log         "<ts> <from-id|none> <to-id> <snapshot|none>" per promote
#   $BRIEFER_ETC/{common,prod,staging,verify}.env

set -euo pipefail

BRIEFER_ROOT="${BRIEFER_ROOT:-/opt/briefer}"
BRIEFER_DATA="${BRIEFER_DATA:-/var/lib/briefer}"
BRIEFER_ETC="${BRIEFER_ETC:-/etc/briefer}"
BRIEFER_REPO="${BRIEFER_REPO:-sheeshee/briefer}"
BRIEFER_RELEASE_BASE_URL="${BRIEFER_RELEASE_BASE_URL:-https://github.com/$BRIEFER_REPO/releases/download}"
BRIEFER_KEEP_BUILDS="${BRIEFER_KEEP_BUILDS:-10}"
BRIEFER_KEEP_SNAPSHOTS="${BRIEFER_KEEP_SNAPSHOTS:-10}"
BRIEFER_SMOKE_MAX_RSS_MB="${BRIEFER_SMOKE_MAX_RSS_MB:-200}"

if [[ -z "${BRIEFER_SVC:-}" ]]; then
  # User units need a runtime dir; non-interactive SSH sessions may lack it.
  export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
  BRIEFER_SVC="systemctl --user"
fi

if [[ -z "${BRIEFER_ARCH:-}" ]]; then
  case "$(uname -m)" in
    aarch64|arm64) BRIEFER_ARCH=arm64 ;;
    x86_64|amd64) BRIEFER_ARCH=amd64 ;;
    *) echo "unsupported machine: $(uname -m)" >&2; exit 1 ;;
  esac
fi

BUILD_ID_RE='^[0-9a-f]{12}$'
# shellcheck disable=SC2034 # used by scripts that source this file
SHA256_RE='^[0-9a-f]{64}$'

log() { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

valid_build_id() { [[ "$1" =~ $BUILD_ID_RE ]]; }

svc() {
  # shellcheck disable=SC2086 # BRIEFER_SVC is intentionally word-split.
  $BRIEFER_SVC "$@"
}

env_var() {
  # env_var <env> <NAME> [default] — read a value from $BRIEFER_ETC/<env>.env
  local file="$BRIEFER_ETC/$1.env" val=""
  [[ -f "$file" ]] && val="$(sed -n "s/^$2=//p" "$file" | tail -1)"
  printf '%s' "${val:-${3:-}}"
}

env_port() {
  case "$1" in
    prod) env_var prod BRIEFER_PORT 8090 ;;
    staging) env_var staging BRIEFER_PORT 8091 ;;
    verify) env_var verify BRIEFER_PORT 8092 ;;
    *) die "unknown env: $1" ;;
  esac
}

current_build() {
  local link="$BRIEFER_ROOT/envs/$1/current"
  [[ -L "$link" ]] && basename "$(readlink "$link")" || true
}

switch_env() {
  # switch_env <env> <build-id> — atomically repoint envs/<env>/current
  mkdir -p "$BRIEFER_ROOT/envs/$1"
  ln -sfn "../../builds/$2" "$BRIEFER_ROOT/envs/$1/current.tmp"
  mv -Tf "$BRIEFER_ROOT/envs/$1/current.tmp" "$BRIEFER_ROOT/envs/$1/current"
}

with_lock() {
  # Serialise every mutating operation (deploys, promotes, verifies, rollbacks).
  mkdir -p "$BRIEFER_DATA"
  exec 9>"$BRIEFER_DATA/.lock"
  flock -w 600 9 || die "timed out waiting for another deploy operation"
}

copy_data_live() {
  # copy_data_live <src-dir> <dst-dir> — consistent copy of a (possibly running)
  # PocketBase data dir using SQLite's online backup API.
  local src="$1" dst="$2"
  rm -rf "$dst"
  mkdir -p "$dst"
  [[ -d "$src" ]] || return 0
  local db
  for db in data.db auxiliary.db; do
    [[ -f "$src/$db" ]] || continue
    python3 - "$src/$db" "$dst/$db" <<'PY'
import sqlite3, sys
src = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
dst = sqlite3.connect(sys.argv[2])
src.backup(dst)
dst.close(); src.close()
PY
  done
  [[ -d "$src/storage" ]] && cp -a "$src/storage" "$dst/storage"
  return 0
}

wait_healthy() {
  local port; port="$(env_port "$1")"
  local _
  for _ in $(seq 1 75); do
    curl -fsS -o /dev/null "http://127.0.0.1:$port/api/health" 2>/dev/null && return 0
    sleep 0.2
  done
  return 1
}

restart_env() {
  svc restart "briefer@$1" || return 1
  wait_healthy "$1"
}

prune() {
  # Keep the newest N builds plus anything an env points at; newest N snapshots.
  local keep=() id
  for id in prod staging verify; do keep+=("$(current_build "$id")"); done
  if [[ -d "$BRIEFER_ROOT/builds" ]]; then
    local n=0 dir
    while IFS= read -r dir; do
      n=$((n + 1))
      id="$(basename "$dir")"
      [[ $n -le $BRIEFER_KEEP_BUILDS ]] && continue
      [[ " ${keep[*]} " == *" $id "* ]] && continue
      grep -q " $id " "$BRIEFER_DATA/promotions.log" 2>/dev/null && [[ $n -le $((BRIEFER_KEEP_BUILDS * 2)) ]] && continue
      rm -rf "$dir"
    done < <(ls -1dt "$BRIEFER_ROOT/builds"/*/ 2>/dev/null | sed 's:/$::')
  fi
  if [[ -d "$BRIEFER_DATA/snapshots" ]]; then
    ls -1t "$BRIEFER_DATA/snapshots"/*.tar.gz 2>/dev/null | tail -n +$((BRIEFER_KEEP_SNAPSHOTS + 1)) | xargs -r rm -f
  fi
}
