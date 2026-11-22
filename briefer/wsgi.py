import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "briefer.settings")

from briefer import telemetry  # noqa: E402

telemetry.configure()

application = get_wsgi_application()
