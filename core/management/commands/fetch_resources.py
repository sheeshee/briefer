import logging
import sys

from django.core.management.base import BaseCommand

from resources.hackernews import HackerNewsResource

logger = logging.getLogger(__name__)

RESOURCES = [
    HackerNewsResource(),
]


class Command(BaseCommand):
    help = "Fetch items from all registered resources"

    def handle(self, *args, **options):
        has_error = False

        for resource in RESOURCES:
            self.stdout.write(f"Fetching: {resource.source_id}")
            try:
                resource.fetch()
                self.stdout.write(self.style.SUCCESS(f"Done: {resource.source_id}"))
            except Exception:
                logger.exception("Error fetching resource: %s", resource.source_id)
                self.stderr.write(self.style.ERROR(f"Error: {resource.source_id}"))
                has_error = True

        if has_error:
            sys.exit(1)
