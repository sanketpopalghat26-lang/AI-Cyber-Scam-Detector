from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from enterprise_pipeline.config.settings import Settings
from enterprise_pipeline.core.interfaces import DatasetInfo
from enterprise_pipeline.dataset_engine.dataset_manager import (
    DatasetDiscovererImpl,
    DatasetFingerprinterImpl,
    DatasetSplitterImpl,
    DatasetValidatorImpl,
    DatasetVersionerImpl,
    DuplicateDetectorImpl,
    ImbalanceAnalyzerImpl,
    LabelNormalizerImpl,
    MissingValueHandlerImpl,
    StatReportGeneratorImpl,
)


class DatasetRepository:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.discoverer = DatasetDiscovererImpl()
        self.validator = DatasetValidatorImpl()
        self.label_normalizer = LabelNormalizerImpl()
        self.duplicate_detector = DuplicateDetectorImpl(settings=self.settings)
        self.missing_handler = MissingValueHandlerImpl()
        self.fingerprinter = DatasetFingerprinterImpl()
        self.versioner = DatasetVersionerImpl(settings=self.settings)
        self.splitter = DatasetSplitterImpl(settings=self.settings)
        self.stats_generator = StatReportGeneratorImpl()
        self.imbalance_analyzer = ImbalanceAnalyzerImpl()

    def load_and_prepare(self, data_path: Path, dataset_name: str, label_column: str = "label") -> dict[str, Any]:
        df = pd.read_csv(data_path)
        df = self._apply_pipeline(df, label_column)
        version = self._make_version()
        path = self.versioner.save_version(df, dataset_name, version)
        fingerprint = self.fingerprinter.fingerprint(df)
        stats = self.stats_generator.generate(df, DatasetInfo(name=dataset_name, path=data_path, format=data_path.suffix.lstrip('.'), shape=df.shape, columns=df.columns.tolist(), label_column=label_column))
        return {
            "name": dataset_name,
            "version": version,
            "path": path,
            "fingerprint": fingerprint,
            "quality_score": stats["quality_score"]["overall"],
            "statistics": stats,
            "dataframe": df,
        }

    def _apply_pipeline(self, df: pd.DataFrame, label_column: str) -> pd.DataFrame:
        df = df.copy()
        if label_column not in df.columns:
            raise ValueError(f"Label column {label_column} not found")
        df = self.label_normalizer.normalize(df, label_column)
        df = self.duplicate_detector.detect(df)
        df = self.missing_handler.handle(df, strategy="median")
        df = self._ensure_text_column(df)
        return df

    def _ensure_text_column(self, df: pd.DataFrame) -> pd.DataFrame:
        if "text" in df.columns:
            return df
        for col in df.columns:
            if df[col].dtype == "object":
                df["text"] = df[col].astype(str)
                break
        if "text" not in df.columns:
            df["text"] = df.iloc[:, 0].astype(str)
        return df

    def split(self, df: pd.DataFrame, label_column: str = "label") -> dict[str, pd.DataFrame]:
        train, val, test = self.splitter.split(df, label_column)
        return {"train": train, "val": val, "test": test}

    def _make_version(self) -> str:
        return datetime.now(UTC).strftime("%Y%m%d%H%M%S")
