import logging
import sys

from django.core.management.base import BaseCommand

from resources.fake import FakeResource
from resources.hackernews import HackerNewsResource
from resources.news import NewsAPIResource

logger = logging.getLogger(__name__)

BASE_RESOURCES = [
    HackerNewsResource(),
    NewsAPIResource(),
]


class Command(BaseCommand):
    help = "Fetch items from all registered resources"

    def add_arguments(self, parser):
        parser.add_argument("--include-fake", action="store_true", default=False)

    def handle(self, *args, **options):
        resources = list(BASE_RESOURCES)
        if options["include_fake"]:
            resources.append(FakeResource())

        has_error = False

        for resource in resources:
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
