import json
from unittest.mock import patch

import pytest
from django.test import Client

from core.models import ActionError, Item


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def pending_item(db, user):
    return Item.objects.create(
        user=user,
        source="test",
        external_id="view-test-1",
        title="Test Item",
        url="https://example.com",
    )


@pytest.mark.django_db
class TestStackView:
    def test_redirects_unauthenticated(self, client):
        response = client.get("/")
        assert response.status_code == 302
        assert "/login/" in response["Location"]

    def test_get_returns_200(self, client, user):
        client.force_login(user)
        response = client.get("/")
        assert response.status_code == 200

    def test_renders_pending_items(self, client, user, pending_item):
        client.force_login(user)
        response = client.get("/")
        assert pending_item.title.encode() in response.content

    def test_does_not_render_other_users_items(self, client, user, db):
        from django.contrib.auth.models import User
        other = User.objects.create_user(username="other", password="x")
        Item.objects.create(user=other, source="s", external_id="o1", title="Other User Item")
        client.force_login(user)
        response = client.get("/")
        assert b"Other User Item" not in response.content

    def test_pending_count_in_context(self, client, user, pending_item):
        client.force_login(user)
        response = client.get("/")
        assert response.context["pending_count"] == 1

    def test_actioned_count_in_context(self, client, user, db):
        Item.objects.create(
            user=user, source="test", external_id="act-1", title="Actioned",
            state=Item.State.ACTIONED
        )
        client.force_login(user)
        response = client.get("/")
        assert response.context["actioned_count"] == 1

    def test_counts_rendered_in_html(self, client, user, pending_item):
        client.force_login(user)
        response = client.get("/")
        assert b'id="pending-count"' in response.content
        assert b'id="actioned-count"' in response.content


@pytest.mark.django_db
class TestResetView:
    def test_redirects_unauthenticated(self, client):
        response = client.post("/reset/")
        assert response.status_code == 302
        assert "/login/" in response["Location"]

    def test_post_resets_items_to_pending(self, client, user, db):
        Item.objects.create(user=user, source="t", external_id="r1", title="A", state=Item.State.SEEN)
        Item.objects.create(user=user, source="t", external_id="r2", title="B", state=Item.State.ACTIONED)
        Item.objects.create(user=user, source="t", external_id="r3", title="C", state=Item.State.DISMISSED)
        client.force_login(user)
        client.post("/reset/")
        assert Item.objects.filter(user=user, state=Item.State.PENDING).count() == 3

    def test_post_only_resets_current_users_items(self, client, user, db):
        from django.contrib.auth.models import User
        other = User.objects.create_user(username="other2", password="x")
        Item.objects.create(user=other, source="t", external_id="o1", title="O", state=Item.State.SEEN)
        Item.objects.create(user=user, source="t", external_id="u1", title="U", state=Item.State.SEEN)
        client.force_login(user)
        client.post("/reset/")
        assert Item.objects.get(user=other, external_id="o1").state == Item.State.SEEN
        assert Item.objects.get(user=user, external_id="u1").state == Item.State.PENDING

    def test_post_redirects_to_stack(self, client, user):
        client.force_login(user)
        response = client.post("/reset/")
        assert response.status_code == 302
        assert response["Location"] == "/"

    def test_get_not_allowed(self, client, user):
        client.force_login(user)
        response = client.get("/reset/")
        assert response.status_code == 405


@pytest.mark.django_db
class TestFetchView:
    def test_redirects_unauthenticated(self, client):
        response = client.post("/fetch/")
        assert response.status_code == 302
        assert "/login/" in response["Location"]

    def test_post_redirects_to_stack(self, client, user):
        client.force_login(user)
        response = client.post("/fetch/")
        assert response.status_code == 302
        assert response["Location"] == "/"

    def test_get_not_allowed(self, client, user):
        client.force_login(user)
        response = client.get("/fetch/")
        assert response.status_code == 405

    def test_without_include_fake_passes_false(self, client, user):
        client.force_login(user)
        with patch("core.views.call_command") as mock_cmd:
            client.post("/fetch/")
            mock_cmd.assert_called_once_with("fetch_resources", include_fake=False)

    def test_with_include_fake_passes_true(self, client, user):
        client.force_login(user)
        with patch("core.views.call_command") as mock_cmd:
            client.post("/fetch/", data={"include_fake": "on"})
            mock_cmd.assert_called_once_with("fetch_resources", include_fake=True)


@pytest.mark.django_db
class TestHistoryView:
    def test_redirects_unauthenticated(self, client):
        response = client.get("/history/")
        assert response.status_code == 302
        assert "/login/" in response["Location"]

    def test_get_returns_200(self, client, user, db):
        client.force_login(user)
        response = client.get("/history/")
        assert response.status_code == 200

    def test_renders_user_items(self, client, user, db):
        Item.objects.create(user=user, source="s", external_id="h1", title="Pending Item")
        Item.objects.create(user=user, source="s", external_id="h2", title="Seen Item", state=Item.State.SEEN)
        Item.objects.create(user=user, source="s", external_id="h3", title="Actioned Item", state=Item.State.ACTIONED)
        client.force_login(user)
        response = client.get("/history/")
        assert b"Pending Item" in response.content
        assert b"Seen Item" in response.content
        assert b"Actioned Item" in response.content

    def test_does_not_render_other_users_items(self, client, user, db):
        from django.contrib.auth.models import User
        other = User.objects.create_user(username="other3", password="x")
        Item.objects.create(user=other, source="s", external_id="h4", title="Other Item")
        client.force_login(user)
        response = client.get("/history/")
        assert b"Other Item" not in response.content

    def test_shows_state_badge(self, client, user, db):
        Item.objects.create(user=user, source="s", external_id="h5", title="X", state=Item.State.ACTIONED)
        client.force_login(user)
        response = client.get("/history/")
        assert b"actioned" in response.content

    def test_pagination_second_page(self, client, user, db):
        for i in range(55):
            Item.objects.create(user=user, source="s", external_id=f"p{i}", title=f"Item {i}")
        client.force_login(user)
        response = client.get("/history/?page=2")
        assert response.status_code == 200
        assert b"Item" in response.content

    def test_get_only(self, client, user, db):
        client.force_login(user)
        response = client.post("/history/")
        assert response.status_code == 405


