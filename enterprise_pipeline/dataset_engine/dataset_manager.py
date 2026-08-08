"""
Enterprise Dataset Manager
===========================
Production-grade dataset management with:
- Auto-discovery, loading, validation, normalization
- Deduplication, missing value handling, outlier detection
- Class imbalance analysis & balancing (SMOTE/ADASYN/undersampling)
- Fingerprinting, versioning, train/val/test splitting
- Statistics reports, quality scoring, lineage tracking
"""

import hashlib
import importlib.util
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split as sk_train_test_split

from ..config.settings import settings_instance
from ..core.interfaces import (
    DataLineageTracker,
    DatasetBalancer,
    DatasetDiscoverer,
    DatasetFingerprinter,
    DatasetInfo,
    DatasetLoader,
    DatasetSplitter,
    DatasetValidator,
    DatasetVersioner,
    DuplicateDetector,
    ImbalanceAnalyzer,
    LabelNormalizer,
    MissingValueHandler,
    OutlierDetector,
    StatReportGenerator,
)
from ..utils.logging_utils import get_logger, log_execution_time

log = get_logger("dataset_engine")


class CSVLoader(DatasetLoader):
    """Loads CSV datasets."""

    FORMATS = {"csv", "tsv", "txt"}

    def load(self, path: Path, **kwargs) -> pd.DataFrame:
        sep = kwargs.get("sep", ",")
        if path.suffix == ".tsv":
            sep = "\t"
        elif path.suffix == ".txt":
            # Auto-detect delimiter
            with open(path, encoding="utf-8", errors="ignore") as f:
                first_line = f.readline()
            if "\t" in first_line:
                sep = "\t"
            elif "|" in first_line:
                sep = "|"
        return pd.read_csv(path, sep=sep, low_memory=False, encoding="utf-8")

    def supports_format(self, fmt: str) -> bool:
        return fmt.lower() in self.FORMATS


class JSONLoader(DatasetLoader):
    """Loads JSON/JSONL datasets."""

    FORMATS = {"json", "jsonl"}

    def load(self, path: Path, **kwargs) -> pd.DataFrame:
        if path.suffix == ".jsonl" or kwargs.get("lines", False):
            return pd.read_json(path, lines=True, encoding="utf-8")
        return pd.read_json(path, encoding="utf-8")

    def supports_format(self, fmt: str) -> bool:
        return fmt.lower() in self.FORMATS


class ParquetLoader(DatasetLoader):
    """Loads Parquet datasets."""

    FORMATS = {"parquet", "pq"}

    def load(self, path: Path, **kwargs) -> pd.DataFrame:
        return pd.read_parquet(path)

    def supports_format(self, fmt: str) -> bool:
        return fmt.lower() in self.FORMATS


class DatasetLoaderFactory:
    """Factory pattern for creating dataset loaders."""

    _loaders: list[DatasetLoader] = [
        CSVLoader(),
        JSONLoader(),
        ParquetLoader(),
    ]

    @classmethod
    def get_loader(cls, path: Path) -> DatasetLoader:
        """Get appropriate loader for a file."""
        ext = path.suffix.lower().lstrip(".")
        for loader in cls._loaders:
            if loader.supports_format(ext):
                return loader
        raise ValueError(f"No loader found for format: {ext}")

    @classmethod
    def register_loader(cls, loader: DatasetLoader) -> None:
        """Register a custom loader."""
        cls._loaders.append(loader)


class DatasetDiscovererImpl(DatasetDiscoverer):
    """Discovers datasets from file system paths."""

    SUPPORTED_EXTS = {".csv", ".tsv", ".txt", ".json", ".jsonl", ".parquet", ".pq"}

    def discover(self, paths: list[Path]) -> list[DatasetInfo]:
        discovered = []
        for base_path in paths:
            if not base_path.exists():
                log.warning(f"Path does not exist: {base_path}")
                continue
            if base_path.is_file():
                infos = self._process_file(base_path)
                if infos:
                    discovered.append(infos)
            else:
                for file_path in base_path.rglob("*"):
                    if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_EXTS:
                        infos = self._process_file(file_path)
                        if infos:
                            discovered.append(infos)
        log.info(f"Discovered {len(discovered)} datasets")
        return discovered

    def _process_file(self, path: Path) -> DatasetInfo | None:
        try:
            loader = DatasetLoaderFactory.get_loader(path)
            df = loader.load(path, nrows=100)  # Peek at first 100 rows
            info = DatasetInfo(
                name=path.stem,
                path=path,
                format=path.suffix.lower().lstrip("."),
                shape=df.shape,
                columns=df.columns.tolist(),
                num_samples=df.shape[0],
                num_features=df.shape[1],
            )
            return info
        except Exception as e:
            log.warning(f"Could not read {path}: {e}")
            return None


