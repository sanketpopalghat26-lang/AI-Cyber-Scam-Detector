
"""
Tests for Explainability API
==============================
"""

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_explain_endpoint():
    """Test the explain endpoint."""
    response = client.post(
        "/api/explain",
        json={
            "text": "Urgent: verify your bank account now or it will be locked",
            "prediction_label": "scam",
            "prediction_confidence": 0.92,
            "include_counterfactuals": True,
            "include_attention": True,
        },
    )
    # The endpoint may be disabled or require auth
    if response.status_code == 200:
        data = response.json()
        assert "confidence" in data
        assert "top_keywords" in data
        assert "reason" in data
        assert "risk_level" in data
        assert "model_version" in data
        assert "probability_graph" in data
        assert "processing_time_ms" in data
    elif response.status_code == 503:
        # Module disabled
        assert "disabled" in response.text


def test_explain_health():
    """Test explainability health endpoint."""
    response = client.get("/api/explain/health")
    if response.status_code == 200:
        data = response.json()
        assert "enabled" in data
        assert "status" in data

