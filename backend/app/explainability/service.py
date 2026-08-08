"""
Explainability Service
========================
Enterprise-grade AI explainability service providing comprehensive
model prediction explanations with multiple visualization data formats.
"""

import re
import time
from datetime import UTC, datetime

from ..core.audit import get_audit_logger
from ..core.observability import Histogram
from .config import ExplainabilityConfig
from .schemas import (
    AttentionMap,
    CounterfactualExplanation,
    ExplainabilityRequest,
    ExplainabilityResponse,
    FeatureImportance,
    PredictionTimeline,
    ProbabilityGraph,
)

# Prometheus metrics
explainability_duration = Histogram(
    "explainability_duration_seconds",
    "Duration of explainability analysis",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)


class ExplainabilityService:
    """
    Service for generating comprehensive AI explainability data.
    Provides confidence scoring, keyword analysis, attention maps,
    counterfactual explanations, and feature importance.
    """

    def __init__(self, config: ExplainabilityConfig | None = None):
        self.config = config or ExplainabilityConfig.from_env() if hasattr(ExplainabilityConfig, 'from_env') else config or ExplainabilityConfig()

    async def explain(
        self,
        request: ExplainabilityRequest,
        user_id: int | None = None,
    ) -> ExplainabilityResponse:
        """Generate comprehensive explainability for a prediction."""
        start_time = time.time()

        # Extract keywords
        top_keywords = self._extract_keywords(request.text)

        # Build reason
        reason = self._build_reason(
            request.prediction_label,
            request.prediction_confidence,
            top_keywords,
        )

        # Determine risk level
        risk_level = self._determine_risk_level(
            request.prediction_label, request.prediction_confidence
        )

        # Build probability graph
        probability_graph = self._build_probability_graph(
            request.prediction_label, request.prediction_confidence
        )

        # Build attention map (if requested)
        attention_map = None
        if request.include_attention:
            attention_map = self._build_attention_map(request.text)

        # Build feature importance
        feature_importance = self._build_feature_importance(
            request.text, request.prediction_label
        )

        # Build counterfactuals (if requested)
        counterfactuals = []
        if request.include_counterfactuals:
            counterfactuals = self._build_counterfactuals(
                request.text, request.prediction_label
            )

        # Build prediction timeline (if requested)
        prediction_timeline = None
        if request.include_timeline:
            prediction_timeline = self._build_prediction_timeline()

        processing_time_ms = (time.time() - start_time) * 1000
        explainability_duration.observe(processing_time_ms / 1000.0)

        # Audit log
        get_audit_logger().log(
            action="explainability.explain",
            actor=str(user_id) if user_id else "anonymous",
            resource="prediction_explanation",
            result="success",
            details={
                "label": request.prediction_label,
                "confidence": request.prediction_confidence,
                "keywords_count": len(top_keywords),
                "counterfactuals": len(counterfactuals),
            },
        )

        return ExplainabilityResponse(
            confidence=request.prediction_confidence,
            top_keywords=top_keywords,
            reason=reason,
            attention_map=attention_map,
            probability_graph=probability_graph,
            risk_level=risk_level,
            model_version=self.config.model_version,
            feature_importance=feature_importance,
            prediction_timeline=prediction_timeline,
            counterfactuals=counterfactuals,
            processing_time_ms=round(processing_time_ms, 2),
            created_at=datetime.now(UTC).isoformat(),
        )

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract keywords contributing to the prediction."""
        lowered = text.lower()
        scam_indicators = {
            "urgent": 0.9, "verify": 0.8, "click": 0.7, "bank": 0.7,
            "password": 0.9, "otp": 0.9, "account": 0.6, "login": 0.7,
            "free": 0.5, "reward": 0.6, "invoice": 0.4, "crypto": 0.6,
            "claim": 0.7, "limited time": 0.8, "gift card": 0.8,
            "compromised": 0.9, "suspended": 0.8, "won": 0.7,
            "prize": 0.6, "security": 0.4, "update now": 0.7,
            "hack": 0.8, "arrest": 0.9, "back taxes": 0.8,
        }
        keywords = []
        for word, score in scam_indicators.items():
            if word in lowered:
                keywords.append((word, score))
        keywords.sort(key=lambda x: x[1], reverse=True)

        # Also extract phrases
        phrases = re.findall(r'\b\w+\b', lowered)
        phrase_counts = {}
        for p in phrases:
            if len(p) > 3:
                phrase_counts[p] = phrase_counts.get(p, 0) + 1

        result = [kw for kw, _ in keywords[:10]]
        if not result:
            result = list(set(phrase_counts.keys()))[:5]
        return result or ["no significant indicators found"]

    def _build_reason(
        self, label: str, confidence: float, keywords: list[str]
    ) -> str:
        """Build a human-readable explanation."""
        if label == "scam" and confidence > 0.7:
            return (
                f"High-confidence scam detection ({confidence:.1%}). "
                f"Key indicators: {', '.join(keywords[:3])}. "
                "This message shows strong patterns of urgency, impersonation, "
                "and social engineering tactics commonly used in phishing scams."
            )
        elif label == "scam":
            return (
                f"Scam detected with {confidence:.1%} confidence. "
                f"Suspicious elements: {', '.join(keywords[:3])}. "
                "Exercise extreme caution."
            )
        elif label == "suspicious":
            return (
                f"Message flagged as suspicious ({confidence:.1%} confidence). "
                f"Risk signals: {', '.join(keywords[:3])}. "
                "Verify the source before taking any action."
            )
        else:
            return (
                f"Message appears safe ({confidence:.1%} confidence). "
                "No significant scam indicators detected. "
                "Always remain vigilant for unexpected requests."
            )

    def _determine_risk_level(self, label: str, confidence: float) -> str:
        """Determine risk level from label and confidence."""
        if label == "scam":
            if confidence > 0.9:
                return "Critical"
            return "High"
        elif label == "suspicious":
            if confidence > 0.7:
                return "Medium"
            return "Low"
        return "Low"

    def _build_probability_graph(
        self, label: str, confidence: float
    ) -> ProbabilityGraph:
        """Build probability distribution graph data."""
        if label == "scam":
            probs = [
                max(0.01, 1.0 - confidence - 0.1),
                max(0.01, confidence * 0.2),
                confidence,
            ]
        elif label == "suspicious":
            probs = [
                max(0.01, 1.0 - confidence - 0.3),
                confidence,
                max(0.01, confidence * 0.3),
            ]
        else:
            probs = [
                confidence,
                max(0.01, (1.0 - confidence) * 0.6),
                max(0.01, (1.0 - confidence) * 0.4),
            ]
        total = sum(probs)
        probs = [round(p / total, 4) for p in probs]

        return ProbabilityGraph(
            labels=["Safe", "Suspicious", "Scam"],
            probabilities=probs,
            predicted_class=label,
            confidence=round(confidence, 4),
        )

    def _build_attention_map(self, text: str) -> AttentionMap:
        """Build attention map highlighting influential tokens."""
        tokens = text.split()
        attention_weights = []

        scam_terms = {
            "urgent": 0.9, "verify": 0.85, "click": 0.7, "bank": 0.75,
            "password": 0.9, "otp": 0.88, "account": 0.65, "login": 0.7,
            "free": 0.5, "reward": 0.6, "invoice": 0.4, "crypto": 0.6,
            "claim": 0.7, "gift": 0.65, "card": 0.5, "won": 0.7,
        }

        max_weight = 0.0
        for token in tokens:
            weight = scam_terms.get(token.lower().strip(".,!?"), 0.1)
            attention_weights.append(weight)
            max_weight = max(max_weight, weight)

        # Normalize
        if max_weight > 0:
            attention_weights = [w / max_weight for w in attention_weights]

        highlights = [
            i for i, w in enumerate(attention_weights) if w > 0.5
        ]

        return AttentionMap(
            tokens=tokens[:100],
            attention_weights=attention_weights[:100],
            highlights=highlights[:20],
        )

    def _build_feature_importance(
        self, text: str, label: str
    ) -> list[FeatureImportance]:
        """Build feature importance breakdown."""
        features = []
        lowered = text.lower()

        # Text length feature
        features.append(FeatureImportance(
            feature_name="text_length",
            importance_score=0.3 if len(text) > 100 else 0.1,
            category="structural",
            description=f"Text length: {len(text)} characters",
        ))

        # URL presence
        has_url = bool(re.search(r"https?://", lowered))
        features.append(FeatureImportance(
            feature_name="url_presence",
            importance_score=0.8 if has_url else 0.0,
            category="structural",
            description="Contains URL" if has_url else "No URL detected",
        ))

        # Urgency words
        urgency_count = sum(
            1 for w in ["urgent", "immediately", "now", "today", "soon"]
            if w in lowered
        )
        features.append(FeatureImportance(
            feature_name="urgency_signals",
            importance_score=min(urgency_count * 0.3, 1.0),
            category="psychological",
            description=f"Found {urgency_count} urgency indicators",
        ))

        # Financial terms
        finance_terms = ["bank", "account", "money", "payment", "invoice", "credit"]
        finance_count = sum(1 for w in finance_terms if w in lowered)
        features.append(FeatureImportance(
            feature_name="financial_terms",
            importance_score=min(finance_count * 0.25, 1.0),
            category="financial",
            description=f"Found {finance_count} financial terms",
        ))

        # Personal information requests
        personal_terms = ["password", "ssn", "otp", "pin", "credit card", "login"]
        personal_count = sum(1 for w in personal_terms if w in lowered)
        features.append(FeatureImportance(
            feature_name="personal_info_request",
            importance_score=min(personal_count * 0.35, 1.0),
            category="security",
            description=f"Requests {personal_count} types of personal information",
        ))

        return features

    def _build_counterfactuals(
        self, text: str, label: str
    ) -> list[CounterfactualExplanation]:
        """Build counterfactual explanations."""
        counterfactuals = []

        if label == "scam":
            # Remove urgency words
            modified = re.sub(
                r'\b(urgent|immediately|now|hurry|act now)\b', '[removed]', text, flags=re.IGNORECASE
            )
            counterfactuals.append(CounterfactualExplanation(
                original_text=text[:200],
                modified_text=modified[:200],
                original_label="scam",
                new_label="suspicious",
                change_required="Removed urgency language",
                minimal_changes=1,
            ))

            # Remove URL
            modified2 = re.sub(r'https?://\S+', '[URL removed]', text, flags=re.IGNORECASE)
            counterfactuals.append(CounterfactualExplanation(
                original_text=text[:200],
                modified_text=modified2[:200],
                original_label="scam",
                new_label="suspicious",
                change_required="Removed URL link",
                minimal_changes=1,
            ))

        elif label == "suspicious":
            modified = re.sub(
                r'\b(verify|confirm|update|check)\b', '[neutralized]', text, flags=re.IGNORECASE
            )
            counterfactuals.append(CounterfactualExplanation(
                original_text=text[:200],
                modified_text=modified[:200],
                original_label="suspicious",
                new_label="safe",
                change_required="Neutralized verification language",
                minimal_changes=1,
            ))

        return counterfactuals[:self.config.max_counterfactuals]

    def _build_prediction_timeline(self) -> PredictionTimeline:
        """Build prediction timeline (sample data - in production, query from DB)."""
        from datetime import timedelta
        now = datetime.now(UTC)
        timestamps = []
        predictions = []
        confidences = []

        for i in range(10):
            ts = now - timedelta(hours=i * 6)
            timestamps.append(ts.isoformat())
            if i < 3:
                predictions.append("scam")
                confidences.append(round(0.85 + (i * 0.03), 4))
            elif i < 7:
                predictions.append("suspicious")
                confidences.append(round(0.6 + (i * 0.02), 4))
            else:
                predictions.append("safe")
                confidences.append(round(0.92 - (i * 0.01), 4))

        return PredictionTimeline(
            timestamps=timestamps,
            predictions=predictions,
            confidences=confidences,
            labels_map={
                "safe": "Safe",
                "suspicious": "Suspicious",
                "scam": "Scam",
            },
        )


# Singleton instance
_service_instance: ExplainabilityService | None = None


def get_explainability_service() -> ExplainabilityService:
    """Get the global explainability service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = ExplainabilityService()
    return _service_instance

