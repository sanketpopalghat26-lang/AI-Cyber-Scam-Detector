"""
Enterprise Observability Module
=================================
Prometheus metrics, OpenTelemetry tracing, structured logging,
and health/readiness/liveness probes.
"""

import contextlib
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request, Response
from loguru import logger
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from prometheus_client.multiprocess import MultiProcessCollector
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# =============================================================================
# Prometheus Metrics
# =============================================================================

# HTTP request metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

http_requests_in_progress = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently in progress",
    ["method"],
)

# Business metrics
predictions_total = Counter(
    "predictions_total",
    "Total number of predictions made",
    ["label", "source"],
)

prediction_duration_seconds = Histogram(
    "prediction_duration_seconds",
    "Time taken for model prediction",
    ["model_type"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

# Auth metrics
auth_attempts_total = Counter(
    "auth_attempts_total",
    "Total authentication attempts",
    ["method", "result"],
)

# Database metrics
db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["query_type"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

db_connections_active = Gauge(
    "db_connections_active",
    "Number of active database connections",
)

# Cache metrics
cache_hits_total = Counter(
    "cache_hits_total",
    "Total number of cache hits",
    ["cache_name"],
)

cache_misses_total = Counter(
    "cache_misses_total",
    "Total number of cache misses",
    ["cache_name"],
)

# System metrics
system_memory_bytes = Gauge(
    "system_memory_bytes",
    "System memory usage in bytes",
    ["type"],
)

system_cpu_percent = Gauge(
    "system_cpu_percent",
    "System CPU usage percentage",
)

# Model metrics
model_inference_time = Histogram(
    "model_inference_time_seconds",
    "Model inference time in seconds",
    ["model_name"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

model_prediction_confidence = Gauge(
    "model_prediction_confidence",
    "Confidence score of latest prediction",
    ["label"],
)


# =============================================================================
# Metrics Middleware
# =============================================================================

class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware that collects Prometheus metrics for all HTTP requests.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        # Initialize multiprocess mode if configured
        if os.getenv("PROMETHEUS_MULTIPROC_DIR"):
            with contextlib.suppress(Exception):
                MultiProcessCollector(os.getenv("PROMETHEUS_MULTIPROC_DIR"))

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Track in-progress requests
        http_requests_in_progress.labels(method=request.method).inc()

        start_time = time.time()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            raise
        finally:
            # Record metrics
            duration = time.time() - start_time
            endpoint = request.url.path

            http_requests_total.labels(
                method=request.method,
                endpoint=endpoint,
                status_code=status_code,
            ).inc()

            http_request_duration_seconds.labels(
                method=request.method,
                endpoint=endpoint,
            ).observe(duration)

            http_requests_in_progress.labels(method=request.method).dec()

        return response


# =============================================================================
# Metrics endpoint
# =============================================================================

def setup_metrics_endpoint(app: FastAPI) -> None:
    """Add /metrics endpoint to the application."""
    from fastapi.responses import Response as FastAPIResponse

    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        """Prometheus metrics endpoint."""
        data = generate_latest()
        return FastAPIResponse(
            content=data,
            media_type=CONTENT_TYPE_LATEST,
        )


# =============================================================================
# Structured Logging
# =============================================================================

class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """
    Adds structured logging for all requests.
    Logs in JSON format for log aggregation.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        correlation_id = request.headers.get(
            "X-Correlation-ID",
            request.headers.get("X-Request-ID", ""),
        )

        # Log request
        logger.info(
            "Request started",
            method=request.method,
            path=request.url.path,
            query_params=str(request.url.query),
            client_ip=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("user-agent", ""),
            correlation_id=correlation_id,
        )

        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000

            # Log response
            logger.info(
                "Request completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
                correlation_id=correlation_id,
            )

            return response

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "Request failed",
                method=request.method,
                path=request.url.path,
                error=str(e),
                duration_ms=round(duration_ms, 2),
                correlation_id=correlation_id,
            )
            raise


# =============================================================================
# Health Probes
# =============================================================================

class HealthStatus:
    """Tracks health status of dependent services."""

    def __init__(self):
        self.checks: dict[str, dict[str, Any]] = {}
        self.startup_time = datetime.now(UTC)

    def register_check(self, name: str, check_func: Callable) -> None:
        """Register a health check function."""
        self.checks[name] = {
            "func": check_func,
            "last_check": None,
            "last_status": None,
            "last_error": None,
        }

    def run_check(self, name: str) -> dict[str, Any]:
        """Run a specific health check."""
        check = self.checks.get(name)
        if not check:
            return {"status": "unknown", "error": f"No check registered for {name}"}

        try:
            result = check["func"]()
            check["last_status"] = result
            check["last_error"] = None
            return result
        except Exception as e:
            check["last_status"] = {"status": "unhealthy"}
            check["last_error"] = str(e)
            return {"status": "unhealthy", "error": str(e)}

    def get_all_checks(self) -> dict[str, dict[str, Any]]:
        """Run all health checks and return results."""
        results = {}
        for name in self.checks:
            results[name] = self.run_check(name)
        return results

    def is_healthy(self) -> bool:
        """Check if all services are healthy."""
        checks = self.get_all_checks()
        return all(
            check.get("status") == "healthy"
            for check in checks.values()
        )


_health_status = HealthStatus()


def get_health_status() -> dict:
    """Get current health status (shared across endpoints)."""
    model_status = "unknown"
    try:
        if "backend.app.main" in __import__("sys").modules:
            from backend.app.main import MODEL
            model_status = "loaded" if hasattr(MODEL, "predict_proba") else "fallback"
    except Exception:
        pass
    return {
        "status": "ok",
        "model_status": model_status,
        "timestamp": datetime.now(UTC).isoformat(),
        "uptime_seconds": (datetime.now(UTC) - _health_status.startup_time).total_seconds(),
    }


def setup_health_endpoints(app: FastAPI) -> None:
    """Add health check endpoints.

    Always registers /health/ready, /health/live, /health/db
    regardless of ENABLE_METRICS flag.
    """

    # Note: /health endpoint is defined in main.py to avoid duplication.
    # This function only adds /health/ready, /health/live, /health/db.

    @app.get("/health/ready", tags=["observability"])
    async def readiness():
        """
        Readiness probe — indicates if the service is ready to accept traffic.
        Checks all dependencies (database, cache, model).
        """
        checks = _health_status.get_all_checks()
        is_ready = all(
            check.get("status") == "healthy"
            for check in checks.values()
        )

        status_code = 200 if is_ready else 503
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "ready" if is_ready else "not_ready",
                "checks": checks,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    @app.get("/health/live", tags=["observability"])
    async def liveness():
        """
        Liveness probe — indicates if the service is alive.
        Does NOT check dependencies (to avoid cascading failures).
        """
        return {
            "status": "alive",
            "timestamp": datetime.now(UTC).isoformat(),
            "uptime_seconds": (datetime.now(UTC) - _health_status.startup_time).total_seconds(),
        }

    @app.get("/health/db", tags=["observability"])
    async def database_health():
        """Database-specific health check."""
        check = _health_status.run_check("database")
        return check


# =============================================================================
# OpenTelemetry Tracing
# =============================================================================

def setup_opentelemetry(app: FastAPI, service_name: str = "ai-cyber-scam-detector") -> None:
    """
    Configure OpenTelemetry for distributed tracing.
    Falls back gracefully if OpenTelemetry packages are not installed.
    """
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )

        # Create resource
        resource = Resource.create({
            "service.name": service_name,
            "service.version": os.getenv("APP_VERSION", "1.0.0"),
            "deployment.environment": os.getenv("APP_ENV", "development"),
        })

        # Create tracer provider
        tracer_provider = TracerProvider(resource=resource)

        # Add span processors
        otlp_endpoint = os.getenv("OTLP_ENDPOINT")
        if otlp_endpoint:
            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        else:
            # Console exporter as fallback
            tracer_provider.add_span_processor(
                BatchSpanProcessor(ConsoleSpanExporter())
            )

        # Set global tracer provider
        trace.set_tracer_provider(tracer_provider)

        # Instrument FastAPI
        FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)

        # Instrument requests library
        RequestsInstrumentor().instrument()

        logger.info("OpenTelemetry tracing configured successfully")

    except ImportError:
        logger.info(
            "OpenTelemetry packages not installed. "
            "Install with: pip install opentelemetry-api opentelemetry-sdk "
            "opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-requests"
        )
    except Exception as e:
        logger.warning(f"Failed to configure OpenTelemetry: {e}")


# =============================================================================
# Full observability setup
# =============================================================================

def setup_observability(app: FastAPI) -> None:
    """Configure all observability features."""
    # Prometheus metrics
    setup_metrics_endpoint(app)
    app.add_middleware(PrometheusMetricsMiddleware)

    # Structured logging
    app.add_middleware(StructuredLoggingMiddleware)

    # OpenTelemetry
    setup_opentelemetry(app)

    logger.info("Observability stack initialized")
