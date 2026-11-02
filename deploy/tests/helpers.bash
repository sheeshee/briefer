# Shared bats setup: an isolated BRIEFER_ROOT/DATA/ETC under a temp dir, a fake
# systemctl that runs real PocketBase processes, and a file:// "GitHub release"
# server holding two real amd64 bundles (A and B).

REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
BUILD_A="aaaaaaaaaaaa"
BUILD_B="bbbbbbbbbbbb"

# Built once per test run (bats runs setup_file per file).
build_fixture_releases() {
  local rel="$BATS_FILE_TMPDIR/releases"
  [[ -d "$rel" ]] && return
  mkdir -p "$rel"
  local id tarball first=1
  for id in "$BUILD_A" "$BUILD_B"; do
    mkdir -p "$rel/build-$id"
    if [[ $first -eq 1 && ! -f "$REPO_ROOT/web/dist/index.html" ]]; then
      (cd "$REPO_ROOT/web" && npm run build >/dev/null)
    fi
    first=0
    tarball="$(BRIEFER_BUILD_ID="$id" "$REPO_ROOT/scripts/build-release.sh" --arch amd64 --skip-web --out "$rel/build-$id" | tail -1)"
    [[ -f "$tarball" ]]
  done
  # A deliberately broken bundle: the binary exits immediately.
  local broken="cccccccccccc" stage="$BATS_FILE_TMPDIR/broken"
  mkdir -p "$stage" "$rel/build-$broken"
  tar -C "$stage" -xzf "$rel/build-$BUILD_A/briefer-$BUILD_A-linux-amd64.tar.gz"
  printf '#!/bin/sh\nexit 1\n' > "$stage/pocketbase"; chmod +x "$stage/pocketbase"
  tar -C "$stage" -czf "$rel/build-$broken/briefer-$broken-linux-amd64.tar.gz" .
  (cd "$rel/build-$broken" && sha256sum "briefer-$broken-linux-amd64.tar.gz" > "briefer-$broken-linux-amd64.tar.gz.sha256")
}

sha_of() {
  cut -d' ' -f1 "$BATS_FILE_TMPDIR/releases/build-$1/briefer-$1-linux-amd64.tar.gz.sha256"
}

setup_env() {
  export T="$BATS_TEST_TMPDIR"
  export BRIEFER_ROOT="$T/opt" BRIEFER_DATA="$T/data" BRIEFER_ETC="$T/etc"
  export BRIEFER_RUN="$T/run"
  export BRIEFER_SVC="$BATS_TEST_DIRNAME/fake-svc"
  export BRIEFER_ARCH="amd64"
  export BRIEFER_RELEASE_BASE_URL="file://$BATS_FILE_TMPDIR/releases"
  export BRIEFER_VERIFY_CLAUDE=0
  export BRIEFER_SMOKE_MAX_RSS_MB=400
  mkdir -p "$BRIEFER_ETC" "$BRIEFER_RUN"
  local base=$(( 20000 + (RANDOM % 4000) * 3 ))
  printf 'BRIEFER_ENV=prod\nBRIEFER_PORT=%s\n' "$base" > "$BRIEFER_ETC/prod.env"
  printf 'BRIEFER_ENV=staging\nBRIEFER_PORT=%s\n' "$((base + 1))" > "$BRIEFER_ETC/staging.env"
  printf 'BRIEFER_ENV=verify\nBRIEFER_PORT=%s\n' "$((base + 2))" > "$BRIEFER_ETC/verify.env"
  export PATH="$REPO_ROOT/deploy/bin:$PATH"
}

teardown_env() {
  local env
  for env in prod staging verify; do "$BRIEFER_SVC" stop "briefer@$env" >/dev/null 2>&1 || true; done
}

current_build() { basename "$(readlink "$BRIEFER_ROOT/envs/$1/current")"; }

served_build() {
  local port
  port="$(sed -n 's/^BRIEFER_PORT=//p' "$BRIEFER_ETC/$1.env")"
  curl -fsS "http://127.0.0.1:$port/api/briefer/version" | python3 -c 'import json,sys; print(json.load(sys.stdin)["build"])'
}

# has_superuser <env> <email> -> prints 1 or 0. (PocketBase creates its own
# temporary __pbinstaller superuser on first start, so we match by email.)
has_superuser() {
  python3 - "$BRIEFER_DATA/$1/data.db" "$2" <<'PY'
import sqlite3, sys
q = "select count(*) from _superusers where email = ?"
print(sqlite3.connect(sys.argv[1]).execute(q, (sys.argv[2],)).fetchone()[0])
PY
}

add_prod_superuser() {
  "$BRIEFER_SVC" stop briefer@prod
  "$BRIEFER_ROOT/envs/prod/current/pocketbase" superuser upsert "$1" "correct-horse-battery" \
    --dir "$BRIEFER_DATA/prod" >/dev/null
  "$BRIEFER_SVC" start briefer@prod
}
