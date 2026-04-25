import logging
import sys

from django.contrib.auth import get_user_model
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
    help = "Fetch items from all registered resources for all users"

    def add_arguments(self, parser):
        parser.add_argument("--include-fake", action="store_true", default=False)

    def handle(self, *args, **options):
        User = get_user_model()
        users = list(User.objects.all())

        if not users:
            self.stdout.write(self.style.WARNING("No users found — skipping fetch"))
            return

        resources = list(BASE_RESOURCES)
        if options["include_fake"]:
            resources.append(FakeResource())

        has_error = False

        for user in users:
            for resource in resources:
                self.stdout.write(f"Fetching {resource.source_id} for {user.username}")
                try:
                    resource.fetch(user)
                    self.stdout.write(self.style.SUCCESS(f"Done: {resource.source_id}"))
                except Exception:
                    logger.exception("Error fetching resource: %s", resource.source_id)
                    self.stderr.write(self.style.ERROR(f"Error: {resource.source_id}"))
                    has_error = True

        if has_error:
            sys.exit(1)
