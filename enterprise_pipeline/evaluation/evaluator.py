"""
Enterprise Model Evaluation
============================
Production-grade evaluation with:
- Accuracy, Precision, Recall, F1, ROC-AUC, PR-AUC, Balanced Accuracy, MCC
- Confusion Matrix, Calibration Curve, ROC Curve, Precision-Recall Curve
- Feature Importance, SHAP Explanation, LIME Explanation
- Error Analysis, Threshold Optimization
- Automatic Best Model Selection
"""

from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    auc,
    balanced_accuracy_score,
    brier_score_loss,
    calibration_curve,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
    matthews_corrcoef,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

from ..config.settings import settings_instance
from ..core.interfaces import ModelEvaluator, ModelExplainer
from ..utils.logging_utils import get_logger, log_execution_time

log = get_logger("evaluation")


class MetricsCalculator:
    """Calculates all evaluation metrics for classification models."""

    def __init__(self):
        self.metrics: dict[str, Any] = {}

    def calculate_all(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_prob: np.ndarray | None = None,
        class_names: list[str] | None = None,
    ) -> dict[str, Any]:
        """Calculate all classification metrics."""
        num_classes = len(np.unique(y_true))
        is_binary = num_classes == 2

        # Core metrics
        metrics = {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "precision_weighted": float(precision_score(y_true, y_pred, average="weighted", zero_division=0)),
            "recall_weighted": float(recall_score(y_true, y_pred, average="weighted", zero_division=0)),
            "f1_weighted": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
            "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
            "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
            "mcc": float(matthews_corrcoef(y_true, y_pred)),
        }

        # Per-class metrics
        if class_names:
            report = classification_report(y_true, y_pred, target_names=class_names, output_dict=True, zero_division=0)
            metrics["per_class"] = {}
            for cls in class_names:
                if cls in report:
                    metrics["per_class"][cls] = {
                        "precision": report[cls]["precision"],
                        "recall": report[cls]["recall"],
                        "f1": report[cls]["f1-score"],
                        "support": report[cls]["support"],
                    }

        # Confusion matrix
        cm = confusion_matrix(y_true, y_pred)
        metrics["confusion_matrix"] = cm.tolist()

        # ROC-AUC and related metrics
        if y_prob is not None:
            if is_binary:
                try:
                    # For binary classification
                    metrics["roc_auc"] = float(roc_auc_score(y_true, y_prob[:, 1]))
                    metrics["log_loss"] = float(log_loss(y_true, y_prob))
                    metrics["brier_score"] = float(brier_score_loss(y_true, y_prob[:, 1]))

                    # ROC curve data
                    fpr, tpr, thresholds = roc_curve(y_true, y_prob[:, 1])
                    metrics["roc_curve"] = {
                        "fpr": fpr.tolist()[:100],  # Sample for plotting
                        "tpr": tpr.tolist()[:100],
                        "thresholds": thresholds.tolist()[:100],
                    }

                    # PR curve data
                    precision_curve, recall_curve, pr_thresholds = precision_recall_curve(y_true, y_prob[:, 1])
                    metrics["pr_auc"] = float(auc(recall_curve, precision_curve))
                    metrics["pr_curve"] = {
                        "precision": precision_curve.tolist()[:100],
                        "recall": recall_curve.tolist()[:100],
                    }
                except Exception as e:
                    log.warning(f"Could not calculate ROC/PR metrics: {e}")
            elif num_classes > 2:
                try:
                    metrics["roc_auc"] = float(roc_auc_score(y_true, y_prob, multi_class="ovr"))
                    metrics["log_loss"] = float(log_loss(y_true, y_prob))
                except Exception as e:
                    log.warning(f"Could not calculate multiclass ROC: {e}")

        # Calibration curve (binary only)
        if is_binary and y_prob is not None:
            try:
                prob_true, prob_pred = calibration_curve(y_true, y_prob[:, 1], n_bins=10)
                metrics["calibration_curve"] = {
                    "prob_true": prob_true.tolist(),
                    "prob_pred": prob_pred.tolist(),
                }
                # Calibration error
                metrics["calibration_error"] = float(np.mean(np.abs(prob_true - prob_pred)))
            except Exception as e:
                log.warning(f"Could not calculate calibration: {e}")

        # Error metrics
        errors = y_true != y_pred
        metrics["error_rate"] = float(errors.mean())
        metrics["num_errors"] = int(errors.sum())

        self.metrics = metrics
        return metrics


