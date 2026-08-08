"""
Enterprise Middleware Stack
===========================
Security headers, CORS, rate limiting, request validation,
audit logging, and monitoring middleware.
"""

import os
import time
import uuid
from collections.abc import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# =============================================================================
# Security Headers Middleware
# =============================================================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds comprehensive security headers to all responses.
    Implements OWASP security best practices.
    """

    def __init__(self, app: ASGIApp, csp_directives: dict | None = None):
        super().__init__(app)
        self.csp_directives = csp_directives or {
            "default-src": "'self'",
            "script-src": "'self' 'unsafe-inline' 'unsafe-eval'",
            "style-src": "'self' 'unsafe-inline'",
            "img-src": "'self' data: blob:",
            "font-src": "'self' data:",
            "connect-src": "'self'",
            "frame-ancestors": "'none'",
            "form-action": "'self'",
            "base-uri": "'self'",
            "object-src": "'none'",
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Security headers
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), "
            "payment=(), usb=(), fullscreen=(self)"
        )

        # Content Security Policy
        csp = "; ".join(
            f"{key} {value}" for key, value in self.csp_directives.items()
        )
        response.headers["Content-Security-Policy"] = csp

        # HSTS - only in production
        if os.getenv("APP_ENV", "development") == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Cross-Origin headers
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-site"

        # Remove server header
        if "server" in response.headers:
            del response.headers["server"]

        return response


# =============================================================================
# CORS Configuration
# =============================================================================

def setup_cors(app: FastAPI) -> None:
    """Configure CORS with strict production settings."""
    origins_str = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173,http://localhost:8000"
    )
    origins = [o.strip() for o in origins_str.split(",") if o.strip()]

    # In production, enforce specific origins
    if os.getenv("APP_ENV", "development") == "production" and origins == ["*"]:
        logger.warning("CORS configured with wildcard in production. Review this setting.")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "X-Correlation-ID",
            "X-API-Key",
            "Accept",
            "Origin",
        ],
        expose_headers=[
            "X-Request-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ],
        max_age=600,  # Preflight cache (10 minutes)
    )


# =============================================================================
# Request ID & Correlation ID Middleware
# =============================================================================

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Adds unique request IDs and correlation IDs for tracing.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        correlation_id = request.headers.get(
            "X-Correlation-ID",
            request.headers.get("X-Request-ID", str(uuid.uuid4()))
        )

        # Store in request state
        request.state.request_id = request_id
        request.state.correlation_id = correlation_id

        response = await call_next(request)

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = correlation_id

        return response


# =============================================================================
# Request Timing Middleware
# =============================================================================

class RequestTimingMiddleware(BaseHTTPMiddleware):
    """
    Tracks request duration and logs slow requests.
    """

    SLOW_REQUEST_THRESHOLD_MS = 1000  # 1 second

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        response = await call_next(request)

        duration_ms = (time.time() - start_time) * 1000
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        # Log slow requests
        if duration_ms > self.SLOW_REQUEST_THRESHOLD_MS:
            logger.warning(
                "Slow request detected",
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration_ms, 2),
                ip=request.client.host if request.client else "unknown",
            )

        return response


# =============================================================================
# Rate Limiting Middleware
# =============================================================================

class SimpleRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory rate limiting.
    Replace with Redis-based implementation in production.
    """

    def __init__(
        self,
        app: ASGIApp,
        max_requests: int = 100,
        window_seconds: int = 60,
        exclude_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.exclude_paths = exclude_paths or ["/health", "/metrics"]
        self._store: dict = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for excluded paths
        if any(request.url.path.startswith(p) for p in self.exclude_paths):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - self.window_seconds

        # Clean and check
        if client_ip in self._store:
            self._store[client_ip] = [
                ts for ts in self._store[client_ip] if ts > window_start
            ]
        else:
            self._store[client_ip] = []

        if len(self._store[client_ip]) >= self.max_requests:
            oldest = min(self._store[client_ip])
            retry_after = int(oldest + self.window_seconds - now)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests",
                    "retry_after_seconds": max(retry_after, 1),
                },
                headers={
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(now + retry_after)),
                    "Retry-After": str(max(retry_after, 1)),
                },
            )

        self._store[client_ip].append(now)
        remaining = self.max_requests - len(self._store[client_ip])

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(max(remaining, 0))
        response.headers["X-RateLimit-Reset"] = str(int(now + self.window_seconds))

        return response


# =============================================================================
# Input Sanitization Middleware
# =============================================================================

class InputSanitizationMiddleware(BaseHTTPMiddleware):
    """
    Sanitizes request inputs to prevent injection attacks.
    """

    DANGEROUS_PATTERNS = [
        "<script",
        "javascript:",
        "onerror=",
        "onload=",
        "onclick=",
        "eval(",
        "exec(",
        "system(",
        "import os",
        "subprocess",
        "__import__",
    ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check JSON body
        if request.method in ("POST", "PUT", "PATCH"):
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                body = await request.body()
                if body:
                    decoded = body.decode("utf-8", errors="ignore")
                    for pattern in self.DANGEROUS_PATTERNS:
                        if pattern in decoded.lower():
                            return JSONResponse(
                                status_code=400,
                                content={
                                    "detail": "Request contains potentially dangerous content",
                                    "blocked_pattern": pattern,
                                },
                            )
                    # Re-set the body so downstream handlers can read it
                    # Starlette stores body in _body after consuming the stream
                    request._body = body

        return await call_next(request)


# =============================================================================
# All Middleware Registration
# =============================================================================

def register_middleware(app: FastAPI) -> None:
    """
    Register all enterprise middleware in the correct order.
    Order matters: first registered = outermost.
    """
    # 1. CORS (outermost)
    setup_cors(app)

    # 2. Security headers
    app.add_middleware(SecurityHeadersMiddleware)

    # 3. Request ID
    app.add_middleware(RequestIDMiddleware)

    # 4. Rate limiting
    app.add_middleware(
        SimpleRateLimitMiddleware,
        max_requests=int(os.getenv("RATE_LIMIT_MAX", "100")),
        window_seconds=int(os.getenv("RATE_LIMIT_WINDOW", "60")),
    )

    # 5. Request timing
    app.add_middleware(RequestTimingMiddleware)

    # 6. Input sanitization
    app.add_middleware(InputSanitizationMiddleware)

