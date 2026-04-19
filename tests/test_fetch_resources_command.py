import pytest
from django.core.management import call_command

from core.models import Item


@pytest.mark.django_db
class TestFetchResourcesCommand:
    def test_without_include_fake_skips_fake_items(self):
        call_command("fetch_resources", include_fake=False)
        assert Item.objects.filter(source="fake").count() == 0

    def test_with_include_fake_creates_fake_items(self):
        call_command("fetch_resources", include_fake=True)
        assert Item.objects.filter(source="fake").count() > 0