@pytest.mark.django_db
class TestActionErrorViews:
    def _make_error(self, user):
        item = Item.objects.create(user=user, source="s", external_id="ae1", title="Broken Item")
        return ActionError.objects.create(item=item, action_id="todoist", error="HTTP 401")

    def test_redirects_unauthenticated(self, client):
        response = client.get("/errors/")
        assert response.status_code == 302
        assert "/login/" in response["Location"]

    def test_list_returns_200(self, client, user, db):
        client.force_login(user)
        response = client.get("/errors/")
        assert response.status_code == 200

    def test_list_shows_errors(self, client, user, db):
        err = self._make_error(user)
        client.force_login(user)
        response = client.get("/errors/")
        assert b"Broken Item" in response.content
        assert b"todoist" in response.content

    def test_detail_returns_200(self, client, user, db):
        err = self._make_error(user)
        client.force_login(user)
        response = client.get(f"/errors/{err.pk}/")
        assert response.status_code == 200

    def test_detail_shows_error_message(self, client, user, db):
        err = self._make_error(user)
        client.force_login(user)
        response = client.get(f"/errors/{err.pk}/")
        assert b"HTTP 401" in response.content

    def test_detail_404_for_missing(self, client, user, db):
        client.force_login(user)
        response = client.get("/errors/99999/")
        assert response.status_code == 404

    def test_list_get_only(self, client, user, db):
        client.force_login(user)
        assert client.post("/errors/").status_code == 405

    def test_detail_get_only(self, client, user, db):
        err = self._make_error(user)
        client.force_login(user)
        assert client.post(f"/errors/{err.pk}/").status_code == 405


@pytest.mark.django_db
class TestActionedTriggersTodoist:
    def test_actioned_calls_todoist_execute(self, client, user, db):
        item = Item.objects.create(user=user, source="s", external_id="td1", title="Trigger Test")
        client.force_login(user)
        with patch("core.views.TodoistAction.execute") as mock_exec:
            client.post(
                f"/items/{item.id}/action/",
                data=json.dumps({"action": "actioned"}),
                content_type="application/json",
            )
        mock_exec.assert_called_once_with(item)


@pytest.mark.django_db
class TestItemActionView:
    def test_redirects_unauthenticated(self, client, user, db):
        item = Item.objects.create(user=user, source="s", external_id="ia0", title="T")
        response = client.post(
            f"/items/{item.id}/action/",
            data=json.dumps({"action": "seen"}),
            content_type="application/json",
        )
        assert response.status_code == 302
        assert "/login/" in response["Location"]

    def test_seen_sets_state(self, client, user, pending_item):
        client.force_login(user)
        response = client.post(
            f"/items/{pending_item.id}/action/",
            data=json.dumps({"action": "seen"}),
            content_type="application/json",
        )
        assert response.status_code == 204
        pending_item.refresh_from_db()
        assert pending_item.state == Item.State.SEEN

    def test_actioned_sets_state_and_timestamp(self, client, user, pending_item):
        client.force_login(user)
        response = client.post(
            f"/items/{pending_item.id}/action/",
            data=json.dumps({"action": "actioned"}),
            content_type="application/json",
        )
        assert response.status_code == 204
        pending_item.refresh_from_db()
        assert pending_item.state == Item.State.ACTIONED
        assert pending_item.actioned_at is not None

    def test_dismissed_sets_state(self, client, user, pending_item):
        client.force_login(user)
        response = client.post(
            f"/items/{pending_item.id}/action/",
            data=json.dumps({"action": "dismissed"}),
            content_type="application/json",
        )
        assert response.status_code == 204
        pending_item.refresh_from_db()
        assert pending_item.state == Item.State.DISMISSED

    def test_invalid_action_returns_400(self, client, user, pending_item):
        client.force_login(user)
        response = client.post(
            f"/items/{pending_item.id}/action/",
            data=json.dumps({"action": "invalid"}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_nonexistent_item_returns_404(self, client, user, db):
        client.force_login(user)
        response = client.post(
            "/items/99999/action/",
            data=json.dumps({"action": "seen"}),
            content_type="application/json",
        )
        assert response.status_code == 404

    def test_cannot_action_other_users_item(self, client, user, db):
        from django.contrib.auth.models import User
        other = User.objects.create_user(username="other4", password="x")
        item = Item.objects.create(user=other, source="s", external_id="ia1", title="T")
        client.force_login(user)
        response = client.post(
            f"/items/{item.id}/action/",
            data=json.dumps({"action": "seen"}),
            content_type="application/json",
        )
        assert response.status_code == 404

    def test_form_post_works(self, client, user, pending_item):
        client.force_login(user)
        response = client.post(
            f"/items/{pending_item.id}/action/",
            data={"action": "seen"},
        )
        assert response.status_code == 204
        pending_item.refresh_from_db()
        assert pending_item.state == Item.State.SEEN
