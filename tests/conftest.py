import os

import django
from django.conf import settings
from dotenv import load_dotenv

load_dotenv()

# pytest-playwright's sync API runs an asyncio event loop on the test thread,
# so Django refuses DB access during live-server test teardown
# (SynchronousOnlyOperation). Safe here: tests are single-threaded and the
# loop never runs Django code. Test-only; never set this in the app.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


def pytest_configure():
    if not settings.configured:
        settings.configure(
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": ":memory:",
                }
            },
            INSTALLED_APPS=[
                "django.contrib.contenttypes",
                "core",
            ],
            ROOT_URLCONF="briefer.urls",
            TEMPLATES=[
                {
                    "BACKEND": "django.template.backends.django.DjangoTemplates",
                    "DIRS": [],
                    "APP_DIRS": True,
                    "OPTIONS": {
                        "context_processors": [
                            "django.template.context_processors.request",
                        ],
                    },
                },
            ],
            DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
            USE_TZ=True,
        )
        django.setup()
