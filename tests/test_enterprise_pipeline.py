
import pandas as pd

from enterprise_pipeline.application.training_service import TrainingService
from enterprise_pipeline.config.settings import Settings


def test_training_service_runs_end_to_end(tmp_path):
    data_path = tmp_path / "synthetic.csv"
    pd.DataFrame(
        {
            "text": [
                "urgent verify your account now",
                "meeting at lunch tomorrow",
                "click here to claim your prize",
                "please review the shared report",
                "suspicious invoice payment required",
                "the weather is sunny today",
                "bank account update required immediately",
                "project deadline moved to friday",
                "your refund is approved",
                "hello team please join the call",
            ],
            "label": ["scam", "safe", "scam", "safe", "scam", "safe", "scam", "safe", "safe", "safe"],
        }
    ).to_csv(data_path, index=False)

    settings = Settings()
    settings.paths.data_dir = tmp_path
    settings.paths.datasets_dir = tmp_path / "datasets"
    settings.paths.models_dir = tmp_path / "models"
    settings.paths.registry_dir = tmp_path / "registry"
    settings.paths.reports_dir = tmp_path / "reports"
    settings.paths.artifacts_dir = tmp_path / "artifacts"
    settings.paths.mlruns_dir = tmp_path / "mlruns"
    settings.paths.logs_dir = tmp_path / "logs"

    service = TrainingService(settings=settings)
    result = service.run_pipeline(data_path=data_path, dataset_name="synthetic")

    assert result["dataset_version"]
    assert result["best_model_name"]
    assert result["best_model_metrics"]["f1_weighted"] >= 0.0
    assert (tmp_path / "registry" / "best_model.pkl").exists()
