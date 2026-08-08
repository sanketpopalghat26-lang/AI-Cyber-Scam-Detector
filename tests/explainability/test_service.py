"""
Tests for the Explainability Service
======================================
"""

import pytest

from backend.app.explainability.config import ExplainabilityConfig
from backend.app.explainability.schemas import ExplainabilityRequest
from backend.app.explainability.service import ExplainabilityService


@pytest.fixture
def service():
    return ExplainabilityService()


@pytest.fixture
def config():
    return ExplainabilityConfig()


@pytest.mark.asyncio
async def test_explain_scam(service):
    """Test explainability for a scam prediction."""
    request = ExplainabilityRequest(
        text="Urgent: verify your bank account now or it will be locked",
        prediction_label="scam",
        prediction_confidence=0.92,
        include_counterfactuals=True,
        include_attention=True,
    )
    result = await service.explain(request)
    assert result.confidence == 0.92
    assert result.risk_level == "Critical"  # confidence 0.92 > 0.9 threshold
    assert len(result.top_keywords) > 0
    assert result.attention_map is not None
    assert len(result.counterfactuals) > 0
    assert result.probability_graph is not None
    assert len(result.feature_importance) > 0
    assert result.model_version is not None
    assert result.processing_time_ms > 0


@pytest.mark.asyncio
async def test_explain_safe(service):
    """Test explainability for a safe prediction."""
    request = ExplainabilityRequest(
        text="Hi, please review the attached invoice before payment.",
        prediction_label="safe",
        prediction_confidence=0.86,
    )
    result = await service.explain(request)
    assert result.risk_level == "Low"


@pytest.mark.asyncio
async def test_explain_suspicious(service):
    """Test explainability for a suspicious prediction."""
    request = ExplainabilityRequest(
        text="Your account has been compromised. Click here to reset.",
        prediction_label="suspicious",
        prediction_confidence=0.72,
    )
    result = await service.explain(request)
    assert result.risk_level == "Medium"


def test_keyword_extraction(service):
    """Test keyword extraction logic."""
    keywords = service._extract_keywords("Urgent: verify your account now!")
    assert len(keywords) > 0
    assert any("urgent" in kw for kw in keywords)


def test_risk_level_determination(service):
    """Test risk level determination."""
    assert service._determine_risk_level("scam", 0.95) == "Critical"
    assert service._determine_risk_level("scam", 0.75) == "High"
    assert service._determine_risk_level("suspicious", 0.8) == "Medium"
    assert service._determine_risk_level("suspicious", 0.5) == "Low"
    assert service._determine_risk_level("safe", 0.9) == "Low"


def test_probability_graph(service):
    """Test probability graph generation."""
    graph = service._build_probability_graph("scam", 0.92)
    assert len(graph.labels) == 3
    assert len(graph.probabilities) == 3
    assert abs(sum(graph.probabilities) - 1.0) < 0.01
    assert graph.predicted_class == "scam"
    assert graph.confidence == 0.92


def test_attention_map(service):
    """Test attention map generation."""
    attention = service._build_attention_map("Urgent: verify your account now!")
    assert len(attention.tokens) > 0
    assert len(attention.attention_weights) == len(attention.tokens)
    assert all(0 <= w <= 1 for w in attention.attention_weights)


def test_feature_importance(service):
    """Test feature importance generation."""
    features = service._build_feature_importance(
        "Urgent: verify your bank password now!", "scam"
    )
    assert len(features) > 0
    for feat in features:
        assert feat.feature_name
        assert -1 <= feat.importance_score <= 1
        assert feat.category


def test_counterfactuals(service):
    """Test counterfactual generation."""
    counterfactuals = service._build_counterfactuals(
        "Urgent: click here to verify your account immediately!", "scam"
    )
    assert len(counterfactuals) > 0
    for cf in counterfactuals:
        assert cf.original_label == "scam"
        assert cf.new_label
        assert cf.original_text
        assert cf.modified_text

