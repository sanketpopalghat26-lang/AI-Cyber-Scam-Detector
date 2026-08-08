"""Comprehensive unit tests for the database module."""
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session

from backend.app.core.db import (
    DatabaseSessionManager,
    create_db_engine,
    get_db_session,
    get_session,
    init_db,
)


class TestCreateDbEngine:
    def test_create_sqlite_engine(self):
        with patch("backend.app.core.db.DATABASE_URL", "sqlite:///test.db"):
            engine = create_db_engine()
            assert engine is not None
            assert "sqlite" in str(engine.url)

    def test_create_postgresql_engine(self):
        with patch(
            "backend.app.core.db.DATABASE_URL",
            "postgresql://user:pass@localhost/db",
        ), patch("backend.app.core.db.create_engine") as mock_create:
            mock_engine = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = MagicMock()
            mock_create.return_value = mock_engine
            engine = create_db_engine()
            assert engine is not None
            # Verify pool settings were passed
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["pool_size"] is not None
            assert call_kwargs["max_overflow"] is not None

    def test_connection_retry_success(self):
        with patch("backend.app.core.db.DATABASE_URL", "sqlite:///test.db"):
            with patch("backend.app.core.db.create_engine") as mock_create:
                mock_engine = MagicMock()
                mock_engine.connect.return_value.__enter__.return_value = MagicMock()
                mock_create.return_value = mock_engine
                engine = create_db_engine()
                assert engine is not None

    def test_connection_retry_failure(self):
        with patch("backend.app.core.db.DATABASE_URL", "sqlite:///test.db"):
            with patch("backend.app.core.db.create_engine") as mock_create:
                mock_create.side_effect = Exception("Connection failed")
                with pytest.raises(RuntimeError, match="Could not connect to database"):
                    create_db_engine()

    def test_connection_retry_then_success(self):
        with patch("backend.app.core.db.DATABASE_URL", "sqlite:///test.db"):
            with patch("backend.app.core.db.create_engine") as mock_create:
                mock_engine = MagicMock()
                mock_engine.connect.return_value.__enter__.return_value = MagicMock()
                mock_create.side_effect = [Exception("Attempt 1 failed"), mock_engine]
                engine = create_db_engine()
                assert engine is not None


class TestInitDb:
    def test_init_db_success(self):
        with patch("backend.app.core.db.engine") as mock_engine:
            with patch("backend.app.core.db.SQLModel.metadata.create_all") as mock_create:
                init_db()
                mock_create.assert_called_once_with(mock_engine)

    def test_init_db_failure(self):
        with patch("backend.app.core.db.engine"), patch(
            "backend.app.core.db.SQLModel.metadata.create_all",
            side_effect=Exception("Create failed"),
        ), pytest.raises(Exception, match="Create failed"):
            init_db()


class TestGetSession:
    def _patched_session(self):
        """Return a mock Session that behaves as a context manager yielding itself."""
        session = MagicMock(spec=Session)
        session.__enter__.return_value = session
        return session

    def test_get_session_yields_session(self):
        with patch("backend.app.core.db.engine") as mock_engine:
            mock_session = self._patched_session()
            with patch("backend.app.core.db.Session", return_value=mock_session):
                gen = get_session()
                session = next(gen)
                assert session is mock_session

    def test_get_session_closes(self):
        with patch("backend.app.core.db.engine") as mock_engine:
            mock_session = self._patched_session()
            with patch("backend.app.core.db.Session", return_value=mock_session):
                gen = get_session()
                next(gen)
                # Exhaust the generator so the `with` block exits and calls close().
                with pytest.raises(StopIteration):
                    next(gen)
                mock_session.close.assert_called_once()

    def test_get_session_rollback_on_error(self):
        with patch("backend.app.core.db.engine") as mock_engine:
            mock_session = self._patched_session()
            with patch("backend.app.core.db.Session", return_value=mock_session):
                gen = get_session()
                next(gen)
                # Throw an exception INTO the generator at the yield point so
                # the generator's except block runs session.rollback().
                with pytest.raises(ValueError, match="test error"):
                    gen.throw(ValueError("test error"))
                mock_session.rollback.assert_called_once()


class TestDatabaseSessionManager:
    def test_context_manager_enter(self):
        with patch("backend.app.core.db.engine") as mock_engine:
            mock_session = MagicMock(spec=Session)
            with patch("backend.app.core.db.Session", return_value=mock_session):
                manager = DatabaseSessionManager()
                with manager as session:
                    assert session is not None

    def test_context_manager_commit_on_success(self):
        with patch("backend.app.core.db.engine") as mock_engine:
            mock_session = MagicMock(spec=Session)
            with patch("backend.app.core.db.Session", return_value=mock_session):
                manager = DatabaseSessionManager()
                with manager:
                    pass
                mock_session.commit.assert_called_once()
                mock_session.close.assert_called_once()

    def test_context_manager_rollback_on_error(self):
        with patch("backend.app.core.db.engine") as mock_engine:
            mock_session = MagicMock(spec=Session)
            with patch("backend.app.core.db.Session", return_value=mock_session):
                manager = DatabaseSessionManager()
                try:
                    with manager:
                        raise ValueError("test")
                except ValueError:
                    pass
                mock_session.rollback.assert_called_once()
                mock_session.close.assert_called_once()

    def test_session_property(self):
        with patch("backend.app.core.db.engine") as mock_engine:
            mock_session = MagicMock(spec=Session)
            with patch("backend.app.core.db.Session", return_value=mock_session):
                manager = DatabaseSessionManager()
                manager.__enter__()
                assert manager.session is not None


class TestGetDbSession:
    def test_get_db_session(self):
        manager = get_db_session()
        assert isinstance(manager, DatabaseSessionManager)