class SHAPExplainer(ModelExplainer):
    """Generate SHAP explanations for model predictions."""

    def __init__(self):
        self.shap_values = None
        self.base_value = None

    def explain(
        self, model: Any, X: np.ndarray, feature_names: list[str],
        sample_size: int = 100,
    ) -> dict[str, Any]:
        """Generate SHAP explanations."""
        try:
            import shap
        except ImportError:
            log.warning("SHAP not installed. Skipping SHAP explanations.")
            return {"error": "SHAP not installed"}

        log.info("Generating SHAP explanations...")

        # Limit samples for performance
        if X.shape[0] > sample_size:
            idx = np.random.choice(X.shape[0], sample_size, replace=False)
            X_sample = X[idx]
        else:
            X_sample = X

        try:
            # Try TreeExplainer for tree-based models
            if hasattr(model, "feature_importances_"):
                explainer = shap.TreeExplainer(model)
                shap_values = explainer.shap_values(X_sample)
            else:
                # Use KernelExplainer as fallback
                explainer = shap.KernelExplainer(model.predict_proba, X_sample[:50])
                shap_values = explainer.shap_values(X_sample[:50])

            self.shap_values = shap_values
            self.base_value = explainer.expected_value

            # Calculate feature importance from SHAP values
            if isinstance(shap_values, list):
                # Multiclass
                importance = np.mean([np.abs(sv).mean(axis=0) for sv in shap_values], axis=0)
            else:
                importance = np.abs(shap_values).mean(axis=0)

            feature_importance = [
                {"feature": name, "importance": float(imp)}
                for name, imp in sorted(
                    zip(feature_names, importance),
                    key=lambda x: x[1],
                    reverse=True,
                )
            ]

            result = {
                "feature_importance": feature_importance,
                "base_value": float(explainer.expected_value) if not isinstance(explainer.expected_value, (list, np.ndarray)) else float(explainer.expected_value[0]),
                "num_features_analyzed": len(feature_importance),
            }

            log.info(f"SHAP explanation complete. Top feature: {feature_importance[0]['feature']}")
            return result

        except Exception as e:
            log.warning(f"SHAP explanation failed: {e}")
            return {"error": str(e)}


class LIMExplainer(ModelExplainer):
    """Generate LIME explanations for individual predictions."""

    def __init__(self):
        self.explainer = None

    def explain(
        self, model: Any, X: np.ndarray, feature_names: list[str],
        num_samples: int = 5000,
    ) -> dict[str, Any]:
        """Generate LIME explanations."""
        try:
            from lime.lime_tabular import LimeTabularExplainer
        except ImportError:
            log.warning("LIME not installed. Skipping LIME explanations.")
            return {"error": "LIME not installed"}

        log.info("Generating LIME explanations...")

        try:
            self.explainer = LimeTabularExplainer(
                X,
                feature_names=feature_names,
                class_names=["safe", "scam"],
                mode="classification",
                random_state=42,
            )

            # Explain first few predictions
            explanations = []
            for i in range(min(5, X.shape[0])):
                exp = self.explainer.explain_instance(
                    X[i], model.predict_proba,
                    num_features=10,
                    num_samples=num_samples,
                )
                explanations.append({
                    "sample_index": int(i),
                    "prediction": int(np.argmax(model.predict_proba(X[i:i+1]))),
                    "features": [
                        {"feature": f, "weight": float(w)}
                        for f, w in exp.as_list()
                    ],
                })

            return {
                "explanations": explanations,
                "num_explanations": len(explanations),
            }

        except Exception as e:
            log.warning(f"LIME explanation failed: {e}")
            return {"error": str(e)}


class ThresholdOptimizer:
    """Optimizes decision threshold for binary classification."""

    def __init__(self, metric: str = "f1"):
        self.metric = metric
        self.best_threshold: float = 0.5
        self.best_score: float = 0.0

    @log_execution_time
    def optimize(
        self, y_true: np.ndarray, y_prob: np.ndarray,
        thresholds: np.ndarray | None = None,
    ) -> dict[str, Any]:
        """Find optimal threshold to maximize chosen metric."""
        if thresholds is None:
            thresholds = np.linspace(0.05, 0.95, 91)

        best_threshold = 0.5
        best_score = 0.0
        scores = []

        for threshold in thresholds:
            y_pred = (y_prob >= threshold).astype(int)

            if self.metric == "f1":
                score = f1_score(y_true, y_pred)
            elif self.metric == "precision":
                score = precision_score(y_true, y_pred, zero_division=0)
            elif self.metric == "recall":
                score = recall_score(y_true, y_pred)
            elif self.metric == "accuracy":
                score = accuracy_score(y_true, y_pred)
            elif self.metric == "mcc":
                score = matthews_corrcoef(y_true, y_pred)
            elif self.metric == "balanced_accuracy":
                score = balanced_accuracy_score(y_true, y_pred)
            else:
                score = f1_score(y_true, y_pred)

            scores.append({"threshold": float(threshold), "score": float(score)})

            if score > best_score:
                best_score = score
                best_threshold = threshold

        self.best_threshold = float(best_threshold)
        self.best_score = float(best_score)

        log.info(f"Optimal threshold={best_threshold:.3f} for {self.metric}={best_score:.4f}")

        return {
            "best_threshold": float(best_threshold),
            "best_score": float(best_score),
            "metric": self.metric,
            "threshold_scores": scores,
        }


