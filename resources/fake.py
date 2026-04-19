import random
from datetime import timedelta

from django.utils import timezone

from core.models import Item
from resources.base import BaseResource

FAKE_ITEMS = [
    {
        "title": "Researchers discover that sleep deprivation makes code reviews worse",
        "summary": "A new study found that developers who review code after fewer than 6 hours of sleep approve 40% more bugs.",
        "url": "https://example.com/sleep-code-review",
        "metadata": {"score": 312, "num_comments": 87},
    },
    {
        "title": "Why your database is slow (and it's not the indexes)",
        "summary": "Connection pooling, N+1 queries, and lock contention are the real culprits behind most database slowdowns.",
        "url": "https://example.com/db-slow",
        "metadata": {"score": 540, "num_comments": 134},
    },
    {
        "title": "The return of the monolith",
        "summary": "More teams are moving back from microservices to modular monoliths as operational complexity mounts.",
        "url": "https://example.com/monolith-return",
        "metadata": {"score": 892, "num_comments": 201},
    },
    {
        "title": "New open-source tool auto-generates API documentation from tests",
        "summary": "DocGen 2.0 watches your test suite and produces up-to-date API docs without any manual markup.",
        "url": "https://example.com/docgen",
        "metadata": {"score": 178, "num_comments": 42},
    },
    {
        "title": "Ask HN: What's your morning routine before writing code?",
        "summary": "Developers share rituals ranging from 20-minute walks to reading papers to simply making coffee.",
        "url": "https://example.com/morning-routine",
        "metadata": {"score": 623, "num_comments": 315},
    },
    {
        "title": "SQLite in production: lessons from running it at scale",
        "summary": "WAL mode, PRAGMA tuning, and backup strategies that let a small team run SQLite for millions of requests.",
        "url": "https://example.com/sqlite-production",
        "metadata": {"score": 741, "num_comments": 188},
    },
    {
        "title": "The underrated power of boring technology",
        "summary": "Choosing PostgreSQL, plain HTTP, and cron jobs over trendy stacks has compounding benefits over years.",
        "url": "https://example.com/boring-tech",
        "metadata": {"score": 1024, "num_comments": 267},
    },
    {
        "title": "Show HN: I built a self-hosted RSS reader in a single Python file",
        "summary": "500 lines, SQLite, no dependencies beyond the stdlib. Demo and source in the comments.",
        "url": "https://example.com/rss-reader",
        "metadata": {"score": 389, "num_comments": 96},
    },
    {
        "title": "How HTMX changes the way you think about web apps",
        "summary": "Instead of fetching JSON and rendering on the client, you return HTML fragments — and it turns out that's enough.",
        "url": "https://example.com/htmx-thinking",
        "metadata": {"score": 456, "num_comments": 112},
    },
    {
        "title": "Firefox is back: market share up for the third consecutive quarter",
        "summary": "Analysts attribute the growth to privacy concerns and dissatisfaction with Chrome's Manifest V3 rollout.",
        "url": "https://example.com/firefox-back",
        "metadata": {"score": 987, "num_comments": 430},
    },
]


class FakeResource(BaseResource):

    source_id = "fake"

    def __init__(self, num_items: int = 10):
        self.num_items = num_items

    def fetch(self) -> None:
        now = timezone.now()
        today = now.date()

        sample = random.sample(FAKE_ITEMS, min(self.num_items, len(FAKE_ITEMS)))

        for i, item in enumerate(sample):
            external_id = f"fake-{today}-{i}"

            if Item.objects.filter(external_id=external_id).exists():
                continue

            Item.objects.create(
                external_id=external_id,
                source=self.source_id,
                title=item["title"],
                summary=item["summary"],
                url=item["url"],
                metadata=item["metadata"],
                expires_at=now + timedelta(hours=24),
            )
