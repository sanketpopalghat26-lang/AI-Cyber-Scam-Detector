"""
Enterprise Settings Module
===========================
Centralized configuration management using Pydantic Settings.
Reads from environment variables and .env files.

Enterprise patterns used:
- Singleton via dependency injection
- Environment-based config
- Secrets management
- Path resolution
"""

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).resolve().parent.parent.parent


def ensure_dir(path: Path) -> Path:
    """Ensure a directory exists and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class DatabaseSettings:
    """Database configuration."""
    url: str = field(default_factory=lambda: os.getenv(
        "DATABASE_URL", "sqlite:///./enterprise_pipeline.db"
    ))
    echo: bool = os.getenv("DB_ECHO", "false").lower() == "true"
    pool_size: int = int(os.getenv("DB_POOL_SIZE", "10"))
    max_overflow: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))


@dataclass
class PathSettings:
    """All file system paths used by the pipeline."""
    root: Path = field(default_factory=get_project_root)

    # Data directories
    data_dir: Path = field(init=False)
    raw_data_dir: Path = field(init=False)
    processed_data_dir: Path = field(init=False)
    datasets_dir: Path = field(init=False)

    # Model directories
    models_dir: Path = field(init=False)
    registry_dir: Path = field(init=False)
    exports_dir: Path = field(init=False)

    # Output directories
    reports_dir: Path = field(init=False)
    logs_dir: Path = field(init=False)
    artifacts_dir: Path = field(init=False)
    mlruns_dir: Path = field(init=False)

    # Config file paths
    features_config: Path = field(init=False)
    dataset_config: Path = field(init=False)

    def __post_init__(self):
        """Initialize and create all directories."""
        base = self.root
        self.data_dir = ensure_dir(base / "data")
        self.raw_data_dir = ensure_dir(base / "data" / "raw")
        self.processed_data_dir = ensure_dir(base / "data" / "processed")
        self.datasets_dir = ensure_dir(base / "data" / "datasets")
        self.models_dir = ensure_dir(base / "models")
        self.registry_dir = ensure_dir(base / "models" / "registry")
        self.exports_dir = ensure_dir(base / "models" / "exports")
        self.reports_dir = ensure_dir(base / "reports")
        self.logs_dir = ensure_dir(base / "logs")
        self.artifacts_dir = ensure_dir(base / "artifacts")
        self.mlruns_dir = ensure_dir(base / "mlruns")
        self.features_config = base / "enterprise_pipeline" / "config" / "features_config.json"
        self.dataset_config = base / "enterprise_pipeline" / "config" / "datasets_config.json"


@dataclass
class ModelSettings:
    """Model training configuration."""
    random_state: int = int(os.getenv("RANDOM_STATE", "42"))
    test_size: float = float(os.getenv("TEST_SIZE", "0.2"))
    val_size: float = float(os.getenv("VAL_SIZE", "0.1"))
    cv_folds: int = int(os.getenv("CV_FOLDS", "5"))
    cv_stratified: bool = os.getenv("CV_STRATIFIED", "true").lower() == "true"
    n_trials: int = int(os.getenv("N_TRIALS", "50"))
    early_stopping_rounds: int = int(os.getenv("EARLY_STOPPING_ROUNDS", "10"))
    timeout_hours: float = float(os.getenv("TIMEOUT_HOURS", "2.0"))

    # Deep learning
    dl_batch_size: int = int(os.getenv("DL_BATCH_SIZE", "64"))
    dl_epochs: int = int(os.getenv("DL_EPOCHS", "50"))
    dl_learning_rate: float = float(os.getenv("DL_LEARNING_RATE", "0.001"))
    dl_patience: int = int(os.getenv("DL_PATIENCE", "10"))
    dl_embed_dim: int = int(os.getenv("DL_EMBED_DIM", "128"))
    dl_hidden_dim: int = int(os.getenv("DL_HIDDEN_DIM", "256"))


@dataclass
class FeatureSettings:
    """Feature engineering configuration."""
    max_features_tfidf: int = int(os.getenv("MAX_FEATURES_TFIDF", "5000"))
    ngram_range: tuple = (1, 3)
    embedding_dim: int = int(os.getenv("EMBEDDING_DIM", "100"))
    use_sentence_transformers: bool = os.getenv("USE_SENTENCE_TRANSFORMERS", "true").lower() == "true"
    sentence_transformer_model: str = os.getenv(
        "SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2"
    )
    feature_selection_method: str = os.getenv(
        "FEATURE_SELECTION_METHOD", "mutual_info"
    )
    n_features_to_select: int = int(os.getenv("N_FEATURES_TO_SELECT", "100"))


@dataclass
class DatasetSettings:
    """Dataset management configuration."""
    min_samples_per_class: int = int(os.getenv("MIN_SAMPLES_PER_CLASS", "10"))
    max_duplicate_threshold: float = float(os.getenv("MAX_DUPLICATE_THRESHOLD", "0.95"))
    outlier_contamination: float = float(os.getenv("OUTLIER_CONTAMINATION", "0.05"))
    balance_strategy: str = os.getenv("BALANCE_STRATEGY", "auto")
    imbalance_threshold: float = float(os.getenv("IMBALANCE_THRESHOLD", "0.3"))
    quality_score_threshold: float = float(os.getenv("QUALITY_SCORE_THRESHOLD", "0.7"))


@dataclass
class MonitoringSettings:
    """Performance monitoring and drift detection configuration."""
    drift_detection_method: str = os.getenv("DRIFT_DETECTION_METHOD", "psd")
    drift_threshold: float = float(os.getenv("DRIFT_THRESHOLD", "0.05"))
    warning_threshold: float = float(os.getenv("WARNING_THRESHOLD", "0.1"))
    alert_channel: str = os.getenv("ALERT_CHANNEL", "log")
    check_interval_minutes: int = int(os.getenv("CHECK_INTERVAL_MINUTES", "60"))
    performance_window: int = int(os.getenv("PERFORMANCE_WINDOW", "1000"))


@dataclass
class ExperimentSettings:
    """MLflow and experiment tracking configuration."""
    mlflow_tracking_uri: str = os.getenv(
        "MLFLOW_TRACKING_URI", "./mlruns"
    )
    experiment_name: str = os.getenv(
        "MLFLOW_EXPERIMENT_NAME", "ai_cyber_scam_detector"
    )
    track_gpu: bool = os.getenv("TRACK_GPU", "false").lower() == "true"
    track_memory: bool = os.getenv("TRACK_MEMORY", "true").lower() == "true"
    track_cpu: bool = os.getenv("TRACK_CPU", "true").lower() == "true"


@dataclass
class LoggingSettings:
    """Logging configuration."""
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_format: str = os.getenv(
        "LOG_FORMAT",
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} | {message}"
    )
    log_to_file: bool = os.getenv("LOG_TO_FILE", "true").lower() == "true"
    log_to_console: bool = os.getenv("LOG_TO_CONSOLE", "true").lower() == "true"
    log_rotation: str = os.getenv("LOG_ROTATION", "1 day")
    log_retention: str = os.getenv("LOG_RETENTION", "30 days")


@dataclass
class Settings:
    """Main settings container - aggregates all sub-settings."""
    app_name: str = "AI Cyber Scam Detector - Enterprise Pipeline"
    version: str = "2.0.0"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    environment: str = os.getenv("ENVIRONMENT", "production")

    database: DatabaseSettings = field(default_factory=DatabaseSettings)
    paths: PathSettings = field(default_factory=PathSettings)
    model: ModelSettings = field(default_factory=ModelSettings)
    features: FeatureSettings = field(default_factory=FeatureSettings)
    dataset: DatasetSettings = field(default_factory=DatasetSettings)
    monitoring: MonitoringSettings = field(default_factory=MonitoringSettings)
    experiment: ExperimentSettings = field(default_factory=ExperimentSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)

    def to_dict(self) -> dict[str, Any]:
        """Serialize settings to dictionary."""
        result = {}
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            if hasattr(value, "__dataclass_fields__"):
                result[field_name] = {
                    f: getattr(value, f)
                    for f in value.__dataclass_fields__
                }
            else:
                result[field_name] = value
        return result

    def to_json(self, path: Path | None = None) -> str:
        """Serialize to JSON string or file."""
        json_str = json.dumps(self.to_dict(), indent=2, default=str)
        if path:
            path.write_text(json_str)
        return json_str


@lru_cache
def get_settings() -> Settings:
    """Get cached settings singleton."""
    return Settings()


settings_instance = get_settings()