class DatasetValidatorImpl(DatasetValidator):
    """Validates dataset schema and quality."""

    def validate(self, df: pd.DataFrame, info: DatasetInfo) -> dict[str, Any]:
        results = {
            "is_valid": True,
            "issues": [],
            "warnings": [],
            "stats": {},
        }

        # Check for empty dataset
        if df.empty:
            results["is_valid"] = False
            results["issues"].append("Dataset is empty")
            return results

        # Check for minimum samples
        settings = settings_instance
        if len(df) < settings.dataset.min_samples_per_class:
            results["warnings"].append(
                f"Dataset has only {len(df)} samples (minimum recommended: {settings.dataset.min_samples_per_class})"
            )

        # Check label column exists
        if info.label_column and info.label_column not in df.columns:
            results["is_valid"] = False
            results["issues"].append(f"Label column '{info.label_column}' not found")
        elif info.label_column:
            # Check label distribution
            labels = df[info.label_column]
            class_dist = labels.value_counts().to_dict()
            results["stats"]["class_distribution"] = class_dist
            if len(class_dist) < 2:
                results["warnings"].append("Dataset has only one class")

        # Check for constant columns
        for col in df.select_dtypes(include=[np.number]).columns:
            if df[col].nunique() == 1:
                results["warnings"].append(f"Column '{col}' is constant")

        # Check for high cardinality features
        for col in df.select_dtypes(include=["object", "string"]).columns:
            cardinality = df[col].nunique()
            if cardinality > len(df) * 0.95:
                results["warnings"].append(
                    f"Column '{col}' has high cardinality ({cardinality} unique values)"
                )

        # Data types summary
        results["stats"]["dtypes"] = {
            str(dt): count for dt, count in df.dtypes.value_counts().items()
        }
        results["stats"]["memory_mb"] = df.memory_usage(deep=True).sum() / 1024 / 1024

        return results


class LabelNormalizerImpl(LabelNormalizer):
    """Normalizes label columns to standard binary format: scam/safe."""

    LABEL_MAPPING = {
        "scam": ["scam", "fraud", "phishing", "malicious", "spam", "bad", "positive", "1", 1, "true", True, "yes"],
        "safe": ["safe", "legitimate", "benign", "ham", "good", "negative", "0", 0, "false", False, "no"],
        "suspicious": ["suspicious", "unknown", "maybe", "uncertain"],
    }

    def normalize(self, df: pd.DataFrame, label_column: str) -> pd.DataFrame:
        if label_column not in df.columns:
            raise ValueError(f"Label column '{label_column}' not found in dataframe")

        df = df.copy()
        # Convert to string and lowercase
        df[label_column] = df[label_column].astype(str).str.lower().str.strip()

        # Map labels
        def map_label(val: str) -> str:
            for standard, variants in self.LABEL_MAPPING.items():
                if val in variants:
                    return standard
            # Try to infer from common patterns
            if any(term in val for term in ["scam", "fraud", "phish", "malic", "spam"]):
                return "scam"
            if any(term in val for term in ["safe", "legit", "benign", "ham"]):
                return "safe"
            return "suspicious"

        df[label_column] = df[label_column].apply(map_label)
        log.info(f"Labels normalized. Distribution: {df[label_column].value_counts().to_dict()}")
        return df


class DuplicateDetectorImpl(DuplicateDetector):
    """Detects exact and near-duplicate records."""

    def __init__(self, settings=settings_instance):
        self.threshold = settings.dataset.max_duplicate_threshold

    def detect(self, df: pd.DataFrame, threshold: float | None = None, text_cols: list[str] | None = None) -> pd.DataFrame:
        threshold = threshold or self.threshold
        before = len(df)

        # Exact duplicates
        exact_dupes = df.duplicated(keep="first")
        df_clean = df[~exact_dupes].copy()

        # Auto-detect text columns if not provided
        if text_cols is None:
            text_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()

        # Near-duplicates for text columns
        if threshold < 1.0 and text_cols:
            near_dupe_indices = self._detect_near_duplicates(df_clean, text_cols, threshold)
            df_clean = df_clean.drop(index=near_dupe_indices, errors="ignore")

        after = len(df_clean)
        log.info(f"Duplicate detection: {before} -> {after} rows ({before - after} duplicates removed)")
        return df_clean

    def _detect_near_duplicates(self, df: pd.DataFrame, text_cols: list[str], threshold: float) -> list[int]:
        """Detect near-duplicate rows based on text similarity."""
        # Combine text columns for comparison
        combined = df[text_cols].astype(str).agg(" ".join, axis=1).str.lower()

        # Use MinHash-like approach: compare first N chars as fingerprint
        fingerprints = combined.str[:50]
        dupes = fingerprints.duplicated(keep="first")
        return dupes[dupes].index.tolist()


