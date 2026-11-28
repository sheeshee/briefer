import json
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from actions.todoist import TodoistAction
from core.models import ActionError, Item


@pytest.fixture
def usage_item(db):
    return Item.objects.create(source="claude-usage", external_id="claude-usage-2026-11-28",
                               title="Claude: 87% of weekly limit left",
                               url="https://pi.example/dash/dashboards/abc")


def _ok():
    resp = MagicMock(status_code=200)
    return resp


@pytest.mark.django_db
class TestTodoistAction:
    @override_settings(TODOIST_API_TOKEN="tok")
    @patch("actions.todoist.requests.post")
    def test_creates_task_due_today_with_link(self, mock_post, usage_item):
        mock_post.return_value = _ok()

        TodoistAction("check Claude usage").execute(usage_item)

        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.todoist.com/api/v1/tasks"
        assert kwargs["json"] == {
            "content": "[check Claude usage](https://pi.example/dash/dashboards/abc)",
            "due_string": "today",
        }
        assert kwargs["headers"]["Authorization"] == "Bearer tok"
        assert ActionError.objects.count() == 0

    @override_settings(TODOIST_API_TOKEN="tok")
    @patch("actions.todoist.requests.post")
    def test_without_url_uses_plain_text(self, mock_post, db):
        item = Item.objects.create(source="claude-usage", external_id="x", title="t")
        mock_post.return_value = _ok()

        TodoistAction("check Claude usage").execute(item)

        assert mock_post.call_args.kwargs["json"]["content"] == "check Claude usage"

    @override_settings(TODOIST_API_TOKEN="tok")
    @patch("actions.todoist.requests.post")
    def test_http_error_recorded(self, mock_post, usage_item, caplog):
        mock_post.return_value = MagicMock(status_code=403)

        TodoistAction("check Claude usage").execute(usage_item)

        err = ActionError.objects.get()
        assert err.action_id == "todoist"
        assert "HTTP 403" in err.error
        assert any(r.levelname == "ERROR" for r in caplog.records)

    @override_settings(TODOIST_API_TOKEN="")
    @patch("actions.todoist.requests.post")
    def test_missing_token_recorded(self, mock_post, usage_item):
        TodoistAction("check Claude usage").execute(usage_item)

        mock_post.assert_not_called()
        assert "TODOIST_API_TOKEN" in ActionError.objects.get().error


@pytest.mark.django_db
class TestActionRouting:
    def _action(self, client, item):
        client.post(f"/items/{item.id}/action/", data=json.dumps({"action": "actioned"}),
                    content_type="application/json")

    def test_claude_usage_goes_to_todoist_not_raindrop(self, client, usage_item):
        with patch("core.views.RaindropAction.execute") as rd, \
             patch("core.views.TodoistAction.execute") as td:
            self._action(client, usage_item)
        td.assert_called_once_with(usage_item)
        rd.assert_not_called()

    def test_other_items_still_go_to_raindrop(self, client, db):
        item = Item.objects.create(source="bbc", external_id="b1", title="News", url="https://x")
        with patch("core.views.RaindropAction.execute") as rd, \
             patch("core.views.TodoistAction.execute") as td:
            self._action(client, item)
        rd.assert_called_once_with(item)
        td.assert_not_called()
