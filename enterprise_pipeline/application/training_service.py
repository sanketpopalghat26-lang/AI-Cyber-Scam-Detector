from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline

from enterprise_pipeline.config.settings import Settings
from enterprise_pipeline.config.validation import SettingsValidationError, require_production_ready
from enterprise_pipeline.domain.models import ModelArtifact
from enterprise_pipeline.experiment_tracking.tracker import MLflowTracker
from enterprise_pipeline.infrastructure.dataset_repository import DatasetRepository
from enterprise_pipeline.infrastructure.model_registry import ModelRegistry
from enterprise_pipeline.utils.observability import get_structured_logger


class TrainingService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.logger = get_structured_logger("training_service")
        self.dataset_repository = DatasetRepository(settings=self.settings)
        self.registry = ModelRegistry(settings=self.settings)
        self.tracker = MLflowTracker(settings=self.settings)

    def run_pipeline(self, data_path: Path, dataset_name: str, label_column: str = "label") -> dict[str, Any]:
        try:
            require_production_ready()
        except SettingsValidationError as exc:
            self.logger.warning("Skipping strict production validation", error=str(exc))

        self.logger.info("Starting training pipeline", dataset_name=dataset_name, data_path=str(data_path), label_column=label_column)
        dataset = self.dataset_repository.load_and_prepare(data_path, dataset_name, label_column)
        splits = self.dataset_repository.split(dataset["dataframe"], label_column=label_column)
        self.tracker.start_run(run_name=f"{dataset_name}_train")
        self.tracker.log_dataset_info(dataset_name, dataset["version"], dataset["fingerprint"])

        X_train = splits["train"]["text"]
        y_train = splits["train"][label_column]
        X_val = splits["val"]["text"]
        y_val = splits["val"][label_column]
        X_test = splits["test"]["text"]
        y_test = splits["test"][label_column]

        model = Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=2000)),
            ("clf", LogisticRegression(max_iter=1000, random_state=42)),
        ])
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        metrics = {
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "precision_weighted": float(precision_score(y_test, y_pred, average="weighted", zero_division=0)),
            "recall_weighted": float(recall_score(y_test, y_pred, average="weighted", zero_division=0)),
            "f1_weighted": float(f1_score(y_test, y_pred, average="weighted", zero_division=0)),
        }
        try:
            y_prob = model.predict_proba(X_test)[:, 1]
            metrics["roc_auc"] = float(roc_auc_score(y_test.map({"safe": 0, "scam": 1}), y_prob))
        except Exception:
            pass

        self.tracker.log_params({"dataset_name": dataset_name, "dataset_version": dataset["version"]})
        self.tracker.log_metrics(metrics)

        artifact = ModelArtifact(
            name="scam_detector",
            version=str(int(time.time())),
            model=model,
            metrics=metrics,
            hyperparameters={"max_features": 2000, "ngram_range": [1, 2]},
            dataset_version=dataset["version"],
            feature_set=["text"],
            status="registered",
            is_best=True,
        )
        self.registry.register(artifact)
        self.registry.promote_to_champion(artifact.name, artifact.version)
        export_path = self.registry.export_best_model(artifact)
        self.tracker.log_model(model, "scam_detector")
        self.tracker.end_run()
        self.logger.info("Training pipeline completed", dataset_version=dataset["version"], metrics=metrics)

        return {
            "dataset_version": dataset["version"],
            "best_model_name": artifact.name,
            "best_model_metrics": metrics,
            "export_path": str(export_path),
        }
