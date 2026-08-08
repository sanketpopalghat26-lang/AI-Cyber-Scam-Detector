"""
Backward-compatible re-export of database module.
All enterprise functionality has moved to backend/app/core/db.py
"""
from .core.db import DatabaseSessionManager, engine, get_session, init_db

__all__ = ["engine", "init_db", "get_session", "DatabaseSessionManager"]

