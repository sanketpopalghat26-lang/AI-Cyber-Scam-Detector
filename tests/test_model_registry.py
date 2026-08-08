
from enterprise_pipeline.config.settings import Settings
from enterprise_pipeline.domain.models import ModelArtifact
from enterprise_pipeline.infrastructure.model_registry import ModelRegistry


def test_register_and_export_best_model(tmp_path):
    settings = Settings()
    settings.paths.data_dir = tmp_path
    settings.paths.datasets_dir = tmp_path / "datasets"
    settings.paths.models_dir = tmp_path / "models"
    settings.paths.registry_dir = tmp_path / "registry"
    settings.paths.reports_dir = tmp_path / "reports"
    settings.paths.artifacts_dir = tmp_path / "artifacts"
    settings.paths.mlruns_dir = tmp_path / "mlruns"
    settings.paths.logs_dir = tmp_path / "logs"

    registry = ModelRegistry(settings=settings)
    artifact = ModelArtifact(name="demo", version="v1", model={"kind": "dummy"}, metrics={"f1": 0.9}, hyperparameters={}, dataset_version="d1", feature_set=["text"], status="registered", is_best=True)

    registered = registry.register(artifact)
    registry.promote_to_champion(registered.name, registered.version)
    export_path = registry.export_best_model(registered)

    assert export_path.exists()
    assert (tmp_path / "registry" / "best_model.pkl").exists()