class MissingValueHandlerImpl(MissingValueHandler):
    """Handles missing values with various strategies."""

    STRATEGIES = {"drop", "mean", "median", "mode", "ffill", "bfill", "constant", "auto"}

    def handle(self, df: pd.DataFrame, strategy: str = "auto") -> pd.DataFrame:
        if strategy == "auto":
            strategy = self._auto_detect_strategy(df)

        if strategy not in self.STRATEGIES:
            raise ValueError(f"Unknown strategy: {strategy}. Use one of {self.STRATEGIES}")

        before_missing = df.isnull().sum().sum()
        if before_missing == 0:
            return df

        df = df.copy()

        if strategy == "drop":
            df = df.dropna()
        elif strategy == "mean":
            for col in df.select_dtypes(include=[np.number]).columns:
                df[col] = df[col].fillna(df[col].mean())
        elif strategy == "median":
            for col in df.select_dtypes(include=[np.number]).columns:
                df[col] = df[col].fillna(df[col].median())
        elif strategy == "mode":
            for col in df.columns:
                if not df[col].mode().empty:
                    df[col] = df[col].fillna(df[col].mode()[0])
        elif strategy == "ffill":
            df = df.ffill()
        elif strategy == "bfill":
            df = df.bfill()
        elif strategy == "constant":
            df = df.fillna(0)

        after_missing = df.isnull().sum().sum()
        log.info(f"Missing values handled ({strategy}): {before_missing} -> {after_missing}")
        return df

    def _auto_detect_strategy(self, df: pd.DataFrame) -> str:
        """Auto-detect best strategy based on data characteristics."""
        total = len(df)
        missing_pct = df.isnull().sum() / total
        high_missing = missing_pct[missing_pct > 0.5]

        if len(high_missing) > total * 0.3:
            return "drop"
        if len(df.select_dtypes(include=[np.number]).columns) > 0:
            return "median"
        return "mode"


class OutlierDetectorImpl(OutlierDetector):
    """Detects outliers using IQR and Isolation Forest methods."""

    def __init__(self, contamination: float = 0.05):
        self.contamination = contamination

    def detect(self, df: pd.DataFrame) -> pd.DataFrame:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if not numeric_cols:
            return pd.Series([False] * len(df))

        outlier_mask = pd.Series([False] * len(df))

        # IQR method for each numeric column
        for col in numeric_cols:
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            lower = Q1 - 3 * IQR
            upper = Q3 + 3 * IQR
            col_outliers = (df[col] < lower) | (df[col] > upper)
            outlier_mask = outlier_mask | col_outliers

        n_outliers = outlier_mask.sum()
        log.info(f"Outlier detection: {n_outliers} outliers found ({n_outliers/len(df)*100:.1f}%)")
        return outlier_mask


class ImbalanceAnalyzerImpl(ImbalanceAnalyzer):
    """Analyzes class imbalance in datasets."""

    def analyze(self, df: pd.DataFrame, label_column: str) -> dict[str, Any]:
        if label_column not in df.columns:
            raise ValueError(f"Label column '{label_column}' not found")

        class_counts = df[label_column].value_counts()
        total = len(df)

        distribution = {str(k): int(v) for k, v in class_counts.items()}
        percentages = {str(k): float(v / total * 100) for k, v in class_counts.items()}

        majority_class = class_counts.index[0]
        majority_count = int(class_counts.iloc[0])
        minority_class = class_counts.index[-1]
        minority_count = int(class_counts.iloc[-1])

        imbalance_ratio = majority_count / max(minority_count, 1)
        is_imbalanced = imbalance_ratio > 3.0  # Standard threshold

        # Gini impurity for distribution evenness
        probs = class_counts / total
        gini = 1 - sum(p ** 2 for p in probs)

        # Entropy
        entropy = -sum(p * np.log2(p) for p in probs)

        # Effective number of classes
        n_eff = 1 / sum(p ** 2 for p in probs)

        result = {
            "total_samples": total,
            "num_classes": len(class_counts),
            "distribution": distribution,
            "percentages": percentages,
            "majority_class": str(majority_class),
            "majority_count": majority_count,
            "minority_class": str(minority_class),
            "minority_count": minority_count,
            "imbalance_ratio": round(imbalance_ratio, 3),
            "is_imbalanced": is_imbalanced,
            "gini_impurity": round(gini, 3),
            "entropy": round(entropy, 3),
            "effective_classes": round(n_eff, 3),
            "needs_balancing": is_imbalanced and imbalance_ratio > 5.0,
        }

        log.info(f"Imbalance analysis: ratio={imbalance_ratio:.2f}, imbalanced={is_imbalanced}")
        return result


