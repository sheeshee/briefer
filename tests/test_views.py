import json

import pytest
from django.test import Client

from core.models import Item


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
class TestFetchView:
    def test_post_redirects_to_stack(self, client):
        response = client.post("/fetch/")
        assert response.status_code == 302
        assert response["Location"] == "/"

    def test_get_not_allowed(self, client):
        response = client.get("/fetch/")
        assert response.status_code == 405


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
