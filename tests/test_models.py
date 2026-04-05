import pytest
from django.db import IntegrityError

from core.models import Item


@pytest.mark.django_db
class TestItemModel:
    def test_create_item_with_required_fields(self):
        item = Item.objects.create(
            source="test",
            external_id="test-1",
            title="Test Item",
        )
        assert item.pk is not None
        assert item.title == "Test Item"
        assert item.source == "test"

    def test_external_id_is_unique(self):
        Item.objects.create(source="test", external_id="dup-1", title="First")
        with pytest.raises(IntegrityError):
            Item.objects.create(source="test", external_id="dup-1", title="Second")

    def test_default_state_is_pending(self):
        item = Item.objects.create(
            source="test", external_id="test-2", title="Test"
        )
        assert item.state == Item.State.PENDING

    def test_state_choices(self):
        assert Item.State.PENDING == "pending"
        assert Item.State.SEEN == "seen"
        assert Item.State.ACTIONED == "actioned"
        assert Item.State.DISMISSED == "dismissed"
