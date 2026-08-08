"""
Pytest configuration and shared fixtures for enterprise test suite.
"""
import os
import sys
from pathlib import Path

import pytest

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-32-chars-minimum!!")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("ENABLE_CACHE", "false")
os.environ.setdefault("ENABLE_METRICS", "true")
os.environ.setdefault("ENABLE_RATE_LIMITING", "false")
os.environ.setdefault("RATE_LIMIT_MAX", "10000")
os.environ.setdefault("LOG_LEVEL", "ERROR")

# Force DB reset on module load: delete existing user to ensure clean state
try:
    from sqlmodel import Session, text

    from backend.app.core.db import engine
    with Session(engine) as session:
        session.exec(text("DELETE FROM users"))
        session.commit()
except Exception:
    pass


@pytest.fixture(autouse=True)
def reset_state():
    """Reset global state between tests."""
    yield
    from backend.app.core.security import _rate_limit_store, _refresh_token_store, _token_blacklist
    _token_blacklist.clear()
    _refresh_token_store.clear()
    _rate_limit_store.clear()


@pytest.fixture
def test_app():
    """Use the module-level app instance which has all routes registered."""
    from backend.app.main import app
    return app


@pytest.fixture
def client(test_app):
    """FastAPI test client."""
    from fastapi.testclient import TestClient
    with TestClient(test_app) as c:
        yield c


@pytest.fixture
def auth_headers(client) -> dict:
    """Get auth headers for a test user."""
    # Signup
    client.post("/auth/signup", json={
        "email": "test@example.com",
        "password": "StrongPass123!"
    })
    # Login
    resp = client.post("/auth/login", data={
        "username": "test@example.com",
        "password": "StrongPass123!"
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(client) -> dict:
    """Get auth headers for admin user."""
    # Clean any existing admin user
    from sqlmodel import Session, text

    from backend.app.core.db import engine
    with Session(engine) as session:
        session.exec(text("DELETE FROM users"))
        session.commit()

    # Fresh signup (avoid common pattern "admin")
    signup_resp = client.post("/auth/signup", json={
        "email": "admin@example.com",
        "password": "Xyz9#K2m!QpR"
    })
    assert signup_resp.status_code == 200, f"Admin signup failed: {signup_resp.text}"
    # Promote to admin
    with Session(engine) as session:
        session.exec(text("UPDATE users SET is_admin = 1 WHERE email = 'admin@example.com'"))
        session.commit()
    # Login with same password used for signup
    resp = client.post("/auth/login", data={
        "username": "admin@example.com",
        "password": "Xyz9#K2m!QpR"
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
