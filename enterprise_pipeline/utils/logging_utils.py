"""
Enterprise Logging Utility
===========================
Structured logging with loguru providing:
- Console and file logging
- Rotation and retention
- Structured JSON output
- Correlation IDs
"""

import sys
import uuid

from loguru import logger as _logger

from ..config.settings import settings_instance


class LoggerFactory:
    """Factory for creating configured loggers."""

    _initialized = False

    @classmethod
    def initialize(cls, settings=settings_instance) -> None:
        """Initialize the logger with settings configuration."""
        if cls._initialized:
            return

        # Remove default handler
        _logger.remove()

        log_level = settings.logging.log_level
        log_format = settings.logging.log_format

        # Console handler
        if settings.logging.log_to_console:
            _logger.add(
                sys.stderr,
                format=log_format,
                level=log_level,
                colorize=True,
                enqueue=True,
            )

        # File handler with rotation
        if settings.logging.log_to_file:
            log_file = settings.paths.logs_dir / "enterprise_pipeline.log"
            _logger.add(
                str(log_file),
                format=log_format,
                level=log_level,
                rotation=settings.logging.log_rotation,
                retention=settings.logging.log_retention,
                compression="zip",
                enqueue=True,
                backtrace=True,
                diagnose=True,
            )

            # Separate error log
            error_log = settings.paths.logs_dir / "error.log"
            _logger.add(
                str(error_log),
                format=log_format,
                level="ERROR",
                rotation=settings.logging.log_rotation,
                retention=settings.logging.log_retention,
                compression="zip",
                enqueue=True,
                backtrace=True,
                diagnose=True,
            )

        cls._initialized = True

    @classmethod
    def get_logger(cls, name: str | None = None):
        """Get a configured logger with optional name context."""
        if not cls._initialized:
            cls.initialize()

        if name:
            return _logger.bind(name=name)
        return _logger

    @classmethod
    def get_correlation_id(cls) -> str:
        """Generate a correlation ID for request tracing."""
        return str(uuid.uuid4())


def get_logger(name: str | None = None):
    """Convenience function to get a logger."""
    return LoggerFactory.get_logger(name)


def log_execution_time(func):
    """Decorator to log function execution time."""
    import functools
    import time

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        start = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            logger.info(f"{func.__name__} completed in {elapsed:.3f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"{func.__name__} failed after {elapsed:.3f}s: {str(e)}")
            raise

    return wrapper


# Initialize on import
LoggerFactory.initialize()