class DatasetBalancerImpl(DatasetBalancer):
    """Balances datasets using SMOTE, ADASYN, or random undersampling."""

    def __init__(self, settings=settings_instance):
        self.settings = settings
        self._smote = None
        self._adasyn = None

    def balance(self, df: pd.DataFrame, label_column: str, strategy: str = "auto") -> pd.DataFrame:
        if strategy == "auto":
            strategy = self.settings.dataset.balance_strategy
            if strategy == "auto":
                # Auto-detect: use SMOTE if imbalance ratio > 10, else undersampling
                analyzer = ImbalanceAnalyzerImpl()
                analysis = analyzer.analyze(df, label_column)
                strategy = "smote" if analysis["imbalance_ratio"] > 10 else "undersample"

        log.info(f"Balancing dataset with strategy: {strategy}")

        if strategy == "smote":
            return self._balance_smote(df, label_column)
        elif strategy == "adasyn":
            return self._balance_adasyn(df, label_column)
        elif strategy == "undersample":
            return self._balance_undersample(df, label_column)
        elif strategy == "oversample":
            return self._balance_oversample(df, label_column)
        else:
            raise ValueError(f"Unknown balance strategy: {strategy}")

    def _balance_smote(self, df: pd.DataFrame, label_column: str) -> pd.DataFrame:
        """Apply SMOTE oversampling."""
        try:
            from imblearn.over_sampling import SMOTE

            # Separate features and labels
            X = df.drop(columns=[label_column])
            y = df[label_column]

            # Encode labels
            y_encoded = pd.factorize(y)[0]

            # One-hot encode categorical columns
            X_processed = pd.get_dummies(X, drop_first=False)

            # Ensure no NaN
            X_processed = X_processed.fillna(0)

            smote = SMOTE(random_state=self.settings.model.random_state)
            X_resampled, y_resampled = smote.fit_resample(X_processed, y_encoded)

            # Convert back to DataFrame
            result_df = pd.DataFrame(X_resampled, columns=X_processed.columns)
            label_encoder = dict(enumerate(y.unique()))
            result_df[label_column] = [label_encoder[i] for i in y_resampled]

            log.info(f"SMOTE balancing: {len(df)} -> {len(result_df)} rows")
            return result_df
        except ImportError:
            log.warning("imbalanced-learn not installed, falling back to oversampling")
            return self._balance_oversample(df, label_column)

    def _balance_adasyn(self, df: pd.DataFrame, label_column: str) -> pd.DataFrame:
        """Apply ADASYN oversampling."""
        try:
            from imblearn.over_sampling import ADASYN

            X = df.drop(columns=[label_column])
            y = df[label_column]
            y_encoded = pd.factorize(y)[0]
            X_processed = pd.get_dummies(X, drop_first=False).fillna(0)

            adasyn = ADASYN(random_state=self.settings.model.random_state)
            X_resampled, y_resampled = adasyn.fit_resample(X_processed, y_encoded)

            result_df = pd.DataFrame(X_resampled, columns=X_processed.columns)
            label_encoder = dict(enumerate(y.unique()))
            result_df[label_column] = [label_encoder[i] for i in y_resampled]

            log.info(f"ADASYN balancing: {len(df)} -> {len(result_df)} rows")
            return result_df
        except ImportError:
            log.warning("imbalanced-learn not installed, falling back to SMOTE")
            return self._balance_smote(df, label_column)

    def _balance_undersample(self, df: pd.DataFrame, label_column: str) -> pd.DataFrame:
        """Randomly undersample majority class."""
        try:
            from imblearn.under_sampling import RandomUnderSampler

            X = df.drop(columns=[label_column])
            y = df[label_column]
            y_encoded = pd.factorize(y)[0]
            X_processed = pd.get_dummies(X, drop_first=False).fillna(0)

            rus = RandomUnderSampler(random_state=self.settings.model.random_state)
            X_resampled, y_resampled = rus.fit_resample(X_processed, y_encoded)

            result_df = pd.DataFrame(X_resampled, columns=X_processed.columns)
            label_encoder = dict(enumerate(y.unique()))
            result_df[label_column] = [label_encoder[i] for i in y_resampled]

            log.info(f"Undersampling: {len(df)} -> {len(result_df)} rows")
            return result_df
        except ImportError:
            log.warning("imbalanced-learn not installed, using manual undersampling")
            return self._manual_undersample(df, label_column)

    def _manual_undersample(self, df: pd.DataFrame, label_column: str) -> pd.DataFrame:
        """Manual undersampling without imbalanced-learn."""
        classes = df[label_column].value_counts()
        min_count = classes.min()

        sampled_dfs = []
        for cls in classes.index:
            cls_df = df[df[label_column] == cls]
            if len(cls_df) > min_count:
                cls_df = cls_df.sample(n=min_count, random_state=self.settings.model.random_state)
            sampled_dfs.append(cls_df)

        return pd.concat(sampled_dfs, ignore_index=True)

    def _balance_oversample(self, df: pd.DataFrame, label_column: str) -> pd.DataFrame:
        """Randomly oversample minority classes."""
        classes = df[label_column].value_counts()
        max_count = classes.max()

        sampled_dfs = []
        for cls in classes.index:
            cls_df = df[df[label_column] == cls]
            if len(cls_df) < max_count:
                n_replicates = max_count // len(cls_df)
                remainder = max_count % len(cls_df)
                replicates = [cls_df] * n_replicates
                if remainder > 0:
                    replicates.append(cls_df.sample(n=remainder, random_state=self.settings.model.random_state))
                cls_df = pd.concat(replicates, ignore_index=True)
            sampled_dfs.append(cls_df)

        return pd.concat(sampled_dfs, ignore_index=True)


class DatasetFingerprinterImpl(DatasetFingerprinter):
    """Generates SHA-256 fingerprints of datasets for versioning and integrity."""

    def fingerprint(self, df: pd.DataFrame) -> str:
        """Generate a deterministic hash of the dataset."""
        # Hash the canonical string representation
        hash_input = pd.util.hash_pandas_object(df).values.tobytes()
        return hashlib.sha256(hash_input).hexdigest()


