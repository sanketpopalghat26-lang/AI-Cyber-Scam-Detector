# =============================================================================
# Stage 1: Builder — Install dependencies and compile assets
# =============================================================================
FROM python:3.11-slim-bookworm AS builder

# Pin system dependencies for reproducibility
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential=12.9 \
    libpq-dev=15.6-0+deb12u1 \
    curl=7.88.1-10+deb12u6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy only requirements first for maximal layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip==24.0 \
    && pip install --no-cache-dir \
        --requirement requirements.txt \
        --target /deps \
        --no-compile

# =============================================================================
# Stage 2: Runtime — Minimal production image
# =============================================================================
FROM python:3.11-slim-bookworm AS runtime

# Security: run as non-root user
RUN groupadd -r -g 1001 appuser \
    && useradd -r -u 1001 -g appuser appuser \
    && mkdir -p /app /app/model /app/logs /app/data \
    && chown -R appuser:appuser /app

# Install only runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev=15.6-0+deb12u1 \
    curl=7.88.1-10+deb12u6 \
    tini=0.19.0-1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy pre-built dependencies from builder stage
COPY --from=builder --chown=appuser:appuser /deps /usr/local/lib/python3.11/site-packages
COPY --from=builder --chown=appuser:appuser /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser core/ ./core/

# Make /app/model read-only for the runtime — models are mounted at deploy time
VOLUME ["/app/model", "/app/data", "/app/logs"]

# Security: read-only root filesystem (enforced at container runtime)
# Use tini as init for proper signal handling and zombie reaping
ENTRYPOINT ["/usr/bin/tini", "--"]

# Healthcheck with proper intervals
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl --fail http://localhost:8000/health || exit 1

# Production environment defaults
ENV \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=42 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    APP_ENV=production \
    LOG_LEVEL=INFO

# Switch to non-root user
USER appuser

EXPOSE 8000

# Use gunicorn with Uvicorn workers for production
CMD ["gunicorn", "app.main:app", \
    "--bind", "0.0.0.0:8000", \
    "--worker-class", "uvicorn.workers.UvicornWorker", \
    "--workers", "4", \
    "--timeout", "120", \
    "--keep-alive", "5", \
    "--max-requests", "10000", \
    "--max-requests-jitter", "1000", \
    "--graceful-timeout", "30", \
    "--access-logfile", "-", \
    "--error-logfile", "-", \
    "--log-level", "info"]

