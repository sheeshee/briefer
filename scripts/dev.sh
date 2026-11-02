#!/usr/bin/env bash
# Local development: PocketBase on :8090 (hooks hot-reload) + Vite on :5173.
#   scripts/dev.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$ROOT/.dev"
(cd "$ROOT/pb" && go build -o "$ROOT/.dev/pocketbase" .)

"$ROOT/.dev/pocketbase" serve --http 127.0.0.1:8090 --dir "$ROOT/.dev/pb_data" \
  --hooksDir "$ROOT/pb/pb_hooks" --hooksWatch --migrationsDir "$ROOT/pb/pb_migrations" \
  --automigrate --publicDir "$ROOT/web/dist" &
PB_PID=$!
trap 'kill $PB_PID 2>/dev/null || true' EXIT

cd "$ROOT/web" && npm run dev
