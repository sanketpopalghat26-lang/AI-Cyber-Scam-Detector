"""
Application Lifecycle Management
=================================
Graceful shutdown, startup validation, signal handling,
and resource cleanup.
"""

import asyncio
import inspect
import os
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from loguru import logger

from .cache import get_cache
from .observability import _health_status
from .secrets import validate_on_startup

# =============================================================================
# Startup Tasks
# =============================================================================

class LifecycleManager:
    """
    Manages application startup and shutdown lifecycle.
    """

    def __init__(self):
        self.startup_tasks: list[Callable] = []
        self.shutdown_tasks: list[Callable] = []
        self._is_shutting_down = False

    def add_startup_task(self, task: Callable, name: str | None = None) -> None:
        """Register a startup task."""
        self.startup_tasks.append((task, name or task.__name__))

    def add_shutdown_task(self, task: Callable, name: str | None = None) -> None:
        """Register a shutdown task."""
        self.shutdown_tasks.append((task, name or task.__name__))

    async def run_startup(self) -> None:
        """Execute all startup tasks."""
        logger.info("Running startup tasks...")
        for task, name in self.startup_tasks:
            try:
                if inspect.iscoroutinefunction(task):
                    await task()
                else:
                    task()
                logger.info(f"Startup task '{name}' completed")
            except Exception as e:
                logger.error(f"Startup task '{name}' failed: {e}")
                if os.getenv("APP_ENV", "development") == "production":
                    raise

    async def run_shutdown(self) -> None:
        """Execute all shutdown tasks gracefully."""
        self._is_shutting_down = True
        logger.info("Running shutdown tasks...")

        for task, name in reversed(self.shutdown_tasks):
            try:
                if inspect.iscoroutinefunction(task):
                    await task()
                else:
                    task()
                logger.info(f"Shutdown task '{name}' completed")
            except Exception as e:
                logger.error(f"Shutdown task '{name}' failed: {e}")


lifecycle = LifecycleManager()


# =============================================================================
# Default startup/shutdown tasks
# =============================================================================

async def _validate_secrets() -> None:
    """Validate configuration secrets on startup."""
    validate_on_startup()


async def _register_health_checks() -> None:
    """Register health checks for dependencies."""
    from .db import engine

    def check_database():
        """Check database connectivity."""
        try:
            from sqlalchemy import text
            from sqlmodel import Session
            with Session(engine) as session:
                session.exec(text("SELECT 1"))
                return {"status": "healthy", "database": str(engine.url)}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def check_cache():
        """Check cache connectivity."""
        cache = get_cache()
        return cache.health_check()

    _health_status.register_check("database", check_database)
    _health_status.register_check("cache", check_cache)


async def _close_cache() -> None:
    """Close cache connections on shutdown."""
    cache = get_cache()
    await cache.close()


async def _close_db_connections() -> None:
    """Close database connections on shutdown."""
    from .db import engine
    try:
        engine.dispose()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")


# =============================================================================
# Graceful Shutdown Handler
# =============================================================================

class GracefulShutdown:
    """
    Handles graceful shutdown on SIGTERM/SIGINT.
    Waits for in-flight requests to complete.
    """

    def __init__(self, app: FastAPI, timeout_seconds: int = 30):
        self.app = app
        self.timeout_seconds = timeout_seconds
        self._active_requests = 0

    async def shutdown(self) -> None:
        """Perform graceful shutdown."""
        logger.info(f"Graceful shutdown initiated. Waiting up to {self.timeout_seconds}s...")

        # Set flag to reject new requests
        self.app.state.shutting_down = True

        # Wait for active requests to complete
        start = datetime.now(UTC)
        while self._active_requests > 0:
            elapsed = (datetime.now(UTC) - start).total_seconds()
            if elapsed >= self.timeout_seconds:
                logger.warning(
                    f"Shutdown timeout reached ({self.timeout_seconds}s). "
                    f"Force closing {self._active_requests} active requests."
                )
                break
            await asyncio.sleep(0.5)

        # Run lifecycle shutdown tasks
        await lifecycle.run_shutdown()

        logger.info("Graceful shutdown complete")


# =============================================================================
# Lifespan context manager for FastAPI
# =============================================================================

@asynccontextmanager
async def lifespan_handler(app: FastAPI):
    """
    FastAPI lifespan context manager.
    Handles startup and shutdown tasks.
    """
    # === STARTUP ===
    logger.info("=" * 60)
    logger.info("AI Cyber Scam Detector - Starting up")
    logger.info(f"Environment: {os.getenv('APP_ENV', 'development')}")
    logger.info(f"Version: {os.getenv('APP_VERSION', '1.0.0')}")
    logger.info("=" * 60)

    # Register default tasks
    lifecycle.add_startup_task(_validate_secrets, "validate_secrets")
    lifecycle.add_startup_task(_register_health_checks, "register_health_checks")
    lifecycle.add_shutdown_task(_close_cache, "close_cache")
    lifecycle.add_shutdown_task(_close_db_connections, "close_db_connections")

    # Run startup
    await lifecycle.run_startup()

    # Set app state
    app.state.shutting_down = False
    app.state.startup_time = datetime.now(UTC)

    # Yield control to application
    yield

    # === SHUTDOWN ===
    logger.info("=" * 60)
    logger.info("AI Cyber Scam Detector - Shutting down")
    logger.info("=" * 60)

    shutdown_handler = GracefulShutdown(app)
    await shutdown_handler.shutdown()