class DatasetVersionerImpl(DatasetVersioner):
    """Manages dataset versions using metadata tracking."""

    def __init__(self, settings=settings_instance):
        self.versions_dir = settings.paths.datasets_dir
        self.metadata_file = self.versions_dir / "dataset_versions.json"
        self._load_metadata()

    def _supports_parquet(self) -> bool:
        return importlib.util.find_spec("pyarrow") is not None or importlib.util.find_spec("fastparquet") is not None

    def _save_data_file(self, df: pd.DataFrame, path: Path) -> None:
        if self._supports_parquet():
            df.to_parquet(path, index=False)
            return
        if path.suffix == ".parquet":
            csv_path = path.with_suffix(".csv")
            df.to_csv(csv_path, index=False)
            return
        df.to_csv(path, index=False)

    def _load_data_file(self, path: Path) -> pd.DataFrame:
        if path.suffix == ".parquet":
            if self._supports_parquet():
                return pd.read_parquet(path)
            csv_path = path.with_suffix(".csv")
            if csv_path.exists():
                return pd.read_csv(csv_path)
            raise ImportError("Parquet support is unavailable and no CSV fallback exists")
        if path.suffix == ".json":
            return pd.read_json(path)
        if path.suffix == ".jsonl":
            return pd.read_json(path, lines=True)
        return pd.read_csv(path)

    def _load_metadata(self) -> None:
        """Load version metadata from disk."""
        if self.metadata_file.exists():
            with open(self.metadata_file) as f:
                self.metadata = json.load(f)
        else:
            self.metadata = {"datasets": {}}

    def _save_metadata(self) -> None:
        """Save version metadata to disk."""
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.metadata_file, "w") as f:
            json.dump(self.metadata, f, indent=2, default=str)

    def save_version(self, df: pd.DataFrame, name: str, version: str) -> Path:
        """Save a versioned copy of the dataset."""
        version_dir = self.versions_dir / name / version
        version_dir.mkdir(parents=True, exist_ok=True)

        data_path = version_dir / "data.parquet"
        self._save_data_file(df, data_path)
        if not data_path.exists() and data_path.suffix == ".parquet":
            data_path = data_path.with_suffix(".csv")

        fingerprinter = DatasetFingerprinterImpl()
        fp = fingerprinter.fingerprint(df)

        # Update metadata
        if name not in self.metadata["datasets"]:
            self.metadata["datasets"][name] = {"versions": {}}

        self.metadata["datasets"][name]["versions"][version] = {
            "fingerprint": fp,
            "shape": list(df.shape),
            "columns": df.columns.tolist(),
            "saved_at": datetime.now(UTC).isoformat(),
            "path": str(data_path),
            "class_distribution": (
                df.iloc[:, -1].value_counts().to_dict()
                if df.shape[1] > 0 else {}
            ),
        }
        self._save_metadata()

        log.info(f"Saved dataset version: {name} v{version} at {data_path}")
        return data_path

    def load_version(self, name: str, version: str) -> pd.DataFrame:
        """Load a specific version of the dataset."""
        if name not in self.metadata["datasets"]:
            raise ValueError(f"Dataset '{name}' not found in registry")
        if version not in self.metadata["datasets"][name]["versions"]:
            raise ValueError(f"Version '{version}' not found for dataset '{name}'")

        version_info = self.metadata["datasets"][name]["versions"][version]
        data_path = Path(version_info["path"])

        if not data_path.exists():
            raise FileNotFoundError(f"Dataset file not found: {data_path}")

        df = self._load_data_file(data_path)

        # Verify fingerprint
        fingerprinter = DatasetFingerprinterImpl()
        actual_fp = fingerprinter.fingerprint(df)
        if actual_fp != version_info["fingerprint"]:
            log.warning(f"Fingerprint mismatch for {name} v{version}: data may be corrupted")

        log.info(f"Loaded dataset version: {name} v{version} ({df.shape})")
        return df

    def list_versions(self, name: str) -> list[dict[str, Any]]:
        """List all versions for a dataset."""
        if name not in self.metadata["datasets"]:
            return []
        versions = self.metadata["datasets"][name]["versions"]
        return [
            {"version": v, **info}
            for v, info in sorted(versions.items())
        ]


