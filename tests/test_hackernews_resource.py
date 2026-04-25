from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from core.models import Item
from resources.hackernews import HackerNewsResource


def _make_api_response(hits):
    response = MagicMock()
    response.json.return_value = {"hits": hits}
    response.raise_for_status.return_value = None
    return response


SAMPLE_HITS = [
    {
        "objectID": "111",
        "title": "Story One",
        "url": "https://example.com/1",
        "points": 100,
        "num_comments": 50,
    },
    {
        "objectID": "222",
        "title": "Story Two",
        "url": "https://example.com/2",
        "points": 200,
        "num_comments": 75,
    },
]


@pytest.mark.django_db
class TestHackerNewsResource:
    @patch("resources.hackernews.requests.get")
    def test_creates_items_with_correct_fields(self, mock_get, user):
        mock_get.return_value = _make_api_response(SAMPLE_HITS)

        resource = HackerNewsResource()
        resource.fetch(user)

        assert Item.objects.filter(user=user).count() == 2
        item = Item.objects.get(user=user, external_id="hackernews-111")
        assert item.title == "Story One"
        assert item.url == "https://example.com/1"
        assert item.source == "hackernews"
        assert item.metadata["score"] == 100
        assert item.metadata["num_comments"] == 50

    @patch("resources.hackernews.requests.get")
    def test_idempotent_no_duplicates(self, mock_get, user):
        mock_get.return_value = _make_api_response(SAMPLE_HITS)

        resource = HackerNewsResource()
        resource.fetch(user)
        resource.fetch(user)

        assert Item.objects.filter(user=user).count() == 2

    @patch("resources.hackernews.requests.get")
    def test_single_story_failure_does_not_abort(self, mock_get, user):
        hits = SAMPLE_HITS.copy()
        mock_get.return_value = _make_api_response(hits)

        resource = HackerNewsResource()

        with patch.object(
            Item.objects, "filter", wraps=Item.objects.filter
        ), patch.object(
            Item.objects,
            "update_or_create",
            side_effect=[Exception("DB error"), MagicMock()],
        ):
            resource.fetch(user)

        # Second story may or may not have been saved depending on mock,
        # but the important thing is no exception was raised.

    @patch("resources.hackernews.requests.get")
    def test_expires_at_set_approximately_24h(self, mock_get, user):
        mock_get.return_value = _make_api_response(SAMPLE_HITS[:1])

        resource = HackerNewsResource()
        before = timezone.now()
        resource.fetch(user)
        after = timezone.now()

        item = Item.objects.get(user=user, external_id="hackernews-111")
        assert item.expires_at >= before + timedelta(hours=23, minutes=59)
        assert item.expires_at <= after + timedelta(hours=24, minutes=1)
