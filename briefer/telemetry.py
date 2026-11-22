"""OpenTelemetry: send traces and logs over OTLP/HTTP.

Off unless OTEL_EXPORTER_OTLP_ENDPOINT is set. On the Pi, the systemd units
point it at the local OpenTelemetry Collector (http://127.0.0.1:4318), which
forwards to OpenObserve. The exporters read the standard OTEL_* variables.

Call configure() once per process, before Django handles requests: wsgi.py
does it in each gunicorn worker (workers load the app after forking, so the
exporters' background threads belong to the worker) and manage.py does it for
commands such as fetch_resources.
"""
import logging
import os

_configured = False


class _RequestAsText(logging.Filter):
    """Replace Django's request object in log records with "METHOD path".

    Django logs with extra={"request": <WSGIRequest>}. OTLP attributes must be
    primitives, and the OTel handler logs a warning for each other value. This
    filter sits on the OTel handler only, which runs after the django logger's
    own handlers (they still see the real request).
    """

    def filter(self, record):
        request = getattr(record, "request", None)
        if request is not None and not isinstance(request, (str, bytes, int, float, bool)):
            method = getattr(request, "method", None)
            path = getattr(request, "get_full_path", None)
            record.request = f"{method} {path()}" if method and path else str(request)
        return True


def configure(service_name="briefer"):
    """Set up tracing and logging export. Returns True if it did."""
    global _configured
    if _configured or not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return False

    from opentelemetry import _logs, trace
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.django import DjangoInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create(
        {"service.name": os.environ.get("OTEL_SERVICE_NAME", service_name)}
    )

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    # Python logging -> OTLP logs. Django's default config logs unhandled view
    # errors (django.request) to mail_admins only when DEBUG is off; they also
    # propagate to the root logger, so this handler catches them.
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    _logs.set_logger_provider(logger_provider)
    root = logging.getLogger()
    handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
    handler.addFilter(_RequestAsText())
    root.addHandler(handler)
    if root.level == logging.NOTSET or root.level > logging.INFO:
        root.setLevel(logging.INFO)

    # A span per request (errors recorded on it) and per outgoing HTTP call
    # (the resource fetchers use requests)
    DjangoInstrumentor().instrument()
    RequestsInstrumentor().instrument()

    _configured = True
    return True