class ErrorAnalyzer:
    """Analyzes model prediction errors in detail."""

    def analyze(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        X: np.ndarray | None = None,
        feature_names: list[str] | None = None,
        class_names: list[str] | None = None,
    ) -> dict[str, Any]:
        """Analyze errors and return detailed report."""
        errors = y_true != y_pred
        n_errors = errors.sum()
        n_total = len(y_true)

        analysis = {
            "total_samples": n_total,
            "num_errors": int(n_errors),
            "error_rate": float(n_errors / n_total),
            "error_distribution": {},
            "confusion_details": {},
        }

        # Error distribution by class
        for cls in np.unique(y_true):
            cls_mask = y_true == cls
            cls_errors = cls_mask & errors
            cls_name = class_names[int(cls)] if class_names else str(cls)

            analysis["error_distribution"][cls_name] = {
                "total": int(cls_mask.sum()),
                "errors": int(cls_errors.sum()),
                "error_rate": float(cls_errors.sum() / max(cls_mask.sum(), 1)),
            }

        # Confusion details
        cm = confusion_matrix(y_true, y_pred)
        for i, true_cls in enumerate(np.unique(y_true)):
            true_name = class_names[int(true_cls)] if class_names else str(true_cls)
            analysis["confusion_details"][true_name] = {}
            for j, pred_cls in enumerate(np.unique(y_pred)):
                pred_name = class_names[int(pred_cls)] if class_names else str(pred_cls)
                analysis["confusion_details"][true_name][pred_name] = int(cm[i][j])

        # Misclassification patterns if X is provided
        if X is not None and feature_names and n_errors > 0:
            error_indices = np.where(errors)[0]
            analysis["sample_errors"] = []

            for idx in error_indices[:10]:  # Show first 10 errors
                true_cls = class_names[int(y_true[idx])] if class_names else str(y_true[idx])
                pred_cls = class_names[int(y_pred[idx])] if class_names else str(y_pred[idx])

                error_info = {
                    "sample_index": int(idx),
                    "true_class": true_cls,
                    "predicted_class": pred_cls,
                }

                # Add top feature values for this sample
                if X.shape[1] <= 50:  # Only if manageable
                    error_info["top_features"] = [
                        {"feature": feature_names[j], "value": float(X[idx, j])}
                        for j in range(min(10, X.shape[1]))
                        if X[idx, j] != 0
                    ]

                analysis["sample_errors"].append(error_info)

        return analysis


