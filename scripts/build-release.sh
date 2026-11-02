#!/usr/bin/env bash
# Build a release bundle: PocketBase binary + hooks + migrations + built frontend.
#
#   scripts/build-release.sh [--arch amd64|arm64] [--out DIR] [--skip-web]
#
# Prints the path of the created tarball on stdout (last line). The build id is
# the first 12 hex chars of the git *tree* hash, so a squash/merge of an
# up-to-date branch produces the same id as the branch head (see
# docs/dev-loop.md, "Promote by content"). Local builds with uncommitted
# changes get a "-dirty" suffix and must never be deployed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARCH="arm64"
OUT="$ROOT/dist"
SKIP_WEB=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --arch) ARCH="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --skip-web) SKIP_WEB=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

case "$ARCH" in amd64|arm64) ;; *) echo "unsupported arch: $ARCH" >&2; exit 2 ;; esac

cd "$ROOT"
BUILD_ID="${BRIEFER_BUILD_ID:-$(git rev-parse 'HEAD^{tree}' | cut -c1-12)}"
COMMIT="$(git rev-parse HEAD)"
if [[ -z "${BRIEFER_BUILD_ID:-}" && -n "$(git status --porcelain -- pb web scripts)" ]]; then
  BUILD_ID="${BUILD_ID}-dirty"
fi

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

if [[ "$SKIP_WEB" -eq 0 ]]; then
  (cd web && npm run build >&2)
fi
[[ -f web/dist/index.html ]] || { echo "web/dist missing; build the frontend first" >&2; exit 1; }

(cd pb && CGO_ENABLED=0 GOOS=linux GOARCH="$ARCH" \
  go build -trimpath -ldflags "-s -w" -o "$STAGE/pocketbase" . ) >&2

cp -R pb/pb_hooks "$STAGE/pb_hooks"
cp -R pb/pb_migrations "$STAGE/pb_migrations"
cp -R web/dist "$STAGE/pb_public"
printf '{"build":"%s","commit":"%s","builtAt":"%s","arch":"%s"}\n' \
  "$BUILD_ID" "$COMMIT" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$ARCH" > "$STAGE/BUILD_INFO.json"

mkdir -p "$OUT"
TARBALL="$OUT/briefer-$BUILD_ID-linux-$ARCH.tar.gz"
tar -C "$STAGE" -czf "$TARBALL" .
(cd "$OUT" && sha256sum "$(basename "$TARBALL")" > "$(basename "$TARBALL").sha256")
echo "$TARBALL"
