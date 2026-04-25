import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError

from core.models import Item


@pytest.mark.django_db
class TestItemModel:
    def test_create_item_with_required_fields(self, user):
        item = Item.objects.create(
            user=user,
            source="test",
            external_id="test-1",
            title="Test Item",
        )
        assert item.pk is not None
        assert item.title == "Test Item"
        assert item.source == "test"

    def test_external_id_unique_per_user(self, user):
        Item.objects.create(user=user, source="test", external_id="dup-1", title="First")
        with pytest.raises(IntegrityError):
            Item.objects.create(user=user, source="test", external_id="dup-1", title="Second")

    def test_external_id_can_be_shared_across_users(self, user, db):
        other = User.objects.create_user(username="other", password="x")
        Item.objects.create(user=user, source="test", external_id="shared-1", title="A")
        Item.objects.create(user=other, source="test", external_id="shared-1", title="B")
        assert Item.objects.filter(external_id="shared-1").count() == 2

    def test_default_state_is_pending(self, user):
        item = Item.objects.create(user=user, source="test", external_id="test-2", title="Test")
        assert item.state == Item.State.PENDING

    def test_state_choices(self):
        assert Item.State.PENDING == "pending"
        assert Item.State.SEEN == "seen"
        assert Item.State.ACTIONED == "actioned"
        assert Item.State.DISMISSED == "dismissed"
