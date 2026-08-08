"""
Explainability API Schemas
============================
"""


from pydantic import BaseModel, Field


class ProbabilityGraph(BaseModel):
    """Probability distribution graph data."""
    labels: list[str] = Field(..., description="Class labels (safe, suspicious, scam)")
    probabilities: list[float] = Field(..., description="Probability scores for each label")
    predicted_class: str = Field(..., description="The predicted class")
    confidence: float = Field(..., ge=0.0, le=1.0)


class FeatureImportance(BaseModel):
    """Feature importance data for explainability."""
    feature_name: str = Field(..., description="Name of the feature")
    importance_score: float = Field(..., ge=-1.0, le=1.0, description="Importance score")
    category: str = Field(default="textual", description="Feature category")
    description: str = Field(default="", description="Human-readable description")


class AttentionMap(BaseModel):
    """Attention map showing which parts of the input were most influential."""
    tokens: list[str] = Field(..., description="Input tokens")
    attention_weights: list[float] = Field(..., description="Attention weights for each token")
    highlights: list[int] = Field(default_factory=list, description="Indices of highlighted tokens")


class CounterfactualExplanation(BaseModel):
    """Counterfactual explanation showing how input changes would alter predictions."""
    original_text: str = Field(..., description="Original input text")
    modified_text: str = Field(..., description="Modified text that changes prediction")
    original_label: str = Field(..., description="Original prediction label")
    new_label: str = Field(..., description="New prediction label after modification")
    change_required: str = Field(..., description="Description of what was changed")
    minimal_changes: int = Field(..., ge=0, description="Number of tokens changed")


class PredictionTimeline(BaseModel):
    """Timeline of predictions for trend analysis."""
    timestamps: list[str] = Field(..., description="Timestamps in ISO format")
    predictions: list[str] = Field(..., description="Prediction labels over time")
    confidences: list[float] = Field(..., description="Confidence scores over time")
    labels_map: dict[str, str] = Field(default_factory=dict, description="Label to display name mapping")


class ExplainabilityRequest(BaseModel):
    """Request for explainability analysis."""
    text: str = Field(..., min_length=1, max_length=10000, description="Text to explain")
    prediction_label: str = Field(..., description="Prediction label from the model")
    prediction_confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    include_counterfactuals: bool = Field(default=True, description="Generate counterfactual explanations")
    include_attention: bool = Field(default=True, description="Generate attention map")
    include_timeline: bool = Field(default=False, description="Include prediction timeline")


class ExplainabilityResponse(BaseModel):
    """Comprehensive explainability response."""
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence score")
    top_keywords: list[str] = Field(..., description="Top keywords contributing to prediction")
    reason: str = Field(..., description="Human-readable explanation reason")
    attention_map: AttentionMap | None = Field(None, description="Attention map visualization data")
    probability_graph: ProbabilityGraph = Field(..., description="Probability distribution graph")
    risk_level: str = Field(..., description="Risk level (Low, Medium, High, Critical)")
    model_version: str = Field(..., description="Model version used")
    feature_importance: list[FeatureImportance] = Field(default_factory=list, description="Feature importance breakdown")
    prediction_timeline: PredictionTimeline | None = Field(None, description="Prediction history timeline")
    counterfactuals: list[CounterfactualExplanation] = Field(default_factory=list, description="Counterfactual explanations")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    created_at: str = Field(..., description="Timestamp of the explanation")

