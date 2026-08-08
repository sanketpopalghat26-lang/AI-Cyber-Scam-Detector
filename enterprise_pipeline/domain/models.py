from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DatasetArtifact:
    name: str
    version: str
    path: Path
    fingerprint: str
    quality_score: float
    statistics: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelArtifact:
    name: str
    version: str
    model: Any
    metrics: dict[str, Any]
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    dataset_version: str | None = None
    feature_set: list[str] | None = None
    status: str = "registered"
    is_best: bool = False
