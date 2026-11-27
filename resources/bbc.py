import hashlib
import logging
import xml.etree.ElementTree as ET
from datetime import timedelta
from urllib.parse import urlsplit, urlunsplit

import requests
from django.utils import timezone

from core.models import Item
from resources.base import BaseResource

logger = logging.getLogger(__name__)


def _strip_query(url: str) -> str:
    """Drop the ?at_medium=RSS&at_campaign=rss tracking parameters."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


class BBCFeedResource(BaseResource):
    """Top stories from one BBC News RSS feed.

    The same story often appears in several BBC feeds (e.g. Top stories and
    Wales), so the external_id depends only on the story's guid: the first
    feed to fetch it wins and the others skip it.
    """

    def __init__(self, source_id: str, feed_url: str, num_stories: int = 5):
        self.source_id = source_id
        self.feed_url = feed_url
        self.num_stories = num_stories

    def fetch(self) -> None:
        now = timezone.now()

        response = requests.get(self.feed_url, timeout=30)
        response.raise_for_status()
        root = ET.fromstring(response.content)

        for entry in root.findall("./channel/item")[: self.num_stories]:
            link = (entry.findtext("link") or "").strip()
            guid = (entry.findtext("guid") or link).strip()
            if not guid:
                continue

            url = _strip_query(link)
            story_key = _strip_query(guid).split("#")[0]
            external_id = "bbc-" + hashlib.sha1(story_key.encode()).hexdigest()[:16]

            if Item.objects.filter(external_id=external_id).exists():
                logger.debug("Skipping already-fetched story: %s", external_id)
                continue

            try:
                Item.objects.create(
                    external_id=external_id,
                    source=self.source_id,
                    title=(entry.findtext("title") or "").strip(),
                    summary=(entry.findtext("description") or "").strip(),
                    url=url,
                    metadata={
                        "feed": self.feed_url,
                        "published_at": (entry.findtext("pubDate") or "").strip(),
                    },
                    expires_at=now + timedelta(hours=24),
                )
                logger.info("Fetched story: %s", external_id)
            except Exception:
                logger.exception("Failed to save story: %s", external_id)
