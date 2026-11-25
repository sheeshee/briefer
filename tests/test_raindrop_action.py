from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
import requests
from django.utils import timezone

from core.models import ActionError, Item, RaindropToken


def _response(status=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data or {}
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(f"{status} Error", response=resp)
    else:
        resp.raise_for_status.return_value = None
    return resp


@pytest.fixture
def item(db):
    return Item.objects.create(
        source="test",
        external_id="raindrop-test-1",
        title="My Test Item",
        url="https://example.com/article",
    )


@pytest.fixture
def item_no_url(db):
    return Item.objects.create(source="test", external_id="raindrop-test-2", title="No URL Item")


@pytest.fixture
def oauth_settings(settings):
    settings.RAINDROP_CLIENT_ID = "cid"
    settings.RAINDROP_CLIENT_SECRET = "csecret"
    settings.RAINDROP_REDIRECT_URI = "https://pi.example/briefer/raindrop/callback/"
    settings.RAINDROP_TEST_TOKEN = ""
    settings.RAINDROP_COLLECTION_ID = ""
    return settings


@pytest.fixture
def token(db):
    return RaindropToken.objects.create(
        pk=1,
        access_token="access-1",
        refresh_token="refresh-1",
        expires_at=timezone.now() + timedelta(days=10),
    )


def _action():
    from actions.raindrop import RaindropAction
    return RaindropAction()


@pytest.mark.django_db
class TestRaindropAction:
    def test_creates_bookmark(self, item, oauth_settings, token):
        with patch("actions.raindrop.requests.post", return_value=_response()) as post:
            _action().execute(item)
        post.assert_called_once()
        url = post.call_args.args[0]
        kwargs = post.call_args.kwargs
        assert url == "https://api.raindrop.io/rest/v1/raindrop"
        assert kwargs["headers"]["Authorization"] == "Bearer access-1"
        body = kwargs["json"]
        assert body["link"] == "https://example.com/article"
        assert body["title"] == "My Test Item"
        assert body["tags"] == ["briefer"]
        assert body["pleaseParse"] == {}
        assert "collection" not in body

    def test_sets_collection_when_configured(self, item, oauth_settings, token):
        oauth_settings.RAINDROP_COLLECTION_ID = "12345"
        with patch("actions.raindrop.requests.post", return_value=_response()) as post:
            _action().execute(item)
        assert post.call_args.kwargs["json"]["collection"] == {"$id": 12345}

    def test_test_token_overrides_oauth(self, item, oauth_settings):
        oauth_settings.RAINDROP_TEST_TOKEN = "test-tok"
        with patch("actions.raindrop.requests.post", return_value=_response()) as post:
            _action().execute(item)
        assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer test-tok"

    def test_skips_when_not_configured(self, item, settings):
        settings.RAINDROP_CLIENT_ID = ""
        settings.RAINDROP_TEST_TOKEN = ""
        with patch("actions.raindrop.requests.post") as post:
            _action().execute(item)
        post.assert_not_called()
        assert ActionError.objects.count() == 0

    def test_records_error_when_not_connected(self, item, oauth_settings):
        with patch("actions.raindrop.requests.post") as post:
            _action().execute(item)
        post.assert_not_called()
        err = ActionError.objects.get()
        assert err.action_id == "raindrop"
        assert "not connected" in err.error

    def test_records_error_when_item_has_no_url(self, item_no_url, oauth_settings, token):
        with patch("actions.raindrop.requests.post") as post:
            _action().execute(item_no_url)
        post.assert_not_called()
        assert "no URL" in ActionError.objects.get().error

    def test_refreshes_expiring_token(self, item, oauth_settings, token):
        token.expires_at = timezone.now() + timedelta(hours=1)
        token.save()
        refreshed = _response(json_data={
            "access_token": "access-2", "refresh_token": "refresh-2", "expires_in": 1209599,
        })
        with patch("actions.raindrop.requests.post", side_effect=[refreshed, _response()]) as post:
            _action().execute(item)
        refresh_call, create_call = post.call_args_list
        assert refresh_call.args[0] == "https://raindrop.io/oauth/access_token"
        assert refresh_call.kwargs["json"] == {
            "client_id": "cid", "client_secret": "csecret",
            "grant_type": "refresh_token", "refresh_token": "refresh-1",
        }
        assert create_call.kwargs["headers"]["Authorization"] == "Bearer access-2"
        token.refresh_from_db()
        assert token.access_token == "access-2"
        assert token.refresh_token == "refresh-2"
        assert token.expires_at > timezone.now() + timedelta(days=13)

    def test_records_error_on_http_failure(self, item, oauth_settings, token):
        with patch("actions.raindrop.requests.post", return_value=_response(status=401)):
            _action().execute(item)
        err = ActionError.objects.get()
        assert err.item == item
        assert err.action_id == "raindrop"
        assert "401" in err.error

    def test_does_not_raise_on_network_failure(self, item, oauth_settings, token):
        with patch("actions.raindrop.requests.post", side_effect=requests.ConnectionError("timeout")):
            _action().execute(item)  # must not raise
        assert "timeout" in ActionError.objects.get().error


@pytest.mark.django_db
class TestRaindropOAuthViews:
    def test_connect_redirects_to_authorize(self, client, oauth_settings):
        response = client.get("/raindrop/connect/")
        assert response.status_code == 302
        loc = response["Location"]
        assert loc.startswith("https://raindrop.io/oauth/authorize?")
        assert "client_id=cid" in loc
        assert "response_type=code" in loc
        assert "redirect_uri=https%3A%2F%2Fpi.example%2Fbriefer%2Fraindrop%2Fcallback%2F" in loc

    def test_callback_exchanges_code_and_stores_token(self, client, oauth_settings):
        resp = _response(json_data={
            "access_token": "a", "refresh_token": "r", "expires_in": 1209599,
        })
        with patch("actions.raindrop.requests.post", return_value=resp) as post:
            response = client.get("/raindrop/callback/?code=xyz")
        assert response.status_code == 302
        assert post.call_args.args[0] == "https://raindrop.io/oauth/access_token"
        assert post.call_args.kwargs["json"] == {
            "grant_type": "authorization_code", "code": "xyz",
            "client_id": "cid", "client_secret": "csecret",
            "redirect_uri": "https://pi.example/briefer/raindrop/callback/",
        }
        token = RaindropToken.objects.get()
        assert token.access_token == "a"
        assert token.refresh_token == "r"

    def test_callback_shows_error_param(self, client, oauth_settings):
        response = client.get("/raindrop/callback/?error=access_denied")
        assert response.status_code == 400
        assert b"access_denied" in response.content
        assert RaindropToken.objects.count() == 0

    def test_callback_shows_exchange_failure(self, client, oauth_settings):
        with patch("actions.raindrop.requests.post", return_value=_response(status=400)):
            response = client.get("/raindrop/callback/?code=bad")
        assert response.status_code == 400
        assert RaindropToken.objects.count() == 0

    def test_stack_shows_connect_link_when_not_connected(self, client, oauth_settings):
        response = client.get("/")
        assert b"connect raindrop" in response.content

    def test_stack_hides_connect_link_when_connected(self, client, oauth_settings, token):
        response = client.get("/")
        assert b"connect raindrop" not in response.content


@pytest.mark.django_db
class TestRaindropLogLevels:
    """ERROR-level logs reach the OpenObserve app_errors alert (ntfy); WARNING doesn't."""

    def test_token_refresh_failure_logs_error(self, item, oauth_settings, token, caplog):
        token.expires_at = timezone.now() + timedelta(hours=1)
        token.save()
        with patch("actions.raindrop.requests.post", return_value=_response(status=400)):
            _action().execute(item)
        rec = next(r for r in caplog.records if r.name == "actions.raindrop")
        assert rec.levelname == "ERROR"
        assert "token request failed" in rec.getMessage()
        assert "token request failed" in ActionError.objects.get().error

    def test_bookmark_http_failure_logs_error(self, item, oauth_settings, token, caplog):
        with patch("actions.raindrop.requests.post", return_value=_response(status=401)):
            _action().execute(item)
        rec = next(r for r in caplog.records if r.name == "actions.raindrop")
        assert rec.levelname == "ERROR"

    def test_missing_url_logs_warning(self, item_no_url, oauth_settings, token, caplog):
        _action().execute(item_no_url)
        rec = next(r for r in caplog.records if r.name == "actions.raindrop")
        assert rec.levelname == "WARNING"
