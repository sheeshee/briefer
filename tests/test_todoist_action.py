import json
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from core.models import ActionError, Item


@pytest.fixture
def item(user):
    return Item.objects.create(
        user=user,
        source="test",
        external_id="todoist-test-1",
        title="My Test Item",
        url="https://example.com/article",
    )


@pytest.fixture
def item_no_url(user):
    return Item.objects.create(
        user=user,
        source="test",
        external_id="todoist-test-2",
        title="No URL Item",
    )


@pytest.mark.django_db
class TestTodoistAction:
    def _make_action(self):
        from actions.todoist import TodoistAction
        return TodoistAction()

    def test_creates_todoist_task(self, item, settings):
        settings.TODOIST_API_TOKEN = "test-token"
        mock_response = MagicMock()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_response) as mock_open:
            self._make_action().execute(item)
        mock_open.assert_called_once()
        req = mock_open.call_args[0][0]
        assert req.get_header("Authorization") == "Bearer test-token"
        body = json.loads(req.data)
        assert "[My Test Item](https://example.com/article)" == body["content"]
        assert body["labels"] == ["briefer"]

    def test_title_only_when_no_url(self, item_no_url, settings):
        settings.TODOIST_API_TOKEN = "test-token"
        mock_response = MagicMock()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_response) as mock_open:
            self._make_action().execute(item_no_url)
        req = mock_open.call_args[0][0]
        body = json.loads(req.data)
        assert body["content"] == "No URL Item"

    def test_skips_when_no_token(self, item, settings):
        settings.TODOIST_API_TOKEN = ""
        with patch("urllib.request.urlopen") as mock_open:
            self._make_action().execute(item)
        mock_open.assert_not_called()
        assert ActionError.objects.count() == 0

    def test_records_action_error_on_http_failure(self, item, settings):
        settings.TODOIST_API_TOKEN = "test-token"
        http_error = urllib.error.HTTPError(
            url="https://api.todoist.com/rest/v2/tasks",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=BytesIO(b""),
        )
        with patch("urllib.request.urlopen", side_effect=http_error):
            self._make_action().execute(item)
        assert ActionError.objects.count() == 1
        err = ActionError.objects.first()
        assert err.item == item
        assert err.action_id == "todoist"
        assert "401" in err.error

    def test_records_action_error_on_network_failure(self, item, settings):
        settings.TODOIST_API_TOKEN = "test-token"
        with patch("urllib.request.urlopen", side_effect=OSError("timeout")):
            self._make_action().execute(item)
        assert ActionError.objects.count() == 1
        assert "timeout" in ActionError.objects.first().error

    def test_does_not_raise_on_failure(self, item, settings):
        settings.TODOIST_API_TOKEN = "test-token"
        with patch("urllib.request.urlopen", side_effect=Exception("boom")):
            self._make_action().execute(item)  # must not raise
