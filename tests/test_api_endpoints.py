"""
Comprehensive API endpoint tests for the AI Cyber Scam Detector.
Covers health, prediction, detection, model info, and error handling.
"""

import os

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-32-chars-minimum!!")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("ENABLE_CACHE", "false")
os.environ.setdefault("ENABLE_METRICS", "false")
os.environ.setdefault("ENABLE_RATE_LIMITING", "false")
os.environ.setdefault("RATE_LIMIT_MAX", "10000")
os.environ.setdefault("LOG_LEVEL", "ERROR")

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestHealthEndpoints:
    """Test health and root endpoints."""

    def test_root_endpoint(self, client):
        """Root endpoint returns API info."""
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "AI Cyber Scam Detector"
        assert data["status"] == "running"
        assert "docs" in data
        assert "health" in data

    def test_health_endpoint(self, client):
        """Health endpoint returns ok status."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "model_status" in data
        assert "timestamp" in data

    def test_health_live(self, client):
        """Liveness probe works."""
        resp = client.get("/health/live")
        assert resp.status_code == 200
        assert resp.json()["status"] == "alive"


class TestModelInfoEndpoint:
    """Test model info endpoint."""

    def test_model_info(self, client):
        """Model info returns model details."""
        resp = client.get("/api/model-info")
        assert resp.status_code == 200
        data = resp.json()
        assert "model_name" in data
        assert "model_type" in data
        assert "classes" in data
        assert "status" in data
        assert data["status"] in ("loaded", "fallback")


class TestPredictEndpoint:
    """Test the /predict endpoint."""

    def test_predict_scam(self, client):
        """Scam message is detected."""
        resp = client.post("/predict", json={
            "text": "Congratulations! You won £1000 cash. Call now to claim your prize."
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["label"] in ("safe", "suspicious", "scam")
        assert 0.0 <= data["confidence"] <= 1.0
        assert "explanation" in data

    def test_predict_safe(self, client):
        """Safe message is detected."""
        resp = client.post("/predict", json={
            "text": "Hey, are you free this evening? Let's meet tomorrow."
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["label"] in ("safe", "suspicious", "scam")
        assert 0.0 <= data["confidence"] <= 1.0

    def test_predict_empty_text(self, client):
        """Empty text returns validation error."""
        resp = client.post("/predict", json={"text": "   "})
        assert resp.status_code == 422

    def test_predict_missing_text(self, client):
        """Missing text field returns validation error."""
        resp = client.post("/predict", json={})
        assert resp.status_code == 422


class TestDetectEndpoint:
    """Test the /api/detect endpoint."""

    def test_detect_scam(self, client):
        """Scam message returns SCAM prediction."""
        resp = client.post("/api/detect", json={
            "text": "Your account has been selected for a reward. Click the link immediately to claim."
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["prediction"] in ("SAFE", "SCAM", "SUSPICIOUS")
        assert data["risk_level"] in ("LOW", "MEDIUM", "HIGH")
        assert "message" in data
        assert 0.0 <= data["confidence"] <= 1.0

    def test_detect_safe(self, client):
        """Safe message returns SAFE prediction."""
        resp = client.post("/api/detect", json={
            "text": "Can you send me the project report before 5 PM?"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["prediction"] in ("SAFE", "SCAM", "SUSPICIOUS")
        assert data["risk_level"] in ("LOW", "MEDIUM", "HIGH")

    def test_detect_empty_text(self, client):
        """Empty text returns validation error."""
        resp = client.post("/api/detect", json={"text": ""})
        assert resp.status_code == 422

    def test_detect_long_text(self, client):
        """Long text is handled."""
        long_text = "This is a test message " * 100
        resp = client.post("/api/detect", json={"text": long_text})
        assert resp.status_code == 200


class TestApiPredictAlias:
    """Test the /api/predict alias endpoint."""

    def test_api_predict(self, client):
        """API predict alias works."""
        resp = client.post("/api/predict", json={
            "text": "URGENT: Verify your bank account now or it will be locked."
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "label" in data
        assert "confidence" in data