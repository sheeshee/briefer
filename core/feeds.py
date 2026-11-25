"""RSS feed of a Raindrop collection, so Kindly (the e-ink reader) can read
what Sam bookmarked. Raindrop only gives RSS for public collections, and
Unsorted can't be public, so briefer builds the feed from the API itself.
"""
from datetime import datetime

from django.contrib.syndication.views import Feed
from django.urls import reverse


class RaindropFeed(Feed):
    title = "Raindrop: Unsorted"
    description = "Bookmarks saved to Raindrop, newest first."

    def __init__(self, raindrops):
        super().__init__()
        self.raindrops = raindrops

    def link(self):
        return reverse("stack")

    def items(self):
        return self.raindrops

    def item_title(self, item):
        return item.get("title") or item["link"]

    # Only a description: with content:encoded Kindly would show this
    # instead of downloading the page.
    def item_description(self, item):
        return item.get("excerpt", "")

    def item_link(self, item):
        return item["link"]

    # Kindly keeps guids unique across all its feeds, so not the link
    def item_guid(self, item):
        return f"raindrop-{item['_id']}"

    item_guid_is_permalink = False

    def item_pubdate(self, item):
        return datetime.fromisoformat(item["created"])
