from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from core.models import Item
from resources.news import NewsAPIResource


def _make_api_response(articles):
    response = MagicMock()
    response.json.return_value = {"status": "ok", "articles": articles}
    response.raise_for_status.return_value = None
    return response


SAMPLE_ARTICLES = [
    {
        "source": {"id": "bbc-news", "name": "BBC News"},
        "author": "Jane Doe",
        "title": "Breaking: Something happened",
        "description": "A short summary of the event.",
        "url": "https://example.com/news/1",
        "publishedAt": "2026-04-19T10:00:00Z",
    },
    {
        "source": {"id": "reuters", "name": "Reuters"},
        "author": "John Smith",
        "title": "Markets react to news",
        "description": "Markets moved after the announcement.",
        "url": "https://example.com/news/2",
        "publishedAt": "2026-04-19T11:00:00Z",
    },
]


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    monkeypatch.setenv("NEWSAPI_KEY", "test-key")


@pytest.mark.django_db
class TestNewsAPIResource:
    @patch("resources.news.requests.get")
    def test_creates_items_with_correct_fields(self, mock_get, user):
        mock_get.return_value = _make_api_response(SAMPLE_ARTICLES)

        NewsAPIResource().fetch(user)

        assert Item.objects.filter(user=user).count() == 2
        item = Item.objects.get(user=user, url="https://example.com/news/1")
        assert item.title == "Breaking: Something happened"
        assert item.summary == "A short summary of the event."
        assert item.source == "news"
        assert item.metadata["source_name"] == "BBC News"
        assert item.metadata["author"] == "Jane Doe"
        assert item.metadata["published_at"] == "2026-04-19T10:00:00Z"

    @patch("resources.news.requests.get")
    def test_passes_api_key_and_page_size(self, mock_get, user):
        mock_get.return_value = _make_api_response([])

        NewsAPIResource(num_stories=10).fetch(user)

        _, kwargs = mock_get.call_args
        assert kwargs["params"]["apiKey"] == "test-key"
        assert kwargs["params"]["pageSize"] == 10

    @patch("resources.news.requests.get")
    def test_idempotent_no_duplicates(self, mock_get, user):
        mock_get.return_value = _make_api_response(SAMPLE_ARTICLES)

        NewsAPIResource().fetch(user)
        NewsAPIResource().fetch(user)

        assert Item.objects.filter(user=user).count() == 2

    @patch("resources.news.requests.get")
    def test_filters_articles_published_before_last_run(self, mock_get, user):
        now = timezone.now()
        # Seed a prior item so "since last run" is non-null.
        Item.objects.create(
            user=user,
            external_id="news-seed",
            source="news",
            title="Old",
            url="https://example.com/old",
        )
        # Force the seeded item's fetched_at to a known value.
        Item.objects.filter(user=user, external_id="news-seed").update(
            fetched_at=now - timedelta(hours=1)
        )

        old_ts = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        new_ts = (now + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        articles = [
            {
                "source": {"name": "X"},
                "title": "Old story",
                "description": "",
                "url": "https://example.com/news/old-story",
                "publishedAt": old_ts,
            },
            {
                "source": {"name": "Y"},
                "title": "New story",
                "description": "",
                "url": "https://example.com/news/new-story",
                "publishedAt": new_ts,
            },
        ]
        mock_get.return_value = _make_api_response(articles)

        NewsAPIResource().fetch(user)

        assert Item.objects.filter(user=user, url="https://example.com/news/new-story").exists()
        assert not Item.objects.filter(
            user=user, url="https://example.com/news/old-story"
        ).exists()

    @patch("resources.news.requests.get")
    def test_missing_api_key_skips_without_error(self, mock_get, user, monkeypatch):
        monkeypatch.delenv("NEWSAPI_KEY", raising=False)

        NewsAPIResource().fetch(user)

        mock_get.assert_not_called()
        assert Item.objects.filter(user=user, source="news").count() == 0

    @patch("resources.news.requests.get")
    def test_expires_at_set_approximately_24h(self, mock_get, user):
        mock_get.return_value = _make_api_response(SAMPLE_ARTICLES[:1])

        before = timezone.now()
        NewsAPIResource().fetch(user)
        after = timezone.now()

        item = Item.objects.get(user=user, url="https://example.com/news/1")
        assert item.expires_at >= before + timedelta(hours=23, minutes=59)
        assert item.expires_at <= after + timedelta(hours=24, minutes=1)
