# Briefer

A self-hosted personal daily briefing app. Fetches items from external sources and presents them as a swipeable card stack for triage.

## What it does

Each day you fetch new items from configured sources (Hacker News, NewsAPI, BBC News RSS feeds: Top stories, Wales, Technology, World) plus a single card with the day's weather forecast. Items appear as a card stack you swipe through — right to action, left to dismiss. Long-press a card for more options.

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
NEWSAPI_KEY=your-newsapi-key

# Optional: daily weather card (Open-Meteo, no key). Defaults to Cardiff.
BRIEFER_WEATHER_LATITUDE=51.49
BRIEFER_WEATHER_LONGITUDE=-3.16
BRIEFER_WEATHER_PLACE=Cardiff
BRIEFER_WEATHER_URL=https://www.bbc.co.uk/weather/2653822

# Raindrop.io action (swipe right saves a bookmark, tagged "briefer").
# Register an app at https://app.raindrop.io/settings/integrations, set its
# redirect URI to <briefer URL>/raindrop/callback/, then click
# "connect raindrop" in the UI once. Tokens are stored in the database and
# refreshed automatically.
RAINDROP_CLIENT_ID=your-client-id
RAINDROP_CLIENT_SECRET=your-client-secret
RAINDROP_REDIRECT_URI=https://yourdomain.com/briefer/raindrop/callback/
# Optional: the app's personal "Test token" instead of OAuth
# RAINDROP_TEST_TOKEN=
# Optional: collection id to save into (default: Unsorted)
# RAINDROP_COLLECTION_ID=
# Optional: collection served as RSS at <briefer URL>/raindrop/feed.xml
# (default: -1, Unsorted). Raindrop only has RSS for public collections, so
# this is how a private one gets to a feed reader such as Kindly.
# RAINDROP_FEED_COLLECTION_ID=
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

## Deleting all items

```bash
uv run manage.py delete_items
```

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
