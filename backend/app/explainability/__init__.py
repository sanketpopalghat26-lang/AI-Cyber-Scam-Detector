"""
AI Explainability Center
=========================
Enterprise-grade AI explainability module providing confidence scores,
keyword analysis, attention maps, probability graphs, risk levels,
feature importance, prediction timelines, and counterfactual explanations.

Feature Flag: ENABLE_EXPLAINABILITY (default: true)
"""

from .config import ExplainabilityConfig
from .router import router
from .schemas import (
    AttentionMap,
    CounterfactualExplanation,
    ExplainabilityRequest,
    ExplainabilityResponse,
    FeatureImportance,
    PredictionTimeline,
    ProbabilityGraph,
)
from .service import ExplainabilityService

__all__ = [
    "ExplainabilityConfig",
    "ExplainabilityResponse",
    "ExplainabilityRequest",
    "FeatureImportance",
    "AttentionMap",
    "CounterfactualExplanation",
    "PredictionTimeline",
    "ProbabilityGraph",
    "ExplainabilityService",
    "router",
]

