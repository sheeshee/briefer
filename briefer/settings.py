import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-change-me-in-production",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in ("true", "1", "yes")

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "briefer.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "briefer.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Raindrop.io: swipe right saves the item as a bookmark. Either set
# RAINDROP_TEST_TOKEN, or the OAuth app's client id/secret/redirect URI and
# visit /raindrop/connect/ once.
RAINDROP_CLIENT_ID = os.environ.get("RAINDROP_CLIENT_ID", "")
RAINDROP_CLIENT_SECRET = os.environ.get("RAINDROP_CLIENT_SECRET", "")
RAINDROP_REDIRECT_URI = os.environ.get("RAINDROP_REDIRECT_URI", "")
RAINDROP_TEST_TOKEN = os.environ.get("RAINDROP_TEST_TOKEN", "")
RAINDROP_COLLECTION_ID = os.environ.get("RAINDROP_COLLECTION_ID", "")  # empty = Unsorted
# /raindrop/feed.xml serves this collection as RSS (for Kindly). -1 = Unsorted.
RAINDROP_FEED_COLLECTION_ID = os.environ.get("RAINDROP_FEED_COLLECTION_ID", "-1")

# Todoist: swipe right on the Claude usage card adds a task due today.
TODOIST_API_TOKEN = os.environ.get("TODOIST_API_TOKEN", "")

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True
