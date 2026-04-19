import pytest
from django.core.management import call_command

from core.models import Item


@pytest.mark.django_db
class TestDeleteItemsCommand:
    def test_deletes_all_items(self):
        Item.objects.create(source="s", external_id="d1", title="A")
        Item.objects.create(source="s", external_id="d2", title="B")
        call_command("delete_items")
        assert Item.objects.count() == 0

    def test_no_items_is_safe(self):
        call_command("delete_items")
        assert Item.objects.count() == 0
