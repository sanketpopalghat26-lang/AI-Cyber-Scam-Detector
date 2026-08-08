"""
Enterprise Experiment Tracking
================================
Production-grade experiment tracking with MLflow integration.
Tracks:
- Parameters, Metrics, Artifacts, Models
- Dataset version, Git commit
- Training time, Memory, CPU, GPU usage
- Resource monitoring
"""

import json
import platform
import subprocess
import time
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from ..config.settings import settings_instance
from ..core.interfaces import ExperimentTracker
from ..utils.logging_utils import get_logger

log = get_logger("experiment_tracking")


class ResourceMonitor:
    """Monitors system resources during training."""

    def __init__(self):
        self.cpu_usage: list[float] = []
        self.memory_usage: list[float] = []
        self.gpu_usage: list[float] = []
        self.start_time: float | None = None
        self._monitoring = False

    def start(self) -> None:
        """Start resource monitoring."""
        self.start_time = time.time()
        self._monitoring = True
        log.debug("Resource monitoring started")

    def stop(self) -> dict[str, Any]:
        """Stop monitoring and return resource stats."""
        self._monitoring = False
        elapsed = time.time() - (self.start_time or time.time())

        stats = {
            "elapsed_seconds": round(elapsed, 2),
            "avg_cpu_percent": round(np.mean(self.cpu_usage), 2) if self.cpu_usage else None,
            "max_cpu_percent": round(max(self.cpu_usage), 2) if self.cpu_usage else None,
            "avg_memory_mb": round(np.mean(self.memory_usage), 2) if self.memory_usage else None,
            "max_memory_mb": round(max(self.memory_usage), 2) if self.memory_usage else None,
            "avg_gpu_percent": round(np.mean(self.gpu_usage), 2) if self.gpu_usage else None,
        }

        log.info(f"Resource usage: {stats}")
        return stats

    def poll(self) -> None:
        """Poll current resource usage."""
        try:
            import psutil

            # CPU
            self.cpu_usage.append(psutil.cpu_percent(interval=0.1))

            # Memory
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            self.memory_usage.append(memory_mb)

            # GPU (via nvidia-smi if available)
            try:
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=2,
                )
                if result.returncode == 0:
                    gpu_percent = float(result.stdout.strip().split("\n")[0])
                    self.gpu_usage.append(gpu_percent)
            except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
                pass

        except ImportError:
            pass


class GitTracker:
    """Tracks git information for reproducibility."""

    @staticmethod
    def get_git_info() -> dict[str, str]:
        """Get current git commit hash and branch."""
        info = {
            "git_commit": None,
            "git_branch": None,
            "git_dirty": None,
        }

        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=5,
                cwd=settings_instance.paths.root,
            )
            if result.returncode == 0:
                info["git_commit"] = result.stdout.strip()

            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=5,
                cwd=settings_instance.paths.root,
            )
            if result.returncode == 0:
                info["git_branch"] = result.stdout.strip()

            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, timeout=5,
                cwd=settings_instance.paths.root,
            )
            if result.returncode == 0:
                info["git_dirty"] = len(result.stdout.strip()) > 0

        except (subprocess.TimeoutExpired, FileNotFoundError):
            log.warning("Git not available or not a git repository")

        return info


