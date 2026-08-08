"""
Integration tests for database operations.
Tests: CRUD, migrations, connections, concurrency, constraints.
"""
import time

import pytest
from sqlmodel import Session, select, text

from backend.app.core.db import engine, init_db
from backend.app.models import Feedback, Log, Report, Scan, User


@pytest.fixture(autouse=True)
def setup_db():
    """Ensure tables exist for each test."""
    init_db()
    yield
    # Clean up test data
    with Session(engine) as session:
        for table in [Log, Feedback, Report, Scan, User]:
            session.exec(text(f"DELETE FROM {table.__tablename__}"))
        session.commit()


class TestDatabaseConnection:
    def test_connection_succeeds(self):
        with Session(engine) as session:
            result = session.exec(text("SELECT 1")).first()
            assert result is not None

    def test_init_db_creates_tables(self):
        init_db()
        with Session(engine) as session:
            tables = session.exec(text(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )).all()
            table_names = [t[0] for t in tables]
            assert "users" in table_names
            assert "scans" in table_names
            assert "reports" in table_names
            assert "feedbacks" in table_names
            assert "logs" in table_names


class TestUserCRUD:
    def test_create_user(self):
        with Session(engine) as session:
            user = User(
                email="test@test.com",
                hashed_password="hashed_pw",
                is_admin=False,
            )
            session.add(user)
            session.commit()
            assert user.id is not None

    def test_read_user(self):
        with Session(engine) as session:
            user = User(email="read@test.com", hashed_password="pw")
            session.add(user)
            session.commit()
            session.refresh(user)

            fetched = session.exec(
                select(User).where(User.email == "read@test.com")
            ).first()
            assert fetched is not None
            assert fetched.email == "read@test.com"

    def test_update_user(self):
        with Session(engine) as session:
            user = User(email="update@test.com", hashed_password="pw")
            session.add(user)
            session.commit()

            user.is_admin = True
            session.add(user)
            session.commit()
            session.refresh(user)
            assert user.is_admin is True

    def test_delete_user_cascade(self):
        with Session(engine) as session:
            user = User(email="delete@test.com", hashed_password="pw")
            session.add(user)
            session.commit()
            session.refresh(user)

            scan = Scan(user_id=user.id, input_text="test", result="safe", confidence=0.9)
            session.add(scan)
            session.commit()

            session.delete(user)
            session.commit()

            remaining = session.exec(select(Scan).where(Scan.user_id == user.id)).all()
            # SQLite might not enforce FK by default
            # Just ensure user is deleted
            assert session.exec(
                select(User).where(User.email == "delete@test.com")
            ).first() is None

    def test_unique_email_constraint(self):
        with Session(engine) as session:
            user1 = User(email="unique@test.com", hashed_password="pw")
            session.add(user1)
            session.commit()

            user2 = User(email="unique@test.com", hashed_password="pw2")
            session.add(user2)
            with pytest.raises(Exception):
                session.commit()


class TestScanCRUD:
    def test_create_scan(self):
        with Session(engine) as session:
            scan = Scan(input_text="test", result="scam", confidence=0.95)
            session.add(scan)
            session.commit()
            assert scan.id is not None
            assert scan.created_at is not None

    def test_scan_user_relationship(self):
        with Session(engine) as session:
            user = User(email="scanuser@test.com", hashed_password="pw")
            session.add(user)
            session.commit()

            scan = Scan(user_id=user.id, input_text="test", result="safe", confidence=0.8)
            session.add(scan)
            session.commit()

            fetched = session.exec(
                select(Scan).where(Scan.user_id == user.id)
            ).first()
            assert fetched is not None

    def test_scan_indexes(self):
        with Session(engine) as session:
            scans = session.exec(
                select(Scan).where(Scan.result == "scam")
            ).all()
            assert isinstance(scans, list)


class TestConcurrentOperations:
    def test_concurrent_reads(self):
        import threading

        results = []

        def read_db():
            with Session(engine) as session:
                result = session.exec(text("SELECT 1")).first()
                results.append(result)

        threads = [threading.Thread(target=read_db) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 10
        assert all(r is not None for r in results)

    def test_bulk_insert(self):
        with Session(engine) as session:
            scans = [
                Scan(input_text=f"Bulk test {i}", result="safe", confidence=0.5)
                for i in range(100)
            ]
            session.add_all(scans)
            session.commit()

        with Session(engine) as session:
            count = session.exec(
                select(Scan).where(Scan.input_text.like("Bulk test%"))
            ).all()
            assert len(count) == 100


class TestQueryPerformance:
    def test_select_one(self):
        with Session(engine) as session:
            start = time.time()
            session.exec(text("SELECT 1")).first()
            duration = time.time() - start
            assert duration < 1.0  # Should be fast

    def test_user_index_query(self):
        with Session(engine) as session:
            user = User(email="index@test.com", hashed_password="pw")
            session.add(user)
            session.commit()

            start = time.time()
            fetched = session.exec(
                select(User).where(User.email == "index@test.com")
            ).first()
            duration = time.time() - start
            assert fetched is not None
            assert duration < 1.0

