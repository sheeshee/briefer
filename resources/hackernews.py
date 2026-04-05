import logging
from datetime import timedelta

import requests
from django.utils import timezone

from core.models import Item
from resources.base import BaseResource

logger = logging.getLogger(__name__)

HN_API_URL = "https://hn.algolia.com/api/v1/search"


class HackerNewsResource(BaseResource):

    source_id = "hackernews"

    def __init__(self, num_stories: int = 10):
        self.num_stories = num_stories

    def fetch(self) -> None:
        now = timezone.now()
        today = now.date()

        response = requests.get(
            HN_API_URL,
            params={"tags": "front_page", "hitsPerPage": self.num_stories},
            timeout=30,
        )
        response.raise_for_status()
        hits = response.json().get("hits", [])

        for hit in hits:
            story_id = hit.get("objectID")
            if not story_id:
                continue

            external_id = f"hackernews-{story_id}"

            existing = Item.objects.filter(
                external_id=external_id,
                fetched_at__date=today,
            ).exists()
            if existing:
                logger.debug("Skipping already-fetched story: %s", external_id)
                continue

            try:
                Item.objects.update_or_create(
                    external_id=external_id,
                    defaults={
                        "source": self.source_id,
                        "title": hit.get("title", ""),
                        "summary": "",
                        "url": hit.get("url") or "",
                        "metadata": {
                            "score": hit.get("points", 0),
                            "num_comments": hit.get("num_comments", 0),
                        },
                        "expires_at": now + timedelta(hours=24),
                    },
                )
                logger.info("Fetched story: %s", external_id)
            except Exception:
                logger.exception("Failed to save story: %s", external_id)
