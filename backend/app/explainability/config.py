"""
Explainability Configuration
=============================
"""

import os
from dataclasses import dataclass


@dataclass
class ExplainabilityConfig:
    """Configuration for the AI Explainability Center."""

    enabled: bool = os.getenv("ENABLE_EXPLAINABILITY", "true").lower() == "true"
    shap_enabled: bool = os.getenv("EXPLAINABILITY_SHAP_ENABLED", "true").lower() == "true"
    lime_enabled: bool = os.getenv("EXPLAINABILITY_LIME_ENABLED", "true").lower() == "true"
    max_counterfactuals: int = int(os.getenv("EXPLAINABILITY_MAX_COUNTERFACTUALS", "3"))
    include_attention_map: bool = os.getenv("EXPLAINABILITY_INCLUDE_ATTENTION", "true").lower() == "true"
    include_feature_importance: bool = os.getenv("EXPLAINABILITY_INCLUDE_FEATURES", "true").lower() == "true"
    include_timeline: bool = os.getenv("EXPLAINABILITY_INCLUDE_TIMELINE", "true").lower() == "true"
    cache_ttl: int = int(os.getenv("EXPLAINABILITY_CACHE_TTL", "600"))
    model_version: str = os.getenv("EXPLAINABILITY_MODEL_VERSION", "2.0.0")

