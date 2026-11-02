# Briefer

A self-hosted personal daily briefing web app. Fetches items from external sources and presents them as a swipeable card stack for triage.

## Stack

Migration in progress (see `docs/dev-loop.md`): the app is moving to
PocketBase + React, one milestone PR at a time. Until M6 both exist:

- **New:** PocketBase (built from the pinned Go module in `pb/`, JS hooks in
  `pb/pb_hooks/`), React + Vite + TypeScript in `web/`, deployed to a
  Raspberry Pi with prod and staging environments via `deploy/`
- **Legacy (removed in M6):** Django 5 + SQLite + vanilla JS, managed with `uv`

## Commands

New stack:

```bash
scripts/dev.sh                      # PocketBase :8090 + Vite :5173
(cd web && npm test && npm run typecheck)
node --test 'pb/tests/*.test.js'    # hook logic
scripts/e2e.sh                      # Playwright against real PocketBase + bundle
npx --yes bats@1.13.0 deploy/tests  # deploy-script tests
```

Legacy Django commands, run with `uv`:

```bash
# Run dev server
uv run manage.py runserver

# Apply migrations
uv run manage.py migrate

# Create migrations after model changes
uv run manage.py makemigrations

# Fetch items from all registered resources
uv run manage.py fetch_resources

# Delete all items from the database
uv run manage.py delete_items

# Run tests
uv run pytest
```

## Project Structure

- `pb/` — PocketBase build (`main.go`), hooks (`pb_hooks/`, logic in `pb_hooks/lib/`), migrations, hook tests
- `web/` — React frontend (`src/`), Vitest unit tests, Playwright e2e (`e2e/`)
- `deploy/` — Pi scripts (`bin/briefer-*`), bootstrap, systemd unit, Caddyfile, bats tests
- `scripts/` — release bundle, e2e and dev runners
- `.github/` — CI, staging deploy, promote-on-merge, manual Pi operations
- `docs/dev-loop.md` — how changes get tested, reviewed and deployed

Legacy Django:

- `briefer/` — Django project settings, URLs, WSGI
- `core/` — main app: `Item` model, views, URLs, templates
- `resources/` — pluggable resource fetchers (subclass `BaseResource`)
- `actions/` — pluggable item actions
- `tests/` — pytest test suite

## Adding a Resource

Subclass `resources.base.BaseResource`, set `source_id`, implement `fetch()`. Register the instance in `core/management/commands/fetch_resources.py`.

`fetch()` must be idempotent — use `external_id` to avoid duplicate `Item` records.

## Testing Approach

Use red-green testing for all feature additions, changes, and bug fixes:
1. Write a failing test that captures the expected behavior
2. Verify it fails (red)
3. Implement the change to make it pass (green)

For PocketBase hooks, keep the `*.pb.js` files thin and put logic in
`pb/pb_hooks/lib/` as plain CommonJS (no `$app`/`$os` globals) so it can be
unit-tested with `node --test`.

## Deploying

Never deploy by hand. Push to the milestone PR: CI deploys to staging on the
Pi and posts a verify report. Merging to `main` promotes the exact
staging-tested bundle to prod. See `docs/dev-loop.md`.

## Committing

After completing any task that modifies files, stage and commit the changes using the `/commit` skill. Group changes into logical commits — one concern per commit.

## Data Model

`core.Item` has states: `pending` → `seen` / `actioned` / `dismissed`. Items are ordered by `-fetched_at`. Optional `expires_at` for time-limited items.