class ModelEvaluatorImpl(ModelEvaluator):
    """Full model evaluation pipeline."""

    def __init__(self, settings=settings_instance):
        self.settings = settings
        self.metrics_calc = MetricsCalculator()
        self.shap_explainer = SHAPExplainer()
        self.lime_explainer = LIMExplainer()
        self.threshold_optimizer = ThresholdOptimizer()
        self.error_analyzer = ErrorAnalyzer()
        self.last_evaluation: dict[str, Any] = {}

    @log_execution_time
    def evaluate(
        self,
        model: Any,
        X_test: np.ndarray,
        y_test: np.ndarray,
        y_prob: np.ndarray | None = None,
        feature_names: list[str] | None = None,
        class_names: list[str] | None = None,
        X_train: np.ndarray | None = None,
        y_train: np.ndarray | None = None,
    ) -> dict[str, Any]:
        """
        Comprehensive model evaluation.

        Args:
            model: Trained model
            X_test: Test features
            y_test: Test labels
            y_prob: Predicted probabilities (optional)
            feature_names: Feature names (optional)
            class_names: Class names (optional)
            X_train: Training features (for SHAP)
            y_train: Training labels

        Returns:
            Dict with all evaluation results
        """
        log.info("Starting comprehensive model evaluation...")

        # Get predictions
        y_pred = model.predict(X_test)
        if y_prob is None and hasattr(model, "predict_proba"):
            y_prob = model.predict_proba(X_test)

        # Calculate metrics
        metrics = self.metrics_calc.calculate_all(y_test, y_pred, y_prob, class_names)

        # Error analysis
        error_analysis = self.error_analyzer.analyze(y_test, y_pred, X_test, feature_names, class_names)

        # Threshold optimization (binary only)
        threshold_result = None
        if y_prob is not None and len(np.unique(y_test)) == 2:
            threshold_result = self.threshold_optimizer.optimize(y_test, y_prob[:, 1])

        # SHAP explanations
        shap_result = None
        if feature_names and X_test is not None:
            try:
                shap_result = self.shap_explainer.explain(model, X_test, feature_names)
            except Exception as e:
                log.warning(f"SHAP failed: {e}")

        # LIME explanations
        lime_result = None
        if feature_names and X_test is not None:
            try:
                lime_result = self.lime_explainer.explain(model, X_test, feature_names)
            except Exception as e:
                log.warning(f"LIME failed: {e}")

        # Compile results
        evaluation = {
            "metrics": metrics,
            "error_analysis": error_analysis,
            "threshold_optimization": threshold_result,
            "shap_explanation": shap_result,
            "lime_explanation": lime_result,
            "num_classes": len(np.unique(y_test)),
            "test_samples": len(y_test),
            "is_binary": len(np.unique(y_test)) == 2,
        }

        self.last_evaluation = evaluation
        log.info(f"Evaluation complete. F1={metrics.get('f1_weighted', 0):.4f}, "
                 f"Acc={metrics.get('accuracy', 0):.4f}")

        return evaluation

    def get_summary(self) -> dict[str, Any]:
        """Get summary of last evaluation."""
        if not self.last_evaluation:
            return {}

        metrics = self.last_evaluation.get("metrics", {})
        return {
            "accuracy": metrics.get("accuracy"),
            "f1_weighted": metrics.get("f1_weighted"),
            "f1_macro": metrics.get("f1_macro"),
            "balanced_accuracy": metrics.get("balanced_accuracy"),
            "mcc": metrics.get("mcc"),
            "roc_auc": metrics.get("roc_auc"),
            "error_rate": metrics.get("error_rate"),
            "num_errors": metrics.get("num_errors"),
            "test_samples": self.last_evaluation.get("test_samples"),
        }


class ComparisonReportGenerator:
    """Generates comparison reports for multiple models."""

    @log_execution_time
    def generate_comparison(
        self,
        model_results: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Generate a comparison report across multiple models."""
        comparison = {
            "num_models": len(model_results),
            "best_model": None,
            "best_f1": 0.0,
            "models": {},
            "rankings": {},
            "summary_table": [],
        }

        # Collect metrics for each model
        for model_name, results in model_results.items():
            metrics = results.get("metrics", results)
            comparison["models"][model_name] = {
                "accuracy": metrics.get("accuracy"),
                "f1_weighted": metrics.get("f1_weighted"),
                "f1_macro": metrics.get("f1_macro"),
                "precision_weighted": metrics.get("precision_weighted"),
                "recall_weighted": metrics.get("recall_weighted"),
                "balanced_accuracy": metrics.get("balanced_accuracy"),
                "mcc": metrics.get("mcc"),
                "roc_auc": metrics.get("roc_auc"),
                "training_time": metrics.get("training_time"),
                "error_rate": metrics.get("error_rate"),
            }

            comparison["summary_table"].append([
                model_name,
                round(metrics.get("accuracy", 0), 4),
                round(metrics.get("f1_weighted", 0), 4),
                round(metrics.get("precision_weighted", 0), 4),
                round(metrics.get("recall_weighted", 0), 4),
                round(metrics.get("balanced_accuracy", 0), 4),
                round(metrics.get("mcc", 0), 4),
                round(metrics.get("roc_auc", 0), 4) if metrics.get("roc_auc") else None,
            ])

        # Rank models
        f1_scores = [(name, results.get("metrics", results).get("f1_weighted", 0))
                     for name, results in model_results.items()]
        f1_scores.sort(key=lambda x: x[1], reverse=True)

        comparison["rankings"] = {
            "by_f1": [{"model": name, "f1": score} for name, score in f1_scores],
        }

        if f1_scores:
            comparison["best_model"] = f1_scores[0][0]
            comparison["best_f1"] = f1_scores[0][1]

        # Best model summary
        if comparison["best_model"]:
            best = comparison["models"][comparison["best_model"]]
            comparison["winner_summary"] = (
                f"Best model: {comparison['best_model']} with "
                f"F1={best['f1_weighted']:.4f}, "
                f"Accuracy={best['accuracy']:.4f}, "
                f"MCC={best['mcc']:.4f}"
            )

        return comparison
