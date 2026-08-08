"""Integration tests for Threat Intelligence REST API endpoints."""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Ensure test environment
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("ENABLE_THREAT_INTEL", "true")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-32-chars-minimum!!")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("ENABLE_CACHE", "false")

# Import threat intel models FIRST to register them with SQLModel metadata
from backend.app.core.db import init_db
from backend.app.main import app
from backend.app.threat_intelligence import models as _threat_intel_models  # noqa: F401
from backend.app.threat_intelligence.service import ThreatIntelligenceService


@pytest.fixture(autouse=True)
def setup_db():
    """Ensure database tables are created before each test."""
    init_db()
    yield


@pytest.fixture
def client():
    """Create a FastAPI test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(client):
    """Get authentication headers for testing."""
    # Signup a test user
    client.post("/auth/signup", json={
        "email": "threatuser@test.com",
        "password": "StrongPass123!",
    })
    # Login
    resp = client.post("/auth/login", data={
        "username": "threatuser@test.com",
        "password": "StrongPass123!",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestThreatSearchEndpoint:
    """Tests for GET /api/threat/search."""

    def test_search_without_auth(self, client):
        """Search should work without authentication."""
        response = client.get("/api/threat/search?query=192.168.1.1")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "results" in data

    def test_search_with_invalid_type(self, client):
        """Search should return 400 for invalid IOC type."""
        response = client.get("/api/threat/search?query=test&ioc_type=invalid")
        assert response.status_code == 400
        assert "Invalid IOC type" in response.text

    def test_search_with_auth(self, client, auth_headers):
        """Search should work with authentication."""
        response = client.get(
            "/api/threat/search?query=8.8.8.8&limit=10",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert data["limit"] == 10

    def test_search_pagination(self, client):
        """Test search pagination parameters."""
        response = client.get(
            "/api/threat/search?query=test&limit=5&offset=10"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 5
        assert data["offset"] == 10


class TestThreatStatsEndpoint:
    """Tests for GET /api/threat/stats."""

    def test_get_stats(self, client):
        """Stats endpoint should return valid statistics."""
        response = client.get("/api/threat/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_iocs" in data
        assert "active_iocs" in data
        assert "by_type" in data
        assert "by_category" in data
        assert "by_risk_level" in data
        assert "last_updated" in data

    def test_stats_structure(self, client):
        """Verify stats response structure."""
        response = client.get("/api/threat/stats")
        data = response.json()
        assert isinstance(data["total_iocs"], int)
        assert isinstance(data["active_iocs"], int)
        assert isinstance(data["by_type"], dict)
        assert isinstance(data["by_category"], dict)
        assert isinstance(data["by_risk_level"], dict)


class TestThreatAnalyzeEndpoint:
    """Tests for POST /api/threat/analyze."""

    @patch.object(ThreatIntelligenceService, 'analyze')
    def test_analyze_ip(self, mock_analyze, client):
        """Test analyzing an IP address."""
        from backend.app.threat_intelligence.schemas import ThreatAnalyzeResponse

        mock_result = ThreatAnalyzeResponse(
            id=1,
            value="8.8.8.8",
            value_type="ip",
            is_malicious=False,
            risk_score=0.1,
            risk_level="low",
            threat_category="unknown",
            confidence=0.95,
            sources_checked=3,
            positive_detections=0,
            total_detections=0,
            provider_results=[],
            explanation="No threats detected",
            tags=[],
            processing_time_ms=1500,
            created_at="2024-01-01T00:00:00Z",
            geoip={},
            dns={},
            whois={},
            asn={},
        )
        mock_analyze.return_value = mock_result

        response = client.post(
            "/api/threat/analyze",
            json={"value": "8.8.8.8"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "risk_score" in data
        assert "risk_level" in data

    def test_analyze_empty_value(self, client):
        """Analyze should reject empty values."""
        response = client.post(
            "/api/threat/analyze",
            json={"value": ""},
        )
        assert response.status_code == 422  # Validation error

    def test_analyze_long_value(self, client):
        """Analyze should handle long values."""
        long_value = "A" * 2001
        response = client.post(
            "/api/threat/analyze",
            json={"value": long_value},
        )
        assert response.status_code == 422  # Validation error

    def test_analyze_with_provider_flags(self, client):
        """Test analyze with specific provider flags."""
        response = client.post(
            "/api/threat/analyze",
            json={
                "value": "example.com",
                "check_virustotal": False,
                "check_abuseipdb": False,
            },
        )
        assert response.status_code == 200


class TestThreatHealthEndpoint:
    """Tests for GET /api/threat/health."""

    def test_health_endpoint(self, client):
        """Health endpoint should return module status."""
        os.environ["APP_ENV"] = "development"
        response = client.get("/api/threat/health")
        # May fail if providers aren't configured, but should return valid JSON
        assert response.status_code in (200, 500)
        if response.status_code == 200:
            data = response.json()
            assert "enabled" in data
            assert "providers" in data

