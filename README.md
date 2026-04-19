# Briefer

A self-hosted personal daily briefing app. Fetches items from external sources and presents them as a swipeable card stack for triage.

## What it does

Each day you fetch new items from configured sources (Hacker News, NewsAPI, etc.). Items appear as a card stack you swipe through — right to action, left to dismiss. Long-press a card for more options.

## Stack

- Python 3.11+ / Django 5 / SQLite
- HTMX for interactivity
- `uv` for dependency and environment management

## Setup

```bash
# Install dependencies
uv sync

# Apply migrations
uv run manage.py migrate

# Start the dev server
uv run manage.py runserver
```

Then open http://localhost:8000.

## Configuration

Create a `.env` file in the project root:

```env
DJANGO_SECRET_KEY=your-secret-key
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=localhost,yourdomain.com

# Required for NewsAPI resource
NEWS_API_KEY=your-newsapi-key
```

## Fetching items

Click **fetch** in the UI, or run the management command directly:

```bash
uv run manage.py fetch_resources
```

To include fake/demo items (useful for development):

```bash
uv run manage.py fetch_resources --include-fake
```

The UI fetch button also has a **fake** checkbox for the same purpose.

## Adding a resource

Subclass `resources.base.BaseResource`, set `source_id`, and implement `fetch()`:

```python
from resources.base import BaseResource
from core.models import Item

class MyResource(BaseResource):
    source_id = "my-source"

    def fetch(self) -> None:
        # fetch data, create Item objects
        Item.objects.get_or_create(
            external_id="unique-id",
            defaults={"source": self.source_id, "title": "...", "url": "..."},
        )
```

Register it in `core/management/commands/fetch_resources.py`.

`fetch()` must be idempotent — use `external_id` to avoid duplicate items.

## Running tests

```bash
uv run pytest
```

## Item states

`pending` → `actioned` / `dismissed` / `seen`

Items have an optional `expires_at` for time-limited content.
