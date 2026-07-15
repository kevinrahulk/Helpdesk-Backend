import logging
import sys
import os
from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, ConsoleLogExporter
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource

# Monkey-patch opentelemetry-instrumentation-fastapi to fix AttributeError with _IncludedRouter in FastAPI >= 0.137.0
try:
    import opentelemetry.instrumentation.fastapi as otel_fastapi
    from starlette.routing import Match

    def patched_get_route_details(scope):
        app = scope["app"]
        route = None

        for starlette_route in app.routes:
            try:
                match, _ = starlette_route.matches(scope)
                if match == Match.FULL:
                    route = starlette_route.path
                    break
                if match == Match.PARTIAL:
                    route = starlette_route.path
            except AttributeError:
                # Bypass routes without a 'path' attribute (like _IncludedRouter)
                pass
        return route

    otel_fastapi._get_route_details = patched_get_route_details
except Exception as e:
    logging.getLogger("app.logging_otel").warning("Failed to monkey-patch FastAPI instrumentor: %s", e)

def setup_logging():
    # 1. Configure standard Python logging format to include OTel trace and span ID fields.
    # Using specific formats that are populated by LoggingInstrumentor.
    log_format = "%(asctime)s [%(levelname)s] %(name)s [trace_id=%(otelTraceID)s span_id=%(otelSpanID)s] - %(message)s"
    
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("app.log", encoding="utf-8"),
        ],
    )
    
    # 2. Configure OpenTelemetry resource
    resource = Resource.create(attributes={
        "service.name": "helpdesk-backend",
        "service.namespace": "helpdesk-assistant"
    })
    
    # 3. Configure TracerProvider
    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)
    
    # 4. Configure LoggerProvider
    logger_provider = LoggerProvider(resource=resource)
    set_logger_provider(logger_provider)
    
    # 5. Add processors and exporters to the OpenTelemetry LoggerProvider
    # Write to OTel console exporter for validation/inspection
    console_exporter = ConsoleLogExporter()
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(console_exporter))
    
    # Optional OTLP log and trace exporters if OTEL_EXPORTER_OTLP_ENDPOINT is set
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        try:
            otlp_exporter = OTLPLogExporter(endpoint=otlp_endpoint, insecure=True)
            logger_provider.add_log_record_processor(BatchLogRecordProcessor(otlp_exporter))
            
            otlp_trace_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
            tracer_provider.add_span_processor(BatchSpanProcessor(otlp_trace_exporter))
        except Exception as e:
            # Print to stdout/stderr and proceed without crashing
            print(f"⚠️ Failed to initialize OTLP exporters: {e}", file=sys.stderr)
            
    # 4. Attach OpenTelemetry LoggingHandler to the Python root logger
    otel_handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
    logging.getLogger().addHandler(otel_handler)
    
    # 5. Instrument standard Python logging to inject OTel context tags
    LoggingInstrumentor().instrument(set_logging_format=False)

    # 6. Suppress internal OpenTelemetry logging warnings to keep application logs clean
    logging.getLogger("opentelemetry").setLevel(logging.ERROR)
