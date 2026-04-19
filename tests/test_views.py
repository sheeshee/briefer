import json
from unittest.mock import patch

import pytest
from django.test import Client

from core.models import ActionError, Item


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def pending_item(db):
    return Item.objects.create(
        source="test",
        external_id="view-test-1",
        title="Test Item",
        url="https://example.com",
    )


@pytest.mark.django_db
class TestStackView:
    def test_get_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_renders_pending_items(self, client, pending_item):
        response = client.get("/")
        assert pending_item.title.encode() in response.content

    def test_pending_count_in_context(self, client, pending_item):
        response = client.get("/")
        assert response.context["pending_count"] == 1

    def test_actioned_count_in_context(self, client, db):
        Item.objects.create(
            source="test", external_id="act-1", title="Actioned", state=Item.State.ACTIONED
        )
        response = client.get("/")
        assert response.context["actioned_count"] == 1

    def test_counts_rendered_in_html(self, client, pending_item):
        response = client.get("/")
        assert b'id="pending-count"' in response.content
        assert b'id="actioned-count"' in response.content


@pytest.mark.django_db
class TestResetView:
    def test_post_resets_items_to_pending(self, client, db):
        Item.objects.create(source="t", external_id="r1", title="A", state=Item.State.SEEN)
        Item.objects.create(source="t", external_id="r2", title="B", state=Item.State.ACTIONED)
        Item.objects.create(source="t", external_id="r3", title="C", state=Item.State.DISMISSED)
        client.post("/reset/")
        assert Item.objects.filter(state=Item.State.PENDING).count() == 3

    def test_post_redirects_to_stack(self, client):
        response = client.post("/reset/")
        assert response.status_code == 302
        assert response["Location"] == "/"

    def test_get_not_allowed(self, client):
        response = client.get("/reset/")
        assert response.status_code == 405


@pytest.mark.django_db
class TestFetchView:
    def test_post_redirects_to_stack(self, client):
        response = client.post("/fetch/")
        assert response.status_code == 302
        assert response["Location"] == "/"

    def test_get_not_allowed(self, client):
        response = client.get("/fetch/")
        assert response.status_code == 405

    def test_without_include_fake_passes_false(self, client):
        with patch("core.views.call_command") as mock_cmd:
            client.post("/fetch/")
            mock_cmd.assert_called_once_with("fetch_resources", include_fake=False)

    def test_with_include_fake_passes_true(self, client):
        with patch("core.views.call_command") as mock_cmd:
            client.post("/fetch/", data={"include_fake": "on"})
            mock_cmd.assert_called_once_with("fetch_resources", include_fake=True)


@pytest.mark.django_db
class TestHistoryView:
    def test_get_returns_200(self, client, db):
        response = client.get("/history/")
        assert response.status_code == 200

    def test_renders_all_items(self, client, db):
        Item.objects.create(source="s", external_id="h1", title="Pending Item")
        Item.objects.create(source="s", external_id="h2", title="Seen Item", state=Item.State.SEEN)
        Item.objects.create(source="s", external_id="h3", title="Actioned Item", state=Item.State.ACTIONED)
        response = client.get("/history/")
        assert b"Pending Item" in response.content
        assert b"Seen Item" in response.content
        assert b"Actioned Item" in response.content

    def test_shows_state_badge(self, client, db):
        Item.objects.create(source="s", external_id="h4", title="X", state=Item.State.ACTIONED)
        response = client.get("/history/")
        assert b"actioned" in response.content

    def test_pagination_second_page(self, client, db):
        for i in range(55):
            Item.objects.create(source="s", external_id=f"p{i}", title=f"Item {i}")
        response = client.get("/history/?page=2")
        assert response.status_code == 200
        assert b"Item" in response.content

    def test_get_only(self, client, db):
        response = client.post("/history/")
        assert response.status_code == 405


@pytest.mark.django_db
class TestActionErrorViews:
    def _make_error(self, db):
        item = Item.objects.create(source="s", external_id="ae1", title="Broken Item")
        return ActionError.objects.create(item=item, action_id="todoist", error="HTTP 401")

    def test_list_returns_200(self, client, db):
        response = client.get("/errors/")
        assert response.status_code == 200

    def test_list_shows_errors(self, client, db):
        err = self._make_error(db)
        response = client.get("/errors/")
        assert b"Broken Item" in response.content
        assert b"todoist" in response.content

    def test_detail_returns_200(self, client, db):
        err = self._make_error(db)
        response = client.get(f"/errors/{err.pk}/")
        assert response.status_code == 200

    def test_detail_shows_error_message(self, client, db):
        err = self._make_error(db)
        response = client.get(f"/errors/{err.pk}/")
        assert b"HTTP 401" in response.content

    def test_detail_404_for_missing(self, client, db):
        response = client.get("/errors/99999/")
        assert response.status_code == 404

    def test_list_get_only(self, client, db):
        assert client.post("/errors/").status_code == 405

    def test_detail_get_only(self, client, db):
        err = self._make_error(db)
        assert client.post(f"/errors/{err.pk}/").status_code == 405


@pytest.mark.django_db
class TestActionedTriggersTodoist:
    def test_actioned_calls_todoist_execute(self, client, db):
        item = Item.objects.create(source="s", external_id="td1", title="Trigger Test")
        with patch("core.views.TodoistAction.execute") as mock_exec:
            client.post(
                f"/items/{item.id}/action/",
                data=json.dumps({"action": "actioned"}),
                content_type="application/json",
            )
        mock_exec.assert_called_once_with(item)


@pytest.mark.django_db
class TestItemActionView:
    def test_seen_sets_state(self, client, pending_item):
        response = client.post(
            f"/items/{pending_item.id}/action/",
            data=json.dumps({"action": "seen"}),
            content_type="application/json",
        )
        assert response.status_code == 204
        pending_item.refresh_from_db()
        assert pending_item.state == Item.State.SEEN

    def test_actioned_sets_state_and_timestamp(self, client, pending_item):
        response = client.post(
            f"/items/{pending_item.id}/action/",
            data=json.dumps({"action": "actioned"}),
            content_type="application/json",
        )
        assert response.status_code == 204
        pending_item.refresh_from_db()
        assert pending_item.state == Item.State.ACTIONED
        assert pending_item.actioned_at is not None

    def test_dismissed_sets_state(self, client, pending_item):
        response = client.post(
            f"/items/{pending_item.id}/action/",
            data=json.dumps({"action": "dismissed"}),
            content_type="application/json",
        )
        assert response.status_code == 204
        pending_item.refresh_from_db()
        assert pending_item.state == Item.State.DISMISSED

    def test_invalid_action_returns_400(self, client, pending_item):
        response = client.post(
            f"/items/{pending_item.id}/action/",
            data=json.dumps({"action": "invalid"}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_nonexistent_item_returns_404(self, client):
        response = client.post(
            "/items/99999/action/",
            data=json.dumps({"action": "seen"}),
            content_type="application/json",
        )
        assert response.status_code == 404

    def test_form_post_works(self, client, pending_item):
        response = client.post(
            f"/items/{pending_item.id}/action/",
            data={"action": "seen"},
        )
        assert response.status_code == 204
        pending_item.refresh_from_db()
        assert pending_item.state == Item.State.SEEN
