"""The RSS feed of a Raindrop collection (Unsorted by default), read by Kindly."""
import logging
import xml.etree.ElementTree as ET
from unittest.mock import patch

import pytest
from django.urls import reverse

from tests.test_raindrop_action import _response

RAINDROPS = {
    "result": True,
    "count": 2,
    "items": [
        {
            "_id": 111,
            "title": "An Italian folding bicycle",
            "link": "https://www.core77.com/posts/folding-bike",
            "excerpt": "It fits into a suitcase.",
            "created": "2026-11-25T10:00:00.000Z",
        },
        {
            "_id": 222,
            "title": "",
            "link": "https://example.com/untitled",
            "excerpt": "",
            "created": "2026-11-24T09:30:00.000Z",
        },
    ],
}


@pytest.fixture
def feed_settings(settings, db):
    settings.RAINDROP_TEST_TOKEN = "test-token"
    settings.RAINDROP_FEED_COLLECTION_ID = "-1"
    return settings


def _get(client):
    return client.get(reverse("raindrop-feed"))


def _items(resp):
    return ET.fromstring(resp.content).findall("./channel/item")


@patch("actions.raindrop.requests.get")
def test_feed_lists_the_collection_newest_first(mock_get, client, feed_settings):
    mock_get.return_value = _response(200, RAINDROPS)

    resp = _get(client)

    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("application/rss+xml")
    items = _items(resp)
    assert [i.findtext("link") for i in items] == [
        "https://www.core77.com/posts/folding-bike",
        "https://example.com/untitled",
    ]
    first = items[0]
    assert first.findtext("title") == "An Italian folding bicycle"
    assert first.findtext("description") == "It fits into a suitcase."
    assert first.findtext("pubDate") == "Wed, 25 Nov 2026 10:00:00 +0000"


@patch("actions.raindrop.requests.get")
def test_feed_asks_raindrop_for_the_configured_collection(mock_get, client, feed_settings):
    mock_get.return_value = _response(200, RAINDROPS)

    _get(client)

    url = mock_get.call_args.args[0]
    assert url.endswith("/raindrops/-1")
    assert mock_get.call_args.kwargs["params"]["sort"] == "-created"
    assert mock_get.call_args.kwargs["headers"]["Authorization"] == "Bearer test-token"


@patch("actions.raindrop.requests.get")
def test_guid_is_the_raindrop_id_not_the_link(mock_get, client, feed_settings):
    # Kindly keeps guids unique across all its feeds: a link could also be in
    # another feed, a Raindrop id can't.
    mock_get.return_value = _response(200, RAINDROPS)

    guid = _items(_get(client))[0].find("guid")

    assert guid.text == "raindrop-111"
    assert guid.get("isPermaLink") == "false"


@patch("actions.raindrop.requests.get")
def test_untitled_item_falls_back_to_its_link(mock_get, client, feed_settings):
    mock_get.return_value = _response(200, RAINDROPS)

    assert _items(_get(client))[1].findtext("title") == "https://example.com/untitled"


@patch("actions.raindrop.requests.get")
def test_feed_has_no_full_content(mock_get, client, feed_settings):
    # With content:encoded Kindly would show the excerpt instead of
    # downloading the page.
    mock_get.return_value = _response(200, RAINDROPS)

    assert b"content:encoded" not in _get(client).content


@patch("actions.raindrop.requests.get")
def test_raindrop_outage_is_a_502_and_a_warning(mock_get, client, feed_settings, caplog):
    mock_get.return_value = _response(503)

    with caplog.at_level(logging.WARNING):
        resp = _get(client)

    assert resp.status_code == 502
    assert [r.levelname for r in caplog.records if "feed" in r.getMessage()] == ["WARNING"]


@patch("actions.raindrop.requests.get")
def test_rejected_token_is_an_error(mock_get, client, feed_settings, caplog):
    # A dead token needs Sam: ERROR reaches the OpenObserve alert.
    mock_get.return_value = _response(401)

    with caplog.at_level(logging.WARNING):
        resp = _get(client)

    assert resp.status_code == 502
    assert [r.levelname for r in caplog.records if "feed" in r.getMessage()] == ["ERROR"]


def test_not_connected_is_an_error(client, settings, db, caplog):
    settings.RAINDROP_TEST_TOKEN = ""
    settings.RAINDROP_FEED_COLLECTION_ID = "-1"

    with caplog.at_level(logging.WARNING):
        resp = _get(client)

    assert resp.status_code == 502
    assert [r.levelname for r in caplog.records if "feed" in r.getMessage()] == ["ERROR"]
