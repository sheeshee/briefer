import hashlib
import logging
import os
from datetime import datetime, timedelta

import requests
from django.utils import timezone

from core.models import Item
from resources.base import BaseResource

logger = logging.getLogger(__name__)

NEWSAPI_URL = "https://newsapi.org/v2/top-headlines"


def _parse_published_at(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class NewsAPIResource(BaseResource):

    source_id = "news"

    def __init__(self, num_stories: int = 10, country: str = "us"):
        self.num_stories = num_stories
        self.country = country

    def fetch(self) -> None:
        api_key = os.environ.get("NEWSAPI_KEY")
        if not api_key:
            logger.warning("NEWSAPI_KEY is not set; skipping news fetch")
            return

        now = timezone.now()

        last_item = (
            Item.objects.filter(source=self.source_id)
            .order_by("-fetched_at")
            .first()
        )
        since = last_item.fetched_at if last_item else None

        response = requests.get(
            NEWSAPI_URL,
            params={
                "country": self.country,
                "pageSize": self.num_stories,
                "apiKey": api_key,
            },
            timeout=30,
        )
        response.raise_for_status()
        articles = response.json().get("articles", [])

        for article in articles:
            url = article.get("url")
            if not url:
                continue

            published_at = _parse_published_at(article.get("publishedAt", ""))
            if since and published_at and published_at <= since:
                continue

            url_hash = hashlib.sha1(url.encode()).hexdigest()[:16]
            external_id = f"news-{url_hash}"

            if Item.objects.filter(external_id=external_id).exists():
                logger.debug("Skipping already-fetched article: %s", external_id)
                continue

            try:
                Item.objects.create(
                    external_id=external_id,
                    source=self.source_id,
                    title=article.get("title", "") or "",
                    summary=article.get("description", "") or "",
                    url=url,
                    metadata={
                        "source_name": (article.get("source") or {}).get("name", ""),
                        "author": article.get("author", "") or "",
                        "published_at": article.get("publishedAt", "") or "",
                    },
                    expires_at=now + timedelta(hours=24),
                )
                logger.info("Fetched article: %s", external_id)
            except Exception:
                logger.exception("Failed to save article: %s", external_id)