class DatasetSplitterImpl(DatasetSplitter):
    """Splits dataset into train/validation/test sets with stratification."""

    def __init__(self, settings=settings_instance):
        self.settings = settings

    def split(
        self, df: pd.DataFrame, label_column: str,
        test_size: float = 0.2, val_size: float = 0.1,
        stratify: bool = True, random_state: int = 42
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Split into train/val/test sets with graceful fallback for small datasets."""
        random_state = random_state or self.settings.model.random_state
        test_size = test_size or self.settings.model.test_size
        val_size = val_size or self.settings.model.val_size

        if len(df) < 6:
            train = df.iloc[: max(1, int(len(df) * 0.6))].copy()
            val = df.iloc[max(1, int(len(df) * 0.6)):].copy()
            test = df.iloc[0:1].copy()
            return train, val, test

        def _safe_split(frame: pd.DataFrame, size: float, stratify_col: pd.Series | None):
            try:
                return sk_train_test_split(frame, test_size=size, random_state=random_state, stratify=stratify_col)
            except ValueError:
                return sk_train_test_split(frame, test_size=size, random_state=random_state, stratify=None)

        stratify_col = df[label_column] if stratify else None
        train_val, test = _safe_split(df, test_size, stratify_col)

        val_relative_size = val_size / (1 - test_size)
        stratify_col = train_val[label_column] if stratify else None
        train, val = _safe_split(train_val, val_relative_size, stratify_col)

        log.info(
            f"Dataset split: train={len(train)} ({len(train)/len(df)*100:.0f}%), "
            f"val={len(val)} ({len(val)/len(df)*100:.0f}%), "
            f"test={len(test)} ({len(test)/len(df)*100:.0f}%)"
        )
        return train, val, test


class StatReportGeneratorImpl(StatReportGenerator):
    """Generates comprehensive dataset statistics reports."""

    def generate(self, df: pd.DataFrame, info: DatasetInfo) -> dict[str, Any]:
        report = {
            "name": info.name,
            "source": str(info.path),
            "generated_at": datetime.now(UTC).isoformat(),
            "overview": {
                "rows": len(df),
                "columns": len(df.columns),
                "memory_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
                "duplicate_rows": df.duplicated().sum(),
                "missing_cells": int(df.isnull().sum().sum()),
            },
            "column_stats": {},
        }

        for col in df.columns:
            stats = {
                "dtype": str(df[col].dtype),
                "missing": int(df[col].isnull().sum()),
                "missing_pct": round(float(df[col].isnull().mean() * 100), 2),
                "unique": int(df[col].nunique()),
            }

            if pd.api.types.is_numeric_dtype(df[col]):
                stats.update({
                    "mean": round(float(df[col].mean()), 4) if df[col].notna().any() else None,
                    "std": round(float(df[col].std()), 4) if df[col].notna().any() else None,
                    "min": round(float(df[col].min()), 4) if df[col].notna().any() else None,
                    "max": round(float(df[col].max()), 4) if df[col].notna().any() else None,
                    "q25": round(float(df[col].quantile(0.25)), 4) if df[col].notna().any() else None,
                    "q50": round(float(df[col].median()), 4) if df[col].notna().any() else None,
                    "q75": round(float(df[col].quantile(0.75)), 4) if df[col].notna().any() else None,
                    "skewness": round(float(df[col].skew()), 4) if df[col].notna().any() else None,
                    "kurtosis": round(float(df[col].kurtosis()), 4) if df[col].notna().any() else None,
                })
            elif pd.api.types.is_object_dtype(df[col]):
                top_values = df[col].value_counts().head(10).to_dict()
                stats.update({
                    "top_values": {str(k): int(v) for k, v in top_values.items()},
                    "top_category": str(df[col].mode().iloc[0]) if not df[col].mode().empty else None,
                    "top_frequency": int(df[col].value_counts().iloc[0]) if not df[col].value_counts().empty else 0,
                })

            report["column_stats"][col] = stats

        # Quality score calculation
        quality_score = self._calculate_quality(df, report)
        report["quality_score"] = quality_score

        return report

    def _calculate_quality(self, df: pd.DataFrame, report: dict) -> dict[str, Any]:
        """Calculate dataset quality score (0-1)."""
        scores = []

        # Completeness score
        completeness = 1 - (report["overview"]["missing_cells"] / max(df.size, 1))
        scores.append(completeness * 0.3)

        # Uniqueness score
        uniqueness = 1 - (report["overview"]["duplicate_rows"] / max(len(df), 1))
        scores.append(uniqueness * 0.2)

        # Feature variety score
        numeric_cols = len(df.select_dtypes(include=[np.number]).columns)
        cat_cols = len(df.select_dtypes(include=["object", "string"]).columns)
        total_cols = max(len(df.columns), 1)
        variety = (numeric_cols + cat_cols * 0.5) / total_cols
        scores.append(variety * 0.2)

        # Size sufficiency score
        size_score = min(len(df) / 1000, 1.0)
        scores.append(size_score * 0.3)

        total_score = round(sum(scores), 4)
        return {
            "overall": total_score,
            "completeness": round(completeness, 4),
            "uniqueness": round(uniqueness, 4),
            "variety": round(variety, 4),
            "size_sufficiency": round(size_score, 4),
            "grade": self._get_grade(total_score),
        }

    def _get_grade(self, score: float) -> str:
        if score >= 0.9:
            return "A+"
        elif score >= 0.8:
            return "A"
        elif score >= 0.7:
            return "B"
        elif score >= 0.6:
            return "C"
        elif score >= 0.5:
            return "D"
        return "F"


class DataLineageTrackerImpl(DataLineageTracker):
    """Tracks data lineage through transformations."""

    def __init__(self):
        self.history: list[dict[str, Any]] = []

    def log_transformation(self, name: str, params: dict[str, Any]) -> None:
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "transformation": name,
            "params": params,
            "correlation_id": str(uuid.uuid4()),
        }
        self.history.append(entry)
        log.debug(f"Lineage: {name} - {params}")

    def get_lineage(self) -> list[dict[str, Any]]:
        return self.history.copy()

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all transformations."""
        return {
            "total_transformations": len(self.history),
            "transformations": [
                {
                    "step": i + 1,
                    "name": entry["transformation"],
                    "timestamp": entry["timestamp"],
                }
                for i, entry in enumerate(self.history)
            ],
            "started_at": self.history[0]["timestamp"] if self.history else None,
            "completed_at": self.history[-1]["timestamp"] if self.history else None,
        }


class DatasetManager:
    """
    Enterprise Dataset Manager - Orchestrates all dataset operations.

    Provides a unified API for:
    - Discovery, loading, and validation
    - Cleaning (dedup, missing values, outliers)
    - Balancing (SMOTE/ADASYN/undersampling)
    - Versioning and tracking
    - Train/val/test splitting
    - Statistics and quality reporting
    - Data lineage tracking
    """

    def __init__(self, settings=settings_instance):
        self.settings = settings
        self.lineage = DataLineageTrackerImpl()

        # Initialize all sub-components
        self.discoverer = DatasetDiscovererImpl()
        self.loader_factory = DatasetLoaderFactory()
        self.validator = DatasetValidatorImpl()
        self.normalizer = LabelNormalizerImpl()
        self.deduper = DuplicateDetectorImpl(settings)
        self.missing_handler = MissingValueHandlerImpl()
        self.outlier_detector = OutlierDetectorImpl()
        self.imbalance_analyzer = ImbalanceAnalyzerImpl()
        self.balancer = DatasetBalancerImpl(settings)
        self.fingerprinter = DatasetFingerprinterImpl()
        self.versioner = DatasetVersionerImpl(settings)
        self.splitter = DatasetSplitterImpl(settings)
        self.stat_reporter = StatReportGeneratorImpl()

    @log_execution_time
    def discover_datasets(self, paths: list[Path] | None = None) -> list[DatasetInfo]:
        """Auto-discover datasets from specified paths."""
        if paths is None:
            paths = [self.settings.paths.data_dir, self.settings.paths.raw_data_dir]
        self.lineage.log_transformation("discover", {"paths": [str(p) for p in paths]})
        return self.discoverer.discover(paths)

    @log_execution_time
    def load_dataset(self, path: Path, **kwargs) -> pd.DataFrame:
        """Load a dataset from a file."""
        loader = self.loader_factory.get_loader(path)
        self.lineage.log_transformation("load", {"path": str(path), "format": path.suffix})
        return loader.load(path, **kwargs)

    @log_execution_time
    def validate_dataset(self, df: pd.DataFrame, info: DatasetInfo) -> dict[str, Any]:
        """Validate dataset quality."""
        self.lineage.log_transformation("validate", {"shape": list(df.shape)})
        return self.validator.validate(df, info)

    @log_execution_time
    def normalize_labels(self, df: pd.DataFrame, label_column: str) -> pd.DataFrame:
        """Normalize labels to standard format."""
        self.lineage.log_transformation("normalize_labels", {"column": label_column})
        return self.normalizer.normalize(df, label_column)

    @log_execution_time
    def remove_duplicates(self, df: pd.DataFrame, threshold: float | None = None) -> pd.DataFrame:
        """Remove duplicate records."""
        self.lineage.log_transformation("deduplicate", {"threshold": threshold or self.settings.dataset.max_duplicate_threshold})
        return self.deduper.detect(df, threshold)

    @log_execution_time
    def handle_missing_values(self, df: pd.DataFrame, strategy: str = "auto") -> pd.DataFrame:
        """Handle missing values."""
        self.lineage.log_transformation("handle_missing", {"strategy": strategy})
        return self.missing_handler.handle(df, strategy)

    @log_execution_time
    def detect_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect outliers and return boolean mask."""
        self.lineage.log_transformation("detect_outliers", {"shape": list(df.shape)})
        return self.outlier_detector.detect(df)

    @log_execution_time
    def analyze_imbalance(self, df: pd.DataFrame, label_column: str) -> dict[str, Any]:
        """Analyze class imbalance."""
        self.lineage.log_transformation("analyze_imbalance", {"column": label_column})
        return self.imbalance_analyzer.analyze(df, label_column)

    @log_execution_time
    def balance_dataset(self, df: pd.DataFrame, label_column: str, strategy: str = "auto") -> pd.DataFrame:
        """Balance the dataset."""
        self.lineage.log_transformation("balance", {"strategy": strategy, "column": label_column})
        return self.balancer.balance(df, label_column, strategy)

    @log_execution_time
    def fingerprint_dataset(self, df: pd.DataFrame) -> str:
        """Generate dataset fingerprint."""
        fp = self.fingerprinter.fingerprint(df)
        self.lineage.log_transformation("fingerprint", {"fingerprint": fp[:16] + "..."})
        return fp

    @log_execution_time
    def save_version(self, df: pd.DataFrame, name: str, version: str | None = None) -> str:
        """Save a versioned copy of the dataset."""
        if version is None:
            version = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        self.versioner.save_version(df, name, version)
        self.lineage.log_transformation("save_version", {"name": name, "version": version})
        return version

    @log_execution_time
    def load_version(self, name: str, version: str) -> pd.DataFrame:
        """Load a specific version of the dataset."""
        self.lineage.log_transformation("load_version", {"name": name, "version": version})
        return self.versioner.load_version(name, version)

    @log_execution_time
    def split_dataset(
        self, df: pd.DataFrame, label_column: str,
        test_size: float | None = None, val_size: float | None = None,
        stratify: bool = True, random_state: int | None = None
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Split into train/val/test."""
        params = {
            "test_size": test_size or self.settings.model.test_size,
            "val_size": val_size or self.settings.model.val_size,
            "stratify": stratify,
        }
        self.lineage.log_transformation("split", params)
        return self.splitter.split(df, label_column, **params)

    @log_execution_time
    def generate_stat_report(self, df: pd.DataFrame, info: DatasetInfo) -> dict[str, Any]:
        """Generate comprehensive statistics report."""
        self.lineage.log_transformation("stat_report", {"name": info.name})
        return self.stat_reporter.generate(df, info)

    def get_lineage(self) -> list[dict[str, Any]]:
        """Get data lineage history."""
        return self.lineage.get_lineage()

    @log_execution_time
    def process_pipeline(
        self,
        path: Path,
        label_column: str,
        text_column: str | None = None,
        balance_strategy: str = "auto",
        save_versioned: bool = True,
        dataset_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Complete dataset processing pipeline.

        Args:
            path: Path to the dataset file
            label_column: Name of the label column
            text_column: Name of the text column (optional)
            balance_strategy: Balancing strategy ('auto', 'smote', 'adasyn', 'undersample', 'oversample')
            save_versioned: Whether to save versioned copies
            dataset_name: Name for versioning (defaults to filename stem)

        Returns:
            Dict with processed datasets and metadata
        """
        log.info(f"Starting dataset pipeline for: {path}")

        # 1. Load
        df = self.load_dataset(path)
        if dataset_name is None:
            dataset_name = path.stem

        # 2. Create dataset info
        info = DatasetInfo(
            name=dataset_name,
            path=path,
            format=path.suffix.lstrip("."),
            shape=df.shape,
            columns=df.columns.tolist(),
            label_column=label_column,
            text_column=text_column,
        )

        # 3. Validate
        validation = self.validate_dataset(df, info)
        if not validation["is_valid"]:
            log.warning(f"Dataset validation failed: {validation['issues']}")

        # 4. Normalize labels
        df = self.normalize_labels(df, label_column)

        # 5. Remove duplicates
        df = self.remove_duplicates(df)

        # 6. Handle missing values
        df = self.handle_missing_values(df)

        # 7. Detect and remove outliers
        outlier_mask = self.detect_outliers(df)
        n_outliers = outlier_mask.sum()
        if n_outliers > 0:
            df = df[~outlier_mask]
            log.info(f"Removed {n_outliers} outlier rows")

        # 8. Analyze imbalance
        imbalance_analysis = self.analyze_imbalance(df, label_column)

        # 9. Balance if needed
        if imbalance_analysis["needs_balancing"]:
            df = self.balance_dataset(df, label_column, balance_strategy)

        # 10. Generate fingerprint
        fingerprint = self.fingerprint_dataset(df)

        # 11. Save version
        version = None
        if save_versioned:
            version = self.save_version(df, dataset_name)

        # 12. Split
        train_df, val_df, test_df = self.split_dataset(df, label_column)

        # 13. Generate report
        info = DatasetInfo(
            name=dataset_name,
            path=path,
            format=path.suffix.lstrip("."),
            shape=df.shape,
            columns=df.columns.tolist(),
            label_column=label_column,
            text_column=text_column,
            fingerprint=fingerprint,
            version=version,
            class_distribution=imbalance_analysis["distribution"],
            quality_score=self.stat_reporter._calculate_quality(df, {"overview": {
                "rows": len(df),
                "columns": len(df.columns),
                "missing_cells": int(df.isnull().sum().sum()),
                "duplicate_rows": 0,
            }}),
        )
        stat_report = self.generate_stat_report(df, info)

        # Save train/val/test splits
        if save_versioned:
            self.save_version(train_df, f"{dataset_name}_train", version)
            self.save_version(val_df, f"{dataset_name}_val", version)
            self.save_version(test_df, f"{dataset_name}_test", version)

        result = {
            "full_dataset": df,
            "train": train_df,
            "val": val_df,
            "test": test_df,
            "info": info,
            "validation": validation,
            "imbalance_analysis": imbalance_analysis,
            "stat_report": stat_report,
            "lineage": self.get_lineage(),
            "version": version,
            "fingerprint": fingerprint,
        }

        log.info(f"Dataset pipeline complete for: {dataset_name}")
        return result