class MLflowTracker(ExperimentTracker):
    """
    MLflow-based experiment tracker.
    Falls back to file-based tracking if MLflow is not available.
    """

    def __init__(self, settings=settings_instance):
        self.settings = settings
        self._mlflow = None
        self._mlflow_available = self._check_mlflow()
        self.current_run_id: str | None = None
        self.resource_monitor = ResourceMonitor()
        self.git_tracker = GitTracker()
        self._local_log: list[dict[str, Any]] = []
        self._run_start_time: float | None = None

    def _check_mlflow(self) -> bool:
        """Check if MLflow is available."""
        try:
            import mlflow
            self._mlflow = mlflow
            # Set tracking URI
            tracking_uri = self.settings.experiment.mlflow_tracking_uri
            if tracking_uri:
                mlflow.set_tracking_uri(tracking_uri)
            return True
        except ImportError:
            log.warning("MLflow not installed. Using file-based tracking.")
            return False

    def start_run(self, run_name: str | None = None) -> None:
        """Start a new experiment run."""
        self._run_start_time = time.time()

        if self._mlflow_available:
            self._mlflow.set_experiment(self.settings.experiment.experiment_name)
            run = self._mlflow.start_run(run_name=run_name)
            self.current_run_id = run.info.run_id
            log.info(f"Started MLflow run: {run.info.run_id} ({run_name})")
        else:
            self.current_run_id = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            self._local_log.append({
                "run_id": self.current_run_id,
                "run_name": run_name,
                "start_time": datetime.now(UTC).isoformat(),
                "type": "start_run",
            })
            log.info(f"Started local run: {self.current_run_id}")

        # Start resource monitoring
        self.resource_monitor.start()

    def log_params(self, params: dict[str, Any]) -> None:
        """Log parameters for current run."""
        if self._mlflow_available and self.current_run_id:
            self._mlflow.log_params(params)

        self._local_log.append({
            "run_id": self.current_run_id,
            "type": "params",
            "params": params,
            "timestamp": datetime.now(UTC).isoformat(),
        })

        log.debug(f"Logged {len(params)} params")

    def log_metrics(self, metrics: dict[str, float]) -> None:
        """Log metrics for current run."""
        if self._mlflow_available and self.current_run_id:
            for key, value in metrics.items():
                self._mlflow.log_metric(key, value)

        self._local_log.append({
            "run_id": self.current_run_id,
            "type": "metrics",
            "metrics": metrics,
            "timestamp": datetime.now(UTC).isoformat(),
        })

        log.debug(f"Logged {len(metrics)} metrics")

    def log_artifact(self, local_path: str) -> None:
        """Log an artifact file."""
        path = Path(local_path)
        if not path.exists():
            log.warning(f"Artifact not found: {local_path}")
            return

        if self._mlflow_available and self.current_run_id:
            self._mlflow.log_artifact(local_path)

        self._local_log.append({
            "run_id": self.current_run_id,
            "type": "artifact",
            "artifact_path": local_path,
            "timestamp": datetime.now(UTC).isoformat(),
        })

        log.info(f"Logged artifact: {local_path}")

    def log_model(self, model: Any, model_name: str) -> None:
        """Log a model."""
        if self._mlflow_available and self.current_run_id:
            try:
                self._mlflow.sklearn.log_model(model, model_name)
            except Exception as e:
                log.warning(f"Could not log model to MLflow: {e}")
                # Save locally
                import joblib
                model_path = self.settings.paths.models_dir / f"{model_name}.joblib"
                joblib.dump(model, model_path)
                self.log_artifact(str(model_path))
        else:
            import joblib
            model_path = self.settings.paths.models_dir / f"{model_name}.joblib"
            model_path.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(model, model_path)
            log.info(f"Saved model locally: {model_path}")

    def log_dataset_info(self, dataset_name: str, version: str, fingerprint: str) -> None:
        """Log dataset information."""
        info = {
            "dataset_name": dataset_name,
            "dataset_version": version,
            "dataset_fingerprint": fingerprint,
        }
        self.log_params(info)

    def end_run(self) -> dict[str, Any]:
        """End the current run and return summary."""
        # Stop resource monitoring
        resource_stats = self.resource_monitor.stop()

        # Log resource metrics
        self.log_metrics({
            "training_time_seconds": resource_stats.get("elapsed_seconds", 0),
            "avg_cpu_percent": resource_stats.get("avg_cpu_percent", 0) or 0,
            "max_cpu_percent": resource_stats.get("max_cpu_percent", 0) or 0,
            "avg_memory_mb": resource_stats.get("avg_memory_mb", 0) or 0,
            "max_memory_mb": resource_stats.get("max_memory_mb", 0) or 0,
        })

        # Log git info
        git_info = self.git_tracker.get_git_info()
        if any(git_info.values()):
            self.log_params(git_info)

        # End MLflow run
        if self._mlflow_available and self.current_run_id:
            self._mlflow.end_run()

        # Save local log
        run_summary = {
            "run_id": self.current_run_id,
            "duration_seconds": resource_stats.get("elapsed_seconds", 0),
            "resource_stats": resource_stats,
            "git_info": git_info,
            "end_time": datetime.now(UTC).isoformat(),
        }

        # Write local log
        log_path = self.settings.paths.artifacts_dir / f"run_{self.current_run_id}.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "w") as f:
            json.dump({
                "summary": run_summary,
                "log": self._local_log,
            }, f, indent=2, default=str)

        log.info(f"Run {self.current_run_id} completed. Duration: {resource_stats.get('elapsed_seconds', 0):.1f}s")

        self.current_run_id = None
        return run_summary

    def get_run_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent run history."""
        if self._mlflow_available:
            try:
                runs = self._mlflow.search_runs(
                    experiment_names=[self.settings.experiment.experiment_name],
                    order_by=["start_time DESC"],
                    max_results=limit,
                )
                return runs.to_dict("records") if not runs.empty else []
            except Exception as e:
                log.warning(f"Could not fetch MLflow runs: {e}")
                return []

        # From local logs
        log_files = sorted(
            Path(self.settings.paths.artifacts_dir).glob("run_*.json"),
            reverse=True,
        )[:limit]

        history = []
        for lf in log_files:
            try:
                with open(lf) as f:
                    data = json.load(f)
                    history.append(data.get("summary", {}))
            except Exception:
                pass

        return history


class ExperimentManager:
    """
    Enterprise Experiment Manager.
    Manages multiple experiment runs, tracking reproducibility.
    """

    def __init__(self, settings=settings_instance):
        self.settings = settings
        self.tracker = MLflowTracker(settings)
        self.current_experiment: str | None = None
        self.experiment_results: dict[str, dict[str, Any]] = {}

    @contextmanager
    def experiment(self, name: str) -> Generator["ExperimentManager", None, None]:
        """Context manager for running experiments."""
        self.current_experiment = name
        self.tracker.start_run(run_name=name)

        # Log system info
        self.tracker.log_params({
            "experiment_name": name,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "hostname": platform.node(),
        })

        try:
            yield self
        finally:
            run_summary = self.tracker.end_run()
            self.experiment_results[name] = run_summary
            self.current_experiment = None

    def log_training_results(
        self,
        model_name: str,
        params: dict[str, Any],
        metrics: dict[str, float],
        feature_names: list[str] | None = None,
        dataset_info: dict[str, str] | None = None,
    ) -> None:
        """Log complete training results for a model."""
        # Log parameters
        self.tracker.log_params({
            **params,
            "model_name": model_name,
        })

        # Log feature info
        if feature_names:
            self.tracker.log_params({"num_features": len(feature_names)})

        # Log dataset info
        if dataset_info:
            self.tracker.log_dataset_info(
                dataset_info.get("name", "unknown"),
                dataset_info.get("version", "unknown"),
                dataset_info.get("fingerprint", "unknown"),
            )

        # Log metrics
        self.tracker.log_metrics(metrics)

    def save_experiment_report(self, path: Path | None = None) -> Path:
        """Save experiment report to file."""
        if path is None:
            path = self.settings.paths.reports_dir / "experiment_report.json"

        path.parent.mkdir(parents=True, exist_ok=True)

        report = {
            "experiment_name": self.current_experiment,
            "results": self.experiment_results,
            "generated_at": datetime.now(UTC).isoformat(),
        }

        with open(path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        log.info(f"Experiment report saved: {path}")
        return path
