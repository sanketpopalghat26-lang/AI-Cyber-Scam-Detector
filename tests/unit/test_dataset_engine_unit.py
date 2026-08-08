"""Unit tests for dataset engine components."""
import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from enterprise_pipeline.core.interfaces import DatasetInfo
from enterprise_pipeline.dataset_engine.dataset_manager import (
    CSVLoader,
    DataLineageTrackerImpl,
    DatasetDiscovererImpl,
    DatasetFingerprinterImpl,
    DatasetLoaderFactory,
    DatasetManager,
    DatasetSplitterImpl,
    DatasetValidatorImpl,
    DuplicateDetectorImpl,
    ImbalanceAnalyzerImpl,
    JSONLoader,
    LabelNormalizerImpl,
    MissingValueHandlerImpl,
    OutlierDetectorImpl,
    ParquetLoader,
)


# =============================================================================
# CSVLoader Tests
# =============================================================================
class TestCSVLoader:
    def test_load_csv(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write("a,b,c\n1,2,3\n4,5,6")
            f.flush()
            loader = CSVLoader()
            df = loader.load(Path(f.name))
            assert len(df) == 2
            assert list(df.columns) == ["a", "b", "c"]
            assert df["a"].iloc[0] == 1

    def test_load_tsv(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tsv", delete=False, encoding="utf-8") as f:
            f.write("a\tb\tc\n1\t2\t3")
            f.flush()
            loader = CSVLoader()
            df = loader.load(Path(f.name))
            assert len(df) == 1
            assert df["a"].iloc[0] == 1

    def test_load_txt_auto_detect(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("a|b|c\n1|2|3")
            f.flush()
            loader = CSVLoader()
            df = loader.load(Path(f.name))
            assert len(df) == 1
            assert df["a"].iloc[0] == 1

    def test_supports_format(self):
        loader = CSVLoader()
        assert loader.supports_format("csv")
        assert loader.supports_format("tsv")
        assert loader.supports_format("txt")
        assert not loader.supports_format("json")

    def test_load_with_custom_sep(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write("a;b;c\n1;2;3")
            f.flush()
            loader = CSVLoader()
            df = loader.load(Path(f.name), sep=";")
            assert df["a"].iloc[0] == 1


# =============================================================================
# JSONLoader Tests
# =============================================================================
class TestJSONLoader:
    def test_load_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump([{"a": 1}, {"a": 2}], f)
            f.flush()
            loader = JSONLoader()
            df = loader.load(Path(f.name))
            assert len(df) == 2

    def test_load_jsonl(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            f.write('{"a": 1}\n{"a": 2}\n')
            f.flush()
            loader = JSONLoader()
            df = loader.load(Path(f.name))
            assert len(df) == 2

    def test_supports_format(self):
        loader = JSONLoader()
        assert loader.supports_format("json")
        assert loader.supports_format("jsonl")
        assert not loader.supports_format("csv")


# =============================================================================
# ParquetLoader Tests
# =============================================================================
class TestParquetLoader:
    def test_supports_format(self):
        loader = ParquetLoader()
        assert loader.supports_format("parquet")
        assert loader.supports_format("pq")
        assert not loader.supports_format("csv")


# =============================================================================
# DatasetLoaderFactory Tests
# =============================================================================
class TestDatasetLoaderFactory:
    def test_get_loader_csv(self):
        loader = DatasetLoaderFactory.get_loader(Path("test.csv"))
        assert isinstance(loader, CSVLoader)

    def test_get_loader_json(self):
        loader = DatasetLoaderFactory.get_loader(Path("test.json"))
        assert isinstance(loader, JSONLoader)

    def test_get_loader_jsonl(self):
        loader = DatasetLoaderFactory.get_loader(Path("test.jsonl"))
        assert isinstance(loader, JSONLoader)

    def test_get_loader_unsupported(self):
        with pytest.raises(ValueError, match="No loader found"):
            DatasetLoaderFactory.get_loader(Path("test.xyz"))

    def test_register_loader(self):
        class MockLoader:
            def supports_format(self, fmt):
                return fmt == "mock"
            def load(self, path, **kwargs):
                return None
        DatasetLoaderFactory.register_loader(MockLoader())
        loader = DatasetLoaderFactory.get_loader(Path("test.mock"))
        assert isinstance(loader, MockLoader)
        # Cleanup
        DatasetLoaderFactory._loaders = [CSVLoader(), JSONLoader(), ParquetLoader()]


# =============================================================================
# DatasetDiscovererImpl Tests
# =============================================================================
class TestDatasetDiscovererImpl:
    def test_discover_non_existent_path(self):
        discoverer = DatasetDiscovererImpl()
        results = discoverer.discover([Path("/nonexistent/path")])
        assert len(results) == 0

    def test_discover_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write("a,b,c\n1,2,3")
            f.flush()
            discoverer = DatasetDiscovererImpl()
            results = discoverer.discover([Path(f.name)])
            assert len(results) >= 1
            assert results[0].name is not None

    def test_discover_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "test.csv"
            p.write_text("a,b,c\n1,2,3", encoding="utf-8")
            discoverer = DatasetDiscovererImpl()
            results = discoverer.discover([Path(tmpdir)])
            assert len(results) >= 1


# =============================================================================
# DatasetValidatorImpl Tests
# =============================================================================
class TestDatasetValidatorImpl:
    def test_valid_dataset(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        info = DatasetInfo(
            name="test", path=Path("test.csv"), format="csv",
            shape=df.shape, columns=df.columns.tolist(),
            num_samples=3, num_features=2,
        )
        validator = DatasetValidatorImpl()
        result = validator.validate(df, info)
        assert result["is_valid"] is True

    def test_empty_dataset(self):
        df = pd.DataFrame()
        info = DatasetInfo(
            name="test", path=Path("test.csv"), format="csv",
            shape=(0, 0), columns=[], num_samples=0, num_features=0,
        )
        validator = DatasetValidatorImpl()
        result = validator.validate(df, info)
        assert result["is_valid"] is False
        assert any("empty" in issue.lower() for issue in result["issues"])

    def test_missing_label_column(self):
        df = pd.DataFrame({"a": [1, 2]})
        info = DatasetInfo(
            name="test", path=Path("test.csv"), format="csv",
            shape=df.shape, columns=df.columns.tolist(),
            num_samples=2, num_features=1, label_column="label",
        )
        validator = DatasetValidatorImpl()
        result = validator.validate(df, info)
        assert result["is_valid"] is False

    def test_constant_column_warning(self):
        df = pd.DataFrame({"a": [1, 1, 1], "b": [4, 5, 6]})
        info = DatasetInfo(
            name="test", path=Path("test.csv"), format="csv",
            shape=df.shape, columns=df.columns.tolist(),
            num_samples=3, num_features=2,
        )
        validator = DatasetValidatorImpl()
        result = validator.validate(df, info)
        assert any("constant" in w.lower() for w in result["warnings"])


# =============================================================================
# LabelNormalizerImpl Tests
# =============================================================================
class TestLabelNormalizerImpl:
    def test_normalize_scam_labels(self):
        df = pd.DataFrame({"label": ["scam", "fraud", "phishing", "malicious", "spam"]})
        normalizer = LabelNormalizerImpl()
        result = normalizer.normalize(df, "label")
        assert (result["label"] == "scam").all()

    def test_normalize_safe_labels(self):
        df = pd.DataFrame({"label": ["safe", "legitimate", "benign", "ham", "good"]})
        normalizer = LabelNormalizerImpl()
        result = normalizer.normalize(df, "label")
        assert (result["label"] == "safe").all()

    def test_normalize_suspicious_labels(self):
        df = pd.DataFrame({"label": ["suspicious", "unknown", "uncertain"]})
        normalizer = LabelNormalizerImpl()
        result = normalizer.normalize(df, "label")
        assert (result["label"] == "suspicious").all()

    def test_normalize_inference_scam(self):
        df = pd.DataFrame({"label": ["contains_scam_keyword"]})
        normalizer = LabelNormalizerImpl()
        result = normalizer.normalize(df, "label")
        assert result["label"].iloc[0] == "scam"

    def test_normalize_missing_column(self):
        normalizer = LabelNormalizerImpl()
        with pytest.raises(ValueError, match="not found"):
            normalizer.normalize(pd.DataFrame({"a": [1]}), "label")

    def test_normalize_numeric_labels(self):
        df = pd.DataFrame({"label": [1, 0]})
        normalizer = LabelNormalizerImpl()
        result = normalizer.normalize(df, "label")
        assert result["label"].iloc[0] == "scam"
        assert result["label"].iloc[1] == "safe"


# =============================================================================
# DuplicateDetectorImpl Tests
# =============================================================================
class TestDuplicateDetectorImpl:
    def test_detect_exact_duplicates(self):
        df = pd.DataFrame({"a": [1, 2, 2, 3], "b": [4, 5, 5, 6]})
        detector = DuplicateDetectorImpl()
        # Override threshold to avoid near-duplicate check
        detector.threshold = 1.0
        result = detector.detect(df)
        assert len(result) == 3

    def test_detect_no_duplicates(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        detector = DuplicateDetectorImpl()
        detector.threshold = 1.0
        result = detector.detect(df)
        assert len(result) == 3

    def test_detect_near_duplicates(self):
        df = pd.DataFrame({
            "text": ["hello world", "hello world", "different text"],
            "num": [1, 2, 3],
        })
        detector = DuplicateDetectorImpl()
        detector.threshold = 0.9
        result = detector.detect(df, threshold=0.9, text_cols=["text"])
        assert len(result) == 2  # One near-duplicate removed

    def test_detect_all_duplicates(self):
        df = pd.DataFrame({"a": [1, 1, 1]})
        detector = DuplicateDetectorImpl()
        detector.threshold = 1.0
        result = detector.detect(df)
        assert len(result) == 1


# =============================================================================
# MissingValueHandlerImpl Tests
# =============================================================================
class TestMissingValueHandlerImpl:
    def test_handle_drop(self):
        df = pd.DataFrame({"a": [1, None, 3], "b": [4, 5, None]})
        handler = MissingValueHandlerImpl()
        result = handler.handle(df, "drop")
        assert len(result) == 1  # Only row 0 survives

    def test_handle_mean(self):
        df = pd.DataFrame({"a": [1.0, None, 3.0], "b": [4.0, 5.0, 6.0]})
        handler = MissingValueHandlerImpl()
        result = handler.handle(df, "mean")
        assert result["a"].iloc[1] == 2.0  # Mean of 1 and 3

    def test_handle_median(self):
        df = pd.DataFrame({"a": [1.0, None, 10.0], "b": [4.0, 5.0, 6.0]})
        handler = MissingValueHandlerImpl()
        result = handler.handle(df, "median")
        assert result["a"].iloc[1] == 5.5  # Median of 1 and 10

    def test_handle_mode(self):
        df = pd.DataFrame({"a": [1, None, 1, 2], "b": [4, 5, 6, 7]})
        handler = MissingValueHandlerImpl()
        result = handler.handle(df, "mode")
        assert result["a"].iloc[1] == 1

    def test_handle_no_missing(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        handler = MissingValueHandlerImpl()
        result = handler.handle(df, "drop")
        assert len(result) == 3

    def test_handle_unknown_strategy(self):
        df = pd.DataFrame({"a": [1, None]})
        handler = MissingValueHandlerImpl()
        with pytest.raises(ValueError, match="Unknown strategy"):
            handler.handle(df, "invalid_strategy")

    def test_handle_constant(self):
        df = pd.DataFrame({"a": [1, None]})
        handler = MissingValueHandlerImpl()
        result = handler.handle(df, "constant")
        assert result["a"].iloc[1] == 0

    def test_handle_ffill(self):
        df = pd.DataFrame({"a": [1, None, None, 4]})
        handler = MissingValueHandlerImpl()
        result = handler.handle(df, "ffill")
        assert result["a"].iloc[1] == 1
        assert result["a"].iloc[2] == 1

    def test_handle_bfill(self):
        df = pd.DataFrame({"a": [1, None, None, 4]})
        handler = MissingValueHandlerImpl()
        result = handler.handle(df, "bfill")
        assert result["a"].iloc[1] == 4
        assert result["a"].iloc[2] == 4


# =============================================================================
# OutlierDetectorImpl Tests
# =============================================================================
class TestOutlierDetectorImpl:
    def test_detect_outliers(self):
        df = pd.DataFrame({"a": [1, 2, 3, 100, 4, 5], "b": [1, 1, 1, 1, 1, 1]})
        detector = OutlierDetectorImpl()
        mask = detector.detect(df)
        assert mask.sum() >= 1  # 100 is an outlier

    def test_no_outliers(self):
        df = pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": [5, 4, 3, 2, 1]})
        detector = OutlierDetectorImpl()
        mask = detector.detect(df)
        assert mask.sum() == 0

    def test_no_numeric_columns(self):
        df = pd.DataFrame({"a": ["x", "y", "z"]})
        detector = OutlierDetectorImpl()
        mask = detector.detect(df)
        assert mask.sum() == 0
        assert len(mask) == 3


# =============================================================================
# ImbalanceAnalyzerImpl Tests
# =============================================================================
class TestImbalanceAnalyzerImpl:
    def test_balanced_dataset(self):
        df = pd.DataFrame({"label": ["A", "A", "B", "B"]})
        analyzer = ImbalanceAnalyzerImpl()
        result = analyzer.analyze(df, "label")
        assert result["is_imbalanced"] is False
        assert result["imbalance_ratio"] == 1.0

    def test_imbalanced_dataset(self):
        df = pd.DataFrame({"label": ["A"] * 10 + ["B"] * 2})
        analyzer = ImbalanceAnalyzerImpl()
        result = analyzer.analyze(df, "label")
        assert result["is_imbalanced"] is True

    def test_missing_label_column(self):
        analyzer = ImbalanceAnalyzerImpl()
        with pytest.raises(ValueError, match="not found"):
            analyzer.analyze(pd.DataFrame({"a": [1]}), "label")


# =============================================================================
# DatasetFingerprinterImpl Tests
# =============================================================================
class TestDatasetFingerprinterImpl:
    def test_fingerprint_consistent(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        fingerprinter = DatasetFingerprinterImpl()
        fp1 = fingerprinter.fingerprint(df)
        fp2 = fingerprinter.fingerprint(df)
        assert fp1 == fp2

    def test_fingerprint_different(self):
        df1 = pd.DataFrame({"a": [1, 2, 3]})
        df2 = pd.DataFrame({"a": [4, 5, 6]})
        fingerprinter = DatasetFingerprinterImpl()
        assert fingerprinter.fingerprint(df1) != fingerprinter.fingerprint(df2)


# =============================================================================
# DatasetSplitterImpl Tests
# =============================================================================
class TestDatasetSplitterImpl:
    def test_split_standard(self):
        df = pd.DataFrame({"a": range(100), "label": ["A", "B"] * 50})
        splitter = DatasetSplitterImpl()
        train, val, test = splitter.split(df, "label", test_size=0.2, val_size=0.1)
        assert len(train) > len(val) > 0
        assert len(test) > len(val) > 0
        assert len(train) > len(test) > 0
        assert len(train) + len(val) + len(test) == len(df)

    def test_split_small_dataset(self):
        df = pd.DataFrame({"a": [1, 2, 3], "label": ["A", "B", "A"]})
        splitter = DatasetSplitterImpl()
        train, val, test = splitter.split(df, "label")
        assert len(train) >= 1

    def test_split_no_stratify(self):
        df = pd.DataFrame({"a": range(50), "label": ["A", "B"] * 25})
        splitter = DatasetSplitterImpl()
        train, val, test = splitter.split(df, "label", stratify=False)
        assert len(train) > 0

    def test_split_random_state(self):
        df = pd.DataFrame({"a": range(100), "label": ["A", "B"] * 50})
        splitter = DatasetSplitterImpl()
        train1, val1, test1 = splitter.split(df, "label", random_state=42)
        train2, val2, test2 = splitter.split(df, "label", random_state=42)
        assert train1.equals(train2)
        assert val1.equals(val2)
        assert test1.equals(test2)


# =============================================================================
# DataLineageTrackerImpl Tests
# =============================================================================
class TestDataLineageTrackerImpl:
    def test_log_transformation(self):
        tracker = DataLineageTrackerImpl()
        tracker.log_transformation("test_op", {"param": "value"})
        assert len(tracker.get_lineage()) == 1

    def test_get_lineage_returns_copy(self):
        tracker = DataLineageTrackerImpl()
        tracker.log_transformation("op1", {})
        lineage = tracker.get_lineage()
        lineage.append({"test": True})
        assert len(tracker.get_lineage()) == 1

    def test_get_summary_empty(self):
        tracker = DataLineageTrackerImpl()
        summary = tracker.get_summary()
        assert summary["total_transformations"] == 0

    def test_get_summary(self):
        tracker = DataLineageTrackerImpl()
        tracker.log_transformation("op1", {})
        tracker.log_transformation("op2", {})
        summary = tracker.get_summary()
        assert summary["total_transformations"] == 2
        assert summary["started_at"] is not None
        assert summary["completed_at"] is not None


# =============================================================================
# DatasetManager Integration Tests
# =============================================================================
class TestDatasetManager:
    def test_initialization(self):
        manager = DatasetManager()
        assert manager.lineage is not None
        assert manager.discoverer is not None
        assert manager.loader_factory is not None
        assert manager.validator is not None
        assert manager.normalizer is not None
        assert manager.deduper is not None
        assert manager.missing_handler is not None
        assert manager.outlier_detector is not None
        assert manager.balancer is not None
        assert manager.fingerprinter is not None
        assert manager.versioner is not None
        assert manager.splitter is not None
        assert manager.stat_reporter is not None

    def test_remove_duplicates(self):
        df = pd.DataFrame({"a": [1, 2, 2, 3]})
        manager = DatasetManager()
        manager.deduper.threshold = 1.0
        result = manager.remove_duplicates(df)
        assert len(result) == 3

    def test_fingerprint_dataset(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        manager = DatasetManager()
        fp = manager.fingerprint_dataset(df)
        assert isinstance(fp, str) and len(fp) > 0

    def test_get_lineage(self):
        manager = DatasetManager()
        lineage = manager.get_lineage()
        assert isinstance(lineage, list)

    def test_normalize_labels(self):
        df = pd.DataFrame({"label": ["scam", "safe"]})
        manager = DatasetManager()
        result = manager.normalize_labels(df, "label")
        assert list(result["label"]) == ["scam", "safe"]
