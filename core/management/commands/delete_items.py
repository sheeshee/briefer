from django.core.management.base import BaseCommand

from core.models import Item


class Command(BaseCommand):
    help = "Delete all items from the database"

    def handle(self, *args, **options):
        count, _ = Item.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} item(s)."))
