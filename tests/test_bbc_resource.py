from unittest.mock import MagicMock, patch

import pytest

from core.models import Item
from resources.bbc import BBCFeedResource


def _rss(items_xml):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>BBC News</title>{items_xml}</channel></rss>""".encode()


def _item(n):
    return f"""<item>
  <title><![CDATA[Story {n}]]></title>
  <description><![CDATA[Summary {n}]]></description>
  <link>https://www.bbc.co.uk/news/articles/a{n}?at_medium=RSS&amp;at_campaign=rss</link>
  <guid isPermaLink="false">https://www.bbc.co.uk/news/articles/a{n}#0</guid>
  <pubDate>Fri, 27 Nov 2026 10:00:00 GMT</pubDate>
</item>"""


def _response(body):
    response = MagicMock()
    response.content = body
    response.raise_for_status.return_value = None
    return response


@pytest.mark.django_db
class TestBBCFeedResource:
    @patch("resources.bbc.requests.get")
    def test_creates_items_with_clean_urls(self, mock_get):
        mock_get.return_value = _response(_rss(_item(1) + _item(2)))

        BBCFeedResource("bbc", "https://feeds.bbci.co.uk/news/rss.xml").fetch()

        assert Item.objects.count() == 2
        item = Item.objects.get(title="Story 1")
        assert item.source == "bbc"
        assert item.summary == "Summary 1"
        assert item.url == "https://www.bbc.co.uk/news/articles/a1"
        assert item.expires_at is not None
        assert item.metadata["published_at"] == "Fri, 27 Nov 2026 10:00:00 GMT"

    @patch("resources.bbc.requests.get")
    def test_limits_number_of_stories(self, mock_get):
        mock_get.return_value = _response(_rss("".join(_item(n) for n in range(10))))

        BBCFeedResource("bbc", "https://x/rss.xml", num_stories=3).fetch()

        assert Item.objects.count() == 3

    @patch("resources.bbc.requests.get")
    def test_idempotent(self, mock_get):
        mock_get.return_value = _response(_rss(_item(1)))
        resource = BBCFeedResource("bbc", "https://x/rss.xml")

        resource.fetch()
        resource.fetch()

        assert Item.objects.count() == 1

    @patch("resources.bbc.requests.get")
    def test_story_in_two_feeds_is_saved_once(self, mock_get):
        mock_get.return_value = _response(_rss(_item(1)))

        BBCFeedResource("bbc", "https://x/rss.xml").fetch()
        BBCFeedResource("bbc-wales", "https://y/rss.xml").fetch()

        assert Item.objects.count() == 1
        assert Item.objects.get().source == "bbc"

    @patch("resources.bbc.requests.get")
    def test_does_not_resurface_dismissed_story(self, mock_get):
        mock_get.return_value = _response(_rss(_item(1)))
        resource = BBCFeedResource("bbc", "https://x/rss.xml")
        resource.fetch()
        Item.objects.update(state=Item.State.DISMISSED)

        resource.fetch()

        assert Item.objects.get().state == Item.State.DISMISSED
