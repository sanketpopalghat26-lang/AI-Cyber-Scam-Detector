
import pandas as pd

from enterprise_pipeline.config.settings import Settings
from enterprise_pipeline.infrastructure.dataset_repository import DatasetRepository


def test_load_and_prepare_creates_version_and_statistics(tmp_path):
    data_path = tmp_path / "sample.csv"
    pd.DataFrame({"text": ["urgent verify account", "meeting tomorrow"], "label": ["scam", "safe"]}).to_csv(data_path, index=False)

    settings = Settings()
    settings.paths.data_dir = tmp_path
    settings.paths.datasets_dir = tmp_path / "datasets"
    settings.paths.models_dir = tmp_path / "models"
    settings.paths.registry_dir = tmp_path / "registry"
    settings.paths.reports_dir = tmp_path / "reports"
    settings.paths.artifacts_dir = tmp_path / "artifacts"
    settings.paths.mlruns_dir = tmp_path / "mlruns"
    settings.paths.logs_dir = tmp_path / "logs"

    repo = DatasetRepository(settings=settings)
    prepared = repo.load_and_prepare(data_path, "sample")

    assert prepared["version"]
    assert prepared["quality_score"] >= 0
    assert "dataframe" in prepared
    assert "text" in prepared["dataframe"].columns
