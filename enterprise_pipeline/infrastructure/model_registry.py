from __future__ import annotations

import json
import pickle
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from enterprise_pipeline.config.settings import Settings
from enterprise_pipeline.domain.models import ModelArtifact


class ModelRegistry:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.registry_dir = self.settings.paths.registry_dir
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.registry_dir / "registry.json"
        self.index: dict[str, Any] = self._load_index()

    def _load_index(self) -> dict[str, Any]:
        if self.index_path.exists():
            return json.loads(self.index_path.read_text())
        return {"models": []}

    def _save_index(self) -> None:
        self.index_path.write_text(json.dumps(self.index, indent=2))

    def register(self, artifact: ModelArtifact) -> ModelArtifact:
        artifact.version = artifact.version or datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        artifact_path = self.registry_dir / f"{artifact.name}_{artifact.version}.pkl"
        with artifact_path.open("wb") as fh:
            pickle.dump(artifact.model, fh)
        payload = {
            "name": artifact.name,
            "version": artifact.version,
            "metrics": artifact.metrics,
            "hyperparameters": artifact.hyperparameters,
            "dataset_version": artifact.dataset_version,
            "feature_set": artifact.feature_set,
            "status": artifact.status,
            "is_best": artifact.is_best,
            "created_at": datetime.now(UTC).isoformat(),
            "path": str(artifact_path),
        }
        self.index["models"].append(payload)
        self._save_index()
        return artifact

    def promote_to_champion(self, name: str, version: str) -> None:
        for entry in self.index["models"]:
            entry["is_best"] = entry["name"] == name and entry["version"] == version
        self._save_index()

    def get_champion(self) -> dict[str, Any] | None:
        for entry in reversed(self.index["models"]):
            if entry.get("is_best"):
                return entry
        return None

    def export_best_model(self, artifact: ModelArtifact) -> Path:
        registry_path = self.registry_dir / "best_model.pkl"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        with registry_path.open("wb") as fh:
            pickle.dump(artifact.model, fh)
        return registry_path
