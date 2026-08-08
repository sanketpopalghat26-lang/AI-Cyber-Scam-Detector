"""
Enterprise Database Module
===========================
Connection pooling, session management, and health checks.
Supports SQLite (dev) and PostgreSQL (production).
"""

import os
from collections.abc import Generator

from loguru import logger
from sqlmodel import Session, SQLModel, create_engine

from .config import DATABASE_URL, DB_ECHO, DB_MAX_OVERFLOW, DB_POOL_SIZE

# =============================================================================
# Database Engine Configuration
# =============================================================================

def create_db_engine():
    """
    Create a database engine with appropriate configuration.

    - SQLite: Simple, no pooling
    - PostgreSQL: Connection pooling with async support
    """
    import time as _time
    max_connect_attempts = 3

    for attempt in range(1, max_connect_attempts + 1):
        try:
            if DATABASE_URL.startswith("sqlite"):
                engine = create_engine(
                    DATABASE_URL,
                    echo=DB_ECHO,
                    connect_args={"check_same_thread": False},  # Required for SQLite
                )
                logger.info("Database: SQLite (development mode)")
            else:
                engine = create_engine(
                    DATABASE_URL,
                    echo=DB_ECHO,
                    pool_size=DB_POOL_SIZE,
                    max_overflow=DB_MAX_OVERFLOW,
                    pool_pre_ping=True,  # Verify connections before using
                    pool_recycle=3600,  # Recycle connections every hour
                    pool_use_lifo=True,  # Use LIFO for better connection reuse
                    connect_args={
                        "sslmode": os.getenv("DB_SSLMODE", "require"),
                        "keepalives": 1,
                        "keepalives_idle": 30,
                        "keepalives_interval": 10,
                        "keepalives_count": 5,
                        "connect_timeout": 10,
                    },
                )
                logger.info(
                    f"Database: PostgreSQL (production mode) — "
                    f"pool_size={DB_POOL_SIZE}, max_overflow={DB_MAX_OVERFLOW}"
                )

            # Test connection
            with engine.connect() as conn:
                from sqlalchemy import text
                conn.execute(text("SELECT 1"))

            return engine
        except Exception as e:
            logger.warning(f"Database connection attempt {attempt}/{max_connect_attempts} failed: {e}")
            if attempt < max_connect_attempts:
                _time.sleep(attempt * 2)

    logger.error(f"All {max_connect_attempts} database connection attempts failed")
    raise RuntimeError(f"Could not connect to database after {max_connect_attempts} attempts")


engine = create_db_engine()


# =============================================================================
# Session Management
# =============================================================================

def init_db() -> None:
    """Initialize database tables."""
    try:
        SQLModel.metadata.create_all(engine)
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def get_session() -> Generator[Session, None, None]:
    """
    Get a database session with automatic cleanup.

    Usage:
        session = get_session()
        # or via FastAPI dependency injection
    """
    with Session(engine) as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


# =============================================================================
# Database Session Manager (for async compatibility)
# =============================================================================

class DatabaseSessionManager:
    """Manages database sessions with context manager support."""

    def __init__(self):
        self._engine = engine

    def __enter__(self):
        self._session = Session(self._engine)
        return self._session

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._session.rollback()
        else:
            self._session.commit()
        self._session.close()

    @property
    def session(self):
        return self._session


def get_db_session() -> DatabaseSessionManager:
    """Get a database session manager."""
    return DatabaseSessionManager()

