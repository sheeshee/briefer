# Briefer

A self-hosted personal daily briefing web app. Fetches items from external sources and presents them as a swipeable card stack for triage.

## Stack

- Django 5 + SQLite
- HTMX for interactivity
- `uv` for dependency and environment management

## Commands

All commands should be run with `uv`:

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

## Committing

After completing any task that modifies files, stage and commit the changes using the `/commit` skill. Group changes into logical commits — one concern per commit.

## Data Model

`core.Item` has states: `pending` → `seen` / `actioned` / `dismissed`. Items are ordered by `-fetched_at`. Optional `expires_at` for time-limited items.
