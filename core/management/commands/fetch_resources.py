import logging
import sys

from django.core.management.base import BaseCommand

from resources.bbc import BBCFeedResource
from resources.fake import FakeResource
from resources.hackernews import HackerNewsResource
from resources.news import NewsAPIResource
from resources.weather import WeatherResource

logger = logging.getLogger(__name__)

BASE_RESOURCES = [
    HackerNewsResource(),
    NewsAPIResource(),
    BBCFeedResource("bbc", "https://feeds.bbci.co.uk/news/rss.xml"),
    BBCFeedResource("bbc-wales", "https://feeds.bbci.co.uk/news/wales/rss.xml"),
    BBCFeedResource("bbc-tech", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    BBCFeedResource("bbc-world", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    # Last, so it is the newest item and sits on top of the stack.
    WeatherResource(),
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
