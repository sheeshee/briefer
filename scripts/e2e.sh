#!/usr/bin/env bash
# Build an amd64 release bundle, run it with real PocketBase, and run the
# Playwright suite against it. Used by CI and locally:
#
#   scripts/e2e.sh [extra playwright args]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${E2E_PORT:-18090}"
WORK="$(mktemp -d)"
PB_PID=""
cleanup() {
  [[ -n "$PB_PID" ]] && kill "$PB_PID" 2>/dev/null || true
  rm -rf "$WORK"
}
trap cleanup EXIT

TARBALL="$("$ROOT/scripts/build-release.sh" --arch amd64 --out "$WORK/dist" ${E2E_SKIP_WEB:+--skip-web} | tail -1)"
mkdir -p "$WORK/release" "$WORK/data"
tar -C "$WORK/release" -xzf "$TARBALL"

(cd "$WORK/release" && BRIEFER_ENV=staging exec ./pocketbase serve \
  --http "127.0.0.1:$PORT" --dir "$WORK/data" \
  --hooksDir ./pb_hooks --migrationsDir ./pb_migrations --publicDir ./pb_public \
  > "$WORK/pocketbase.log" 2>&1) &
PB_PID=$!

for _ in $(seq 1 50); do
  curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1 && break
  sleep 0.2
done
curl -fsS "http://127.0.0.1:$PORT/api/health" >/dev/null || { cat "$WORK/pocketbase.log" >&2; exit 1; }

cd "$ROOT/web"
BRIEFER_URL="http://127.0.0.1:$PORT" npx playwright test "$@"
