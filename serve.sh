#!/usr/bin/env bash
set -euo pipefail

PORT=${1:-8000}

exec uv run gunicorn briefer.wsgi:application --bind "0.0.0.0:${PORT}"
