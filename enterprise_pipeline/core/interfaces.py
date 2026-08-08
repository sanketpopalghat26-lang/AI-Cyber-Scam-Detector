"""
Enterprise Interfaces - Abstract Base Classes & Protocols
=========================================================
Defines contracts for all major components following SOLID principles.
All concrete implementations depend on these abstractions.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# Type aliases
DataFrame = pd.DataFrame
Series = pd.Series
Array = np.ndarray
ModelType = Any
Features = np.ndarray
Labels = np.ndarray


class DatasetInfo:
    """Value object for dataset metadata."""

    def __init__(
        self,
        name: str,
        path: Path,
        format: str,
        shape: tuple[int, int],
        columns: list[str],
        label_column: str | None = None,
        text_column: str | None = None,
        num_samples: int = 0,
        num_features: int = 0,
        class_distribution: dict[str, int] | None = None,
        quality_score: float = 0.0,
        fingerprint: str | None = None,
        version: str | None = None,
        missing_values: dict[str, int] | None = None,
        duplicate_count: int = 0,
    ):
        self.name = name
        self.path = path
        self.format = format
        self.shape = shape
        self.columns = columns
        self.label_column = label_column
        self.text_column = text_column
        self.num_samples = num_samples or shape[0]
        self.num_features = num_features or shape[1]
        self.class_distribution = class_distribution or {}
        self.quality_score = quality_score
        self.fingerprint = fingerprint
        self.version = version
        self.missing_values = missing_values or {}
        self.duplicate_count = duplicate_count


# ---- Data Engine Interfaces ----

class DatasetDiscoverer(ABC):
    """Auto-discovers datasets from multiple sources."""

    @abstractmethod
    def discover(self, paths: list[Path]) -> list[DatasetInfo]:
        """Discover datasets from given paths."""
        ...


class DatasetLoader(ABC):
    """Loads datasets from various formats."""

    @abstractmethod
    def load(self, path: Path, **kwargs) -> DataFrame:
        """Load a dataset from a file path."""
        ...

    @abstractmethod
    def supports_format(self, format: str) -> bool:
        """Check if this loader supports a given format."""
        ...


class DatasetValidator(ABC):
    """Validates dataset schema and quality."""

    @abstractmethod
    def validate(self, df: DataFrame, info: DatasetInfo) -> dict[str, Any]:
        """Validate dataset and return validation results."""
        ...


class LabelNormalizer(ABC):
    """Normalizes label columns to standard format."""

    @abstractmethod
    def normalize(self, df: DataFrame, label_column: str) -> DataFrame:
        """Normalize labels to binary classes: 'scam' vs 'safe'."""
        ...


class DuplicateDetector(ABC):
    """Detects and removes duplicate records."""

    @abstractmethod
    def detect(self, df: DataFrame, threshold: float = 0.95) -> DataFrame:
        """Detect duplicates and return cleaned dataframe."""
        ...


class MissingValueHandler(ABC):
    """Handles missing values in datasets."""

    @abstractmethod
    def handle(self, df: DataFrame, strategy: str = "auto") -> DataFrame:
        """Handle missing values using specified strategy."""
        ...


class OutlierDetector(ABC):
    """Detects outliers in numerical features."""

    @abstractmethod
    def detect(self, df: DataFrame) -> DataFrame:
        """Return boolean mask of outliers."""
        ...


class ImbalanceAnalyzer(ABC):
    """Analyzes class imbalance in datasets."""

    @abstractmethod
    def analyze(self, df: DataFrame, label_column: str) -> dict[str, Any]:
        """Analyze class distribution and return imbalance metrics."""
        ...


class DatasetBalancer(ABC):
    """Balances dataset using SMOTE, ADASYN, or undersampling."""

    @abstractmethod
    def balance(self, df: DataFrame, label_column: str, strategy: str = "auto") -> DataFrame:
        """Balance the dataset."""
        ...


class DatasetFingerprinter(ABC):
    """Generates unique fingerprints for datasets."""

    @abstractmethod
    def fingerprint(self, df: DataFrame) -> str:
        """Generate a cryptographic fingerprint of the dataset."""
        ...


class DatasetVersioner(ABC):
    """Manages dataset versions."""

    @abstractmethod
    def save_version(self, df: DataFrame, name: str, version: str) -> Path:
        """Save a versioned copy of the dataset."""
        ...

    @abstractmethod
    def load_version(self, name: str, version: str) -> DataFrame:
        """Load a specific version of the dataset."""
        ...


class DatasetSplitter(ABC):
    """Splits dataset into train/validation/test sets."""

    @abstractmethod
    def split(
        self, df: DataFrame, label_column: str,
        test_size: float = 0.2, val_size: float = 0.1,
        stratify: bool = True, random_state: int = 42
    ) -> tuple[DataFrame, DataFrame, DataFrame]:
        """Split dataset into train/val/test."""
        ...


class StatReportGenerator(ABC):
    """Generates comprehensive dataset statistics report."""

    @abstractmethod
    def generate(self, df: DataFrame, info: DatasetInfo) -> dict[str, Any]:
        """Generate statistics report as dictionary."""
        ...


class DataLineageTracker(ABC):
    """Tracks data lineage and transformations."""

    @abstractmethod
    def log_transformation(self, name: str, params: dict[str, Any]) -> None:
        """Log a data transformation step."""
        ...

    @abstractmethod
    def get_lineage(self) -> list[dict[str, Any]]:
        """Get full transformation history."""
        ...


# ---- Feature Engineering Interfaces ----

class FeatureExtractor(ABC):
    """Extracts features from raw data."""

    @abstractmethod
    def extract(self, df: DataFrame) -> DataFrame:
        """Extract features and return feature dataframe."""
        ...

    @property
    @abstractmethod
    def feature_names(self) -> list[str]:
        """Get names of extracted features."""
        ...


class FeatureSelector(ABC):
    """Selects most important features."""

    @abstractmethod
    def select(self, X: Features, y: Labels, feature_names: list[str]) -> list[str]:
        """Select top features and return their names."""
        ...


class NLPEmbedder(ABC):
    """Generates NLP embeddings from text."""

    @abstractmethod
    def embed(self, texts: list[str]) -> Array:
        """Convert texts to embeddings."""
        ...


# ---- Model Interfaces ----

class ModelTrainer(ABC):
    """Trains machine learning models."""

    @abstractmethod
    def train(self, X_train: Features, y_train: Labels, **kwargs) -> ModelType:
        """Train a model and return it."""
        ...


class HyperparameterOptimizer(ABC):
    """Optimizes hyperparameters for models."""

    @abstractmethod
    def optimize(
        self, model_class, X_train: Features, y_train: Labels,
        X_val: Features, y_val: Labels, n_trials: int = 50
    ) -> dict[str, Any]:
        """Find best hyperparameters."""
        ...


class CrossValidator(ABC):
    """Performs cross-validation."""

    @abstractmethod
    def validate(
        self, model_class, X: Features, y: Labels,
        params: dict[str, Any], cv_folds: int = 5, stratified: bool = True
    ) -> dict[str, list[float]]:
        """Perform cross-validation and return metrics."""
        ...


# ---- Evaluation Interfaces ----

class ModelEvaluator(ABC):
    """Evaluates model performance."""

    @abstractmethod
    def evaluate(self, model: ModelType, X_test: Features, y_test: Labels) -> dict[str, float]:
        """Evaluate model and return metrics."""
        ...


class ModelExplainer(ABC):
    """Explains model predictions."""

    @abstractmethod
    def explain(self, model: ModelType, X: Features, feature_names: list[str]) -> dict[str, Any]:
        """Generate explanations for model predictions."""
        ...


class Visualizer(ABC):
    """Generates visualization plots."""

    @abstractmethod
    def plot_confusion_matrix(self, y_true: Labels, y_pred: Labels, save_path: Path) -> None:
        """Plot and save confusion matrix."""
        ...

    @abstractmethod
    def plot_roc_curve(self, y_true: Labels, y_score: Array, save_path: Path) -> None:
        """Plot and save ROC curve."""
        ...

    @abstractmethod
    def plot_pr_curve(self, y_true: Labels, y_score: Array, save_path: Path) -> None:
        """Plot and save Precision-Recall curve."""
        ...


# ---- Experiment Tracking Interfaces ----

class ExperimentTracker(ABC):
    """Tracks experiments and metrics."""

    @abstractmethod
    def start_run(self, run_name: str | None = None) -> None:
        """Start a new experiment run."""
        ...

    @abstractmethod
    def log_params(self, params: dict[str, Any]) -> None:
        """Log parameters for current run."""
        ...

    @abstractmethod
    def log_metrics(self, metrics: dict[str, float]) -> None:
        """Log metrics for current run."""
        ...

    @abstractmethod
    def log_artifact(self, local_path: str) -> None:
        """Log an artifact file."""
        ...

    @abstractmethod
    def log_model(self, model: ModelType, model_name: str) -> None:
        """Log a model."""
        ...

    @abstractmethod
    def end_run(self) -> None:
        """End the current run."""
        ...


# ---- Model Registry Interfaces ----

class ModelRegistry(ABC):
    """Manages model versions and promotions."""

    @abstractmethod
    def register_model(self, model: ModelType, name: str, version: str, metrics: dict[str, float]) -> None:
        """Register a model in the registry."""
        ...

    @abstractmethod
    def promote_to_champion(self, model_name: str, version: str) -> bool:
        """Promote a model to champion."""
        ...

    @abstractmethod
    def get_champion(self, model_name: str) -> ModelType | None:
        """Get the current champion model."""
        ...

    @abstractmethod
    def rollback(self, model_name: str) -> bool:
        """Rollback to previous version."""
        ...


# ---- Continuous Training Interfaces ----

class DriftDetector(ABC):
    """Detects concept and data drift."""

    @abstractmethod
    def detect_drift(self, reference_data: Array, current_data: Array) -> dict[str, Any]:
        """Detect drift between reference and current data."""
        ...


class PerformanceMonitor(ABC):
    """Monitors model performance over time."""

    @abstractmethod
    def log_prediction(self, input_data: Any, prediction: Any, actual: Any | None = None) -> None:
        """Log a prediction for monitoring."""
        ...

    @abstractmethod
    def get_performance_report(self) -> dict[str, Any]:
        """Get current performance report."""
        ...


class AlertHandler(ABC):
    """Handles alerting for drift and performance issues."""

    @abstractmethod
    def send_alert(self, title: str, message: str, severity: str = "info") -> None:
        """Send an alert."""
        ...


# ---- Pipeline Orchestrator Interface ----

class PipelineStep(ABC):
    """Base class for all pipeline steps."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute this pipeline step and return updated context."""
        ...


class PipelineOrchestrator(ABC):
    """Orchestrates the entire ML pipeline."""

    @abstractmethod
    def add_step(self, step: PipelineStep) -> None:
        """Add a step to the pipeline."""
        ...

    @abstractmethod
    def run(self, initial_context: dict[str, Any]) -> dict[str, Any]:
        """Run the entire pipeline."""
        ...
