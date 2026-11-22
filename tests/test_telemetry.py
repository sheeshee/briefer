"""briefer.telemetry sends traces and logs over OTLP only when configured.

The enabled case runs in a subprocess: it installs global OpenTelemetry
providers and instruments Django, which must not leak into other tests.
"""
import os
import subprocess
import sys
import textwrap

from briefer import telemetry


def test_configure_is_a_no_op_without_an_endpoint(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert telemetry.configure() is False


def run_configured(code):
    env = dict(
        os.environ,
        DJANGO_SETTINGS_MODULE="briefer.settings",
        # Nothing listens here; exports fail quietly in the background
        OTEL_EXPORTER_OTLP_ENDPOINT="http://127.0.0.1:9",
        OTEL_SERVICE_NAME="briefer-test",
    )
    script = textwrap.dedent(
        """
        import logging
        from briefer import telemetry
        assert telemetry.configure() is True
        assert telemetry.configure() is False  # only once per process
        """
    ) + textwrap.dedent(code)
    result = subprocess.run(
        [sys.executable, "-c", script], env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_configure_sends_logs_to_otlp():
    run_configured(
        """
        from opentelemetry.sdk._logs import LoggingHandler
        root = logging.getLogger()
        assert any(isinstance(h, LoggingHandler) for h in root.handlers)
        assert root.level <= logging.INFO
        """
    )


def test_configure_traces_with_the_service_name():
    run_configured(
        """
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider)
        assert provider.resource.attributes["service.name"] == "briefer-test"
        """
    )


def test_configure_instruments_django_and_requests():
    run_configured(
        """
        from opentelemetry.instrumentation.django import DjangoInstrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        assert DjangoInstrumentor().is_instrumented_by_opentelemetry
        assert RequestsInstrumentor().is_instrumented_by_opentelemetry
        """
    )


def test_django_request_logs_export_without_attribute_warnings():
    # Django logs with extra={"request": <WSGIRequest>}; OTLP attributes must
    # be primitives, and the OTel handler warns about every other value.
    run_configured(
        """
        import django
        django.setup()
        from django.test import RequestFactory
        warnings = []
        class Collect(logging.Handler):
            def emit(self, record):
                warnings.append(record.getMessage())
        logging.getLogger("opentelemetry.attributes").addHandler(Collect())
        request = RequestFactory().get("/briefer/missing")
        logging.getLogger("django.request").warning(
            "Not Found: %s", request.path, extra={"status_code": 404, "request": request}
        )
        assert warnings == [], warnings
        """
    )
