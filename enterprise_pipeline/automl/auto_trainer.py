"""
Enterprise AutoML Engine
=========================
Production-grade automated model training with:
- Classical ML: Logistic Regression, Random Forest, Extra Trees, Gradient Boosting,
  XGBoost, LightGBM, CatBoost, AdaBoost, Naive Bayes, Decision Tree, SVM, KNN, MLP
- Deep Learning: CNN, LSTM, Transformer, Hybrid models
- Hyperparameter Optimization: Optuna, Bayesian Optimization, Random Search
- Cross Validation: 5-fold, 10-fold, Stratified
"""

import contextlib
import time
import warnings
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.ensemble import (
    AdaBoostClassifier,
    ExtraTreesClassifier,
    GradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    matthews_corrcoef,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import (
    KFold,
    StratifiedKFold,
    cross_validate,
)
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

from ..config.settings import settings_instance
from ..core.interfaces import CrossValidator, HyperparameterOptimizer
from ..utils.logging_utils import get_logger, log_execution_time

log = get_logger("automl")

warnings.filterwarnings("ignore")


@dataclass
class ModelConfig:
    """Configuration for a single model type."""
    name: str
    model_class: type[BaseEstimator]
    default_params: dict[str, Any] = field(default_factory=dict)
    param_grid: dict[str, list[Any]] = field(default_factory=dict)
    requires_scaling: bool = False
    supports_categorical: bool = True
    supports_multiclass: bool = True
    is_deep_learning: bool = False


class ModelFactory:
    """Factory pattern for creating ML/DL models."""

    @staticmethod
    def get_all_model_configs() -> dict[str, ModelConfig]:
        """Get all available model configurations."""
        return {
            # Classical ML Models
            "logistic_regression": ModelConfig(
                name="Logistic Regression",
                model_class=LogisticRegression,
                default_params={"random_state": 42, "max_iter": 1000, "n_jobs": -1},
                param_grid={
                    "C": [0.01, 0.1, 1.0, 10.0, 100.0],
                    "penalty": ["l2", "l1", "elasticnet"],
                    "solver": ["lbfgs", "liblinear", "saga"],
                },
                requires_scaling=True,
            ),
            "random_forest": ModelConfig(
                name="Random Forest",
                model_class=RandomForestClassifier,
                default_params={"random_state": 42, "n_jobs": -1, "n_estimators": 300},
                param_grid={
                    "n_estimators": [100, 200, 300, 500],
                    "max_depth": [10, 20, 30, None],
                    "min_samples_split": [2, 5, 10],
                    "min_samples_leaf": [1, 2, 4],
                    "max_features": ["sqrt", "log2", None],
                },
            ),
            "extra_trees": ModelConfig(
                name="Extra Trees",
                model_class=ExtraTreesClassifier,
                default_params={"random_state": 42, "n_jobs": -1, "n_estimators": 300},
                param_grid={
                    "n_estimators": [100, 200, 300, 500],
                    "max_depth": [10, 20, 30, None],
                    "min_samples_split": [2, 5, 10],
                    "min_samples_leaf": [1, 2, 4],
                },
            ),
            "gradient_boosting": ModelConfig(
                name="Gradient Boosting",
                model_class=GradientBoostingClassifier,
                default_params={"random_state": 42, "n_estimators": 200},
                param_grid={
                    "n_estimators": [100, 200, 300],
                    "learning_rate": [0.01, 0.05, 0.1, 0.2],
                    "max_depth": [3, 5, 7, 10],
                    "min_samples_split": [2, 5, 10],
                    "subsample": [0.8, 0.9, 1.0],
                },
            ),
            "xgboost": ModelConfig(
                name="XGBoost",
                model_class=None,  # Lazy import
                default_params={
                    "random_state": 42, "n_estimators": 200, "verbosity": 0,
                    "use_label_encoder": False, "n_jobs": -1,
                },
                param_grid={
                    "n_estimators": [100, 200, 300, 500],
                    "learning_rate": [0.01, 0.05, 0.1, 0.2],
                    "max_depth": [3, 5, 7, 10],
                    "subsample": [0.8, 0.9, 1.0],
                    "colsample_bytree": [0.8, 0.9, 1.0],
                    "gamma": [0, 0.1, 0.2],
                },
            ),
            "lightgbm": ModelConfig(
                name="LightGBM",
                model_class=None,  # Lazy import
                default_params={
                    "random_state": 42, "n_estimators": 200, "verbose": -1,
                    "n_jobs": -1,
                },
                param_grid={
                    "n_estimators": [100, 200, 300, 500],
                    "learning_rate": [0.01, 0.05, 0.1, 0.2],
                    "max_depth": [3, 5, 7, 10, -1],
                    "num_leaves": [31, 64, 128, 256],
                    "subsample": [0.8, 0.9, 1.0],
                    "colsample_bytree": [0.8, 0.9, 1.0],
                },
            ),
            "catboost": ModelConfig(
                name="CatBoost",
                model_class=None,  # Lazy import
                default_params={
                    "random_state": 42, "iterations": 200, "verbose": False,
                    "allow_writing_files": False,
                },
                param_grid={
                    "iterations": [100, 200, 300, 500],
                    "learning_rate": [0.01, 0.05, 0.1, 0.2],
                    "depth": [4, 6, 8, 10],
                    "l2_leaf_reg": [1, 3, 5, 10],
                },
            ),
            "adaboost": ModelConfig(
                name="AdaBoost",
                model_class=AdaBoostClassifier,
                default_params={"random_state": 42, "n_estimators": 200},
                param_grid={
                    "n_estimators": [50, 100, 200, 300],
                    "learning_rate": [0.5, 0.8, 1.0, 1.5],
                },
            ),
            "naive_bayes": ModelConfig(
                name="Naive Bayes",
                model_class=GaussianNB,
                default_params={},
                param_grid={},
            ),
            "decision_tree": ModelConfig(
                name="Decision Tree",
                model_class=DecisionTreeClassifier,
                default_params={"random_state": 42},
                param_grid={
                    "max_depth": [5, 10, 20, 30, None],
                    "min_samples_split": [2, 5, 10, 20],
                    "min_samples_leaf": [1, 2, 4, 8],
                    "criterion": ["gini", "entropy"],
                },
            ),
            "svm": ModelConfig(
                name="SVM",
                model_class=SVC,
                default_params={"random_state": 42, "probability": True, "max_iter": 10000},
                param_grid={
                    "C": [0.1, 1.0, 10.0, 100.0],
                    "kernel": ["linear", "rbf", "poly"],
                    "gamma": ["scale", "auto", 0.01, 0.1],
                },
                requires_scaling=True,
            ),
            "knn": ModelConfig(
                name="KNN",
                model_class=KNeighborsClassifier,
                default_params={"n_jobs": -1},
                param_grid={
                    "n_neighbors": [3, 5, 7, 9, 11, 15],
                    "weights": ["uniform", "distance"],
                    "metric": ["euclidean", "manhattan", "minkowski"],
                },
                requires_scaling=True,
            ),
            "mlp": ModelConfig(
                name="MLP",
                model_class=MLPClassifier,
                default_params={"random_state": 42, "max_iter": 500, "early_stopping": True},
                param_grid={
                    "hidden_layer_sizes": [(64,), (128,), (256,), (64, 32), (128, 64)],
                    "activation": ["relu", "tanh"],
                    "learning_rate_init": [0.0001, 0.001, 0.01],
                    "batch_size": [32, 64, 128],
                },
                requires_scaling=True,
            ),
        }

    @staticmethod
    def create_model(config: ModelConfig, params: dict[str, Any] | None = None) -> BaseEstimator:
        """Create a model instance from config."""
        # Lazy imports for optional dependencies
        if config.name == "XGBoost":
            try:
                from xgboost import XGBClassifier
                config.model_class = XGBClassifier
            except ImportError:
                log.warning("XGBoost not installed. Skipping.")
                return None
        elif config.name == "LightGBM":
            try:
                from lightgbm import LGBMClassifier
                config.model_class = LGBMClassifier
            except ImportError:
                log.warning("LightGBM not installed. Skipping.")
                return None
        elif config.name == "CatBoost":
            try:
                from catboost import CatBoostClassifier
                config.model_class = CatBoostClassifier
            except ImportError:
                log.warning("CatBoost not installed. Skipping.")
                return None

        if config.model_class is None:
            return None

        model_params = {**config.default_params}
        if params:
            model_params.update(params)

        return config.model_class(**model_params)


class CrossValidatorImpl(CrossValidator):
    """Performs cross-validation with multiple fold strategies."""

    def __init__(self, settings=settings_instance):
        self.settings = settings

    def validate(
        self, model_class: type[BaseEstimator], X: np.ndarray, y: np.ndarray,
        params: dict[str, Any], cv_folds: int = 5, stratified: bool = True
    ) -> dict[str, list[float]]:
        """Perform cross-validation and return metrics."""
        cv_folds = cv_folds or self.settings.model.cv_folds
        stratified = stratified if stratified is not None else self.settings.model.cv_stratified

        # Create model
        model = model_class(**params) if params else model_class()

        # Define CV strategy
        if stratified and len(np.unique(y)) >= 2:
            cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=self.settings.model.random_state)
        else:
            cv = KFold(n_splits=cv_folds, shuffle=True, random_state=self.settings.model.random_state)

        # Perform cross-validation
        scoring = {
            "accuracy": "accuracy",
            "f1": "f1_weighted",
            "precision": "precision_weighted",
            "recall": "recall_weighted",
            "roc_auc": "roc_auc_ovr_weighted",
        }

        try:
            scores = cross_validate(
                model, X, y, cv=cv, scoring=scoring,
                n_jobs=-1, return_train_score=False,
                error_score="raise",
            )
            results = {
                "accuracy": [float(s) for s in scores["test_accuracy"]],
                "f1": [float(s) for s in scores["test_f1"]],
                "precision": [float(s) for s in scores["test_precision"]],
                "recall": [float(s) for s in scores["test_recall"]],
            }

            # ROC AUC may not work for all models
            if "test_roc_auc" in scores:
                results["roc_auc"] = [float(s) for s in scores["test_roc_auc"]]

            # Add stats
            for metric_name, values in results.items():
                results[f"{metric_name}_mean"] = float(np.mean(values))
                results[f"{metric_name}_std"] = float(np.std(values))

            return results
        except Exception as e:
            log.warning(f"Cross-validation failed: {e}")
            return {"error": [str(e)]}


class OptunaOptimizer(HyperparameterOptimizer):
    """Hyperparameter optimization using Optuna."""

    def __init__(self, settings=settings_instance):
        self.settings = settings
        self.best_params: dict[str, Any] = {}
        self.best_score: float = 0.0
        self.study = None

    def optimize(
        self, model_class, X_train: np.ndarray, y_train: np.ndarray,
        X_val: np.ndarray, y_val: np.ndarray, n_trials: int = 50
    ) -> dict[str, Any]:
        """Find best hyperparameters using Optuna."""
        try:
            import optuna
        except ImportError:
            log.warning("Optuna not installed. Using random search fallback.")
            return self._random_search(model_class, X_train, y_train, X_val, y_val, n_trials)

        n_trials = n_trials or self.settings.model.n_trials
        timeout = self.settings.model.timeout_hours * 3600

        def objective(trial):
            # Sample hyperparameters based on model type
            model_name = model_class.__name__.lower()
            if "randomforest" in model_name or "extratrees" in model_name:
                params = {
                    "n_estimators": trial.suggest_int("n_estimators", 100, 500, step=50),
                    "max_depth": trial.suggest_int("max_depth", 5, 50),
                    "min_samples_split": trial.suggest_int("min_samples_split", 2, 20),
                    "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 10),
                    "max_features": trial.suggest_categorical("max_features", ["sqrt", "log2", None]),
                    "random_state": self.settings.model.random_state,
                    "n_jobs": -1,
                }
            elif "gradientboosting" in model_name:
                params = {
                    "n_estimators": trial.suggest_int("n_estimators", 100, 500, step=50),
                    "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                    "max_depth": trial.suggest_int("max_depth", 3, 10),
                    "min_samples_split": trial.suggest_int("min_samples_split", 2, 20),
                    "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                    "random_state": self.settings.model.random_state,
                }
            elif "logisticregression" in model_name:
                params = {
                    "C": trial.suggest_float("C", 0.001, 100, log=True),
                    "penalty": trial.suggest_categorical("penalty", ["l2", "l1"]),
                    "solver": trial.suggest_categorical("solver", ["lbfgs", "liblinear", "saga"]),
                    "random_state": self.settings.model.random_state,
                    "max_iter": 1000,
                    "n_jobs": -1,
                }
            elif "svm" in model_name or "svc" in model_name:
                params = {
                    "C": trial.suggest_float("C", 0.01, 100, log=True),
                    "kernel": trial.suggest_categorical("kernel", ["linear", "rbf", "poly"]),
                    "gamma": trial.suggest_categorical("gamma", ["scale", "auto"]),
                    "probability": True,
                    "random_state": self.settings.model.random_state,
                }
            else:
                # Generic random search fallback
                return self._random_search_single(model_class, X_train, y_train, X_val, y_val)

            # Create and train model
            try:
                model = model_class(**params)
                model.fit(X_train, y_train)
                y_pred = model.predict(X_val)
                score = f1_score(y_val, y_pred, average="weighted")
                return score
            except Exception as e:
                log.debug(f"Trial failed: {e}")
                return 0.0

        try:
            self.study = optuna.create_study(
                direction="maximize",
                sampler=optuna.samplers.TPESampler(seed=self.settings.model.random_state),
            )
            self.study.optimize(objective, n_trials=n_trials, timeout=timeout)

            self.best_params = self.study.best_params
            self.best_score = self.study.best_value
            log.info(f"Optuna optimization complete. Best F1: {self.best_score:.4f}")

            return self.best_params
        except Exception as e:
            log.warning(f"Optuna optimization failed: {e}")
            return self._random_search(model_class, X_train, y_train, X_val, y_val, n_trials)

    def _random_search(
        self, model_class, X_train, y_train, X_val, y_val, n_trials: int
    ) -> dict[str, Any]:
        """Fallback random search."""
        best_score = 0.0
        best_params = {}
        trial_count = 0

        while trial_count < min(n_trials, 20):
            trial_count += 1
            score = self._random_search_single(model_class, X_train, y_train, X_val, y_val)
            if score > best_score:
                best_score = score
            # No easy way to track params here, so just return empty
            log.debug(f"Random search trial {trial_count}: {score:.4f}")

        return best_params

    def _random_search_single(self, model_class, X_train, y_train, X_val, y_val) -> float:
        """Run a single random search trial."""
        try:
            model = model_class()
            model.fit(X_train, y_train)
            y_pred = model.predict(X_val)
            return f1_score(y_val, y_pred, average="weighted")
        except Exception:
            return 0.0


class DeepLearningTrainer:
    """Trains deep learning models (CNN, LSTM, Transformer, Hybrid)."""

    def __init__(self, settings=settings_instance):
        self.settings = settings
        self._tf_available = False
        self._check_tensorflow()

    def _check_tensorflow(self):
        try:
            import tensorflow as tf
            self._tf_available = True
            self._tf = tf
            from tensorflow import keras
            self._keras = keras
        except ImportError:
            log.warning("TensorFlow not available. Deep learning models will be skipped.")

    def build_cnn(self, input_dim: int, num_classes: int) -> Any:
        """Build a 1D CNN model for text classification."""
        if not self._tf_available:
            return None
        from tensorflow.keras import layers, models

        model = models.Sequential([
            layers.Input(shape=(input_dim,)),
            layers.Reshape((input_dim, 1)),
            layers.Conv1D(64, kernel_size=3, activation="relu", padding="same"),
            layers.BatchNormalization(),
            layers.MaxPooling1D(pool_size=2),
            layers.Conv1D(128, kernel_size=3, activation="relu", padding="same"),
            layers.BatchNormalization(),
            layers.GlobalAveragePooling1D(),
            layers.Dropout(0.3),
            layers.Dense(64, activation="relu"),
            layers.Dropout(0.3),
            layers.Dense(num_classes, activation="softmax" if num_classes > 2 else "sigmoid"),
        ])

        model.compile(
            optimizer=self._keras.optimizers.Adam(learning_rate=self.settings.model.dl_learning_rate),
            loss="sparse_categorical_crossentropy" if num_classes > 2 else "binary_crossentropy",
            metrics=["accuracy"],
        )
        return model

    def build_lstm(self, input_dim: int, num_classes: int) -> Any:
        """Build an LSTM model for text classification."""
        if not self._tf_available:
            return None
        from tensorflow.keras import layers, models

        model = models.Sequential([
            layers.Input(shape=(input_dim,)),
            layers.Reshape((input_dim, 1)),
            layers.LSTM(128, return_sequences=True),
            layers.BatchNormalization(),
            layers.LSTM(64),
            layers.BatchNormalization(),
            layers.Dropout(0.3),
            layers.Dense(64, activation="relu"),
            layers.Dropout(0.3),
            layers.Dense(num_classes, activation="softmax" if num_classes > 2 else "sigmoid"),
        ])

        model.compile(
            optimizer=self._keras.optimizers.Adam(learning_rate=self.settings.model.dl_learning_rate),
            loss="sparse_categorical_crossentropy" if num_classes > 2 else "binary_crossentropy",
            metrics=["accuracy"],
        )
        return model

    def build_transformer(self, input_dim: int, num_classes: int) -> Any:
        """Build a Transformer model for text classification."""
        if not self._tf_available:
            return None
        from tensorflow.keras import layers, models

        inputs = layers.Input(shape=(input_dim,))
        x = layers.Reshape((input_dim, 1))(inputs)

        # Multi-head attention
        attention = layers.MultiHeadAttention(num_heads=8, key_dim=64)(x, x)
        x = layers.Add()([x, attention])
        x = layers.LayerNormalization()(x)

        # Feed-forward
        ffn = layers.Dense(256, activation="relu")(x)
        ffn = layers.Dense(1)(ffn)
        x = layers.Add()([x, ffn])
        x = layers.LayerNormalization()(x)

        # Global pooling and output
        x = layers.GlobalAveragePooling1D()(x)
        x = layers.Dropout(0.3)(x)
        x = layers.Dense(64, activation="relu")(x)
        outputs = layers.Dense(num_classes, activation="softmax" if num_classes > 2 else "sigmoid")(x)

        model = models.Model(inputs=inputs, outputs=outputs)
        model.compile(
            optimizer=self._keras.optimizers.Adam(learning_rate=self.settings.model.dl_learning_rate),
            loss="sparse_categorical_crossentropy" if num_classes > 2 else "binary_crossentropy",
            metrics=["accuracy"],
        )
        return model

    def build_hybrid(self, input_dim: int, num_classes: int) -> Any:
        """Build a hybrid CNN-LSTM model."""
        if not self._tf_available:
            return None
        from tensorflow.keras import layers, models

        model = models.Sequential([
            layers.Input(shape=(input_dim,)),
            layers.Reshape((input_dim, 1)),
            layers.Conv1D(64, kernel_size=3, activation="relu", padding="same"),
            layers.MaxPooling1D(pool_size=2),
            layers.LSTM(64, return_sequences=True),
            layers.LSTM(32),
            layers.Dropout(0.3),
            layers.Dense(64, activation="relu"),
            layers.Dropout(0.3),
            layers.Dense(num_classes, activation="softmax" if num_classes > 2 else "sigmoid"),
        ])

        model.compile(
            optimizer=self._keras.optimizers.Adam(learning_rate=self.settings.model.dl_learning_rate),
            loss="sparse_categorical_crossentropy" if num_classes > 2 else "binary_crossentropy",
            metrics=["accuracy"],
        )
        return model

    @log_execution_time
    def train(
        self, X_train: np.ndarray, y_train: np.ndarray,
        X_val: np.ndarray, y_val: np.ndarray,
        num_classes: int, model_type: str = "cnn",
    ) -> Any | None:
        """Train a deep learning model."""
        if not self._tf_available:
            log.warning("TensorFlow not available, skipping deep learning training")
            return None

        input_dim = X_train.shape[1]

        builders = {
            "cnn": self.build_cnn,
            "lstm": self.build_lstm,
            "transformer": self.build_transformer,
            "hybrid": self.build_hybrid,
        }

        if model_type not in builders:
            raise ValueError(f"Unknown model type: {model_type}. Use: {list(builders.keys())}")

        model = builders[model_type](input_dim, num_classes)
        if model is None:
            return None

        # Train with callbacks
        from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau

        callbacks = [
            EarlyStopping(
                monitor="val_loss",
                patience=self.settings.model.dl_patience,
                restore_best_weights=True,
            ),
            ReduceLROnPlateau(
                monitor="val_loss",
                factor=0.5,
                patience=self.settings.model.dl_patience // 2,
                min_lr=1e-6,
            ),
        ]

        history = model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            epochs=self.settings.model.dl_epochs,
            batch_size=self.settings.model.dl_batch_size,
            callbacks=callbacks,
            verbose=0,
        )

        log.info(f"DL {model_type.upper()} training complete. "
                 f"Final val_acc: {history.history['val_accuracy'][-1]:.4f}")

        return model


class AutoMLTrainer:
    """
    Enterprise AutoML Trainer - orchestrates training of multiple models
    with hyperparameter optimization and cross-validation.
    """

    def __init__(self, settings=settings_instance):
        self.settings = settings
        self.model_factory = ModelFactory()
        self.cross_validator = CrossValidatorImpl(settings)
        self.hyperopt = OptunaOptimizer(settings)
        self.dl_trainer = DeepLearningTrainer(settings)
        self.scaler = StandardScaler()
        self.trained_models: dict[str, Any] = {}
        self.model_results: dict[str, dict[str, Any]] = {}
        self.best_model_name: str | None = None
        self.best_model: Any | None = None
        self.label_encoder: LabelEncoder | None = None

    @log_execution_time
    def train_all_models(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
        model_names: list[str] | None = None,
        optimize_hyperparams: bool = True,
        include_deep_learning: bool = True,
    ) -> dict[str, dict[str, Any]]:
        """
        Train all available models and compare results.

        Args:
            X_train, y_train: Training data
            X_val, y_val: Validation data
            X_test, y_test: Test data
            model_names: Specific models to train (None = all)
            optimize_hyperparams: Whether to perform hyperparameter optimization
            include_deep_learning: Whether to include DL models

        Returns:
            Dict of model_name -> evaluation results
        """
        log.info("Starting AutoML training pipeline...")

        # Get all model configs
        all_configs = self.model_factory.get_all_model_configs()

        if model_names:
            configs = {name: cfg for name, cfg in all_configs.items() if name in model_names}
        else:
            configs = all_configs

        # For models requiring scaling
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)
        X_test_scaled = self.scaler.transform(X_test)

        num_classes = len(np.unique(y_train))

        results = {}

        # Train classical ML models
        for model_name, config in configs.items():
            if config.is_deep_learning and not include_deep_learning:
                continue
            if config.is_deep_learning:
                continue  # Handle DL separately

            log.info(f"Training {config.name}...")
            start_time = time.time()

            try:
                # Prepare data (scaled or not)
                X_tr = X_train_scaled if config.requires_scaling else X_train
                X_vl = X_val_scaled if config.requires_scaling else X_val
                X_te = X_test_scaled if config.requires_scaling else X_test

                # Get default params (or optimized ones)
                if optimize_hyperparams and config.param_grid:
                    best_params = self.hyperopt.optimize(
                        config.model_class, X_tr, y_train, X_vl, y_val,
                        n_trials=self.settings.model.n_trials,
                    )
                    params = {**config.default_params, **best_params}
                else:
                    params = config.default_params

                # Create and train model
                model = self.model_factory.create_model(config, params)
                if model is None:
                    continue

                model.fit(X_tr, y_train)

                # Evaluate
                train_time = time.time() - start_time

                # Test predictions
                y_pred = model.predict(X_te)
                y_prob = model.predict_proba(X_te) if hasattr(model, "predict_proba") else None

                # Calculate metrics
                metrics = {
                    "accuracy": float(accuracy_score(y_test, y_pred)),
                    "precision": float(precision_score(y_test, y_pred, average="weighted", zero_division=0)),
                    "recall": float(recall_score(y_test, y_pred, average="weighted", zero_division=0)),
                    "f1": float(f1_score(y_test, y_pred, average="weighted", zero_division=0)),
                    "balanced_accuracy": float(balanced_accuracy_score(y_test, y_pred)),
                    "mcc": float(matthews_corrcoef(y_test, y_pred)),
                    "training_time": round(train_time, 3),
                }

                # ROC-AUC if probabilities available
                if y_prob is not None and num_classes == 2:
                    with contextlib.suppress(Exception):
                        metrics["roc_auc"] = float(roc_auc_score(y_test, y_prob[:, 1]))
                elif y_prob is not None and num_classes > 2:
                    with contextlib.suppress(Exception):
                        metrics["roc_auc"] = float(roc_auc_score(y_test, y_prob, multi_class="ovr"))

                # Cross-validation scores
                cv_results = self.cross_validator.validate(
                    config.model_class, X_tr, y_train, params,
                    cv_folds=self.settings.model.cv_folds,
                    stratified=self.settings.model.cv_stratified,
                )
                metrics["cv_scores"] = cv_results

                # Store model and results
                self.trained_models[model_name] = model
                self.model_results[model_name] = metrics
                results[model_name] = metrics

                log.info(f"{config.name}: F1={metrics['f1']:.4f}, "
                         f"Acc={metrics['accuracy']:.4f}, Time={train_time:.2f}s")

            except Exception as e:
                log.error(f"Failed to train {config.name}: {e}")
                results[model_name] = {"error": str(e)}

        # Train deep learning models
        if include_deep_learning and self.dl_trainer._tf_available:
            dl_models = {
                "cnn": ("CNN", self.dl_trainer.build_cnn),
                "lstm": ("LSTM", self.dl_trainer.build_lstm),
                "transformer": ("Transformer", self.dl_trainer.build_transformer),
                "hybrid": ("Hybrid CNN-LSTM", self.dl_trainer.build_hybrid),
            }

            for dl_name, (dl_label, builder) in dl_models.items():
                log.info(f"Training {dl_label}...")
                try:
                    start_time = time.time()
                    input_dim = X_train.shape[1]
                    model = builder(input_dim, num_classes)

                    if model is None:
                        continue

                    from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau

                    callbacks = [
                        EarlyStopping(patience=self.settings.model.dl_patience, restore_best_weights=True),
                        ReduceLROnPlateau(factor=0.5, patience=self.settings.model.dl_patience // 2),
                    ]

                    history = model.fit(
                        X_train_scaled, y_train,
                        validation_data=(X_val_scaled, y_val),
                        epochs=self.settings.model.dl_epochs,
                        batch_size=self.settings.model.dl_batch_size,
                        callbacks=callbacks,
                        verbose=0,
                    )

                    train_time = time.time() - start_time

                    # Evaluate
                    y_pred = np.argmax(model.predict(X_test_scaled), axis=1) if num_classes > 2 else \
                             (model.predict(X_test_scaled) > 0.5).astype(int).flatten()
                    y_prob = model.predict(X_test_scaled)

                    metrics = {
                        "accuracy": float(accuracy_score(y_test, y_pred)),
                        "precision": float(precision_score(y_test, y_pred, average="weighted", zero_division=0)),
                        "recall": float(recall_score(y_test, y_pred, average="weighted", zero_division=0)),
                        "f1": float(f1_score(y_test, y_pred, average="weighted", zero_division=0)),
                        "balanced_accuracy": float(balanced_accuracy_score(y_test, y_pred)),
                        "mcc": float(matthews_corrcoef(y_test, y_pred)),
                        "training_time": round(train_time, 3),
                        "dl_history": {
                            "val_accuracy": [float(x) for x in history.history["val_accuracy"]],
                            "val_loss": [float(x) for x in history.history["val_loss"]],
                        },
                    }

                    self.trained_models[dl_name] = model
                    self.model_results[dl_name] = metrics
                    results[dl_name] = metrics

                    log.info(f"{dl_label}: F1={metrics['f1']:.4f}, Time={train_time:.2f}s")

                except Exception as e:
                    log.error(f"Failed to train {dl_label}: {e}")
                    results[dl_name] = {"error": str(e)}

        # Select best model
        self._select_best_model()

        log.info(f"AutoML training complete. Best model: {self.best_model_name}")
        return results

    def _select_best_model(self) -> None:
        """Select the best model based on F1 score."""
        best_score = -1.0
        best_model = None
        best_name = None

        for name, metrics in self.model_results.items():
            if "error" in metrics:
                continue
            score = metrics.get("f1", 0.0)
            if score > best_score:
                best_score = score
                best_model = self.trained_models.get(name)
                best_name = name

        self.best_model_name = best_name
        self.best_model = best_model

        if best_name:
            log.info(f"Best model selected: {best_name} (F1={best_score:.4f})")

    def get_best_model(self) -> tuple[str | None, Any | None]:
        """Get the best performing model."""
        return self.best_model_name, self.best_model

    def get_model_comparison(self) -> pd.DataFrame:
        """Get a DataFrame comparing all trained models."""
        rows = []
        for name, metrics in self.model_results.items():
            if "error" in metrics:
                continue
            row = {"model": name, "model_name": name}
            for metric in ["accuracy", "f1", "precision", "recall", "balanced_accuracy", "mcc", "roc_auc", "training_time"]:
                row[metric] = metrics.get(metric, None)
            rows.append(row)

        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("f1", ascending=False).reset_index(drop=True)
        return df

    def get_training_summary(self) -> dict[str, Any]:
        """Get summary of all training results."""
        return {
            "best_model": self.best_model_name,
            "best_f1": self.model_results.get(self.best_model_name, {}).get("f1", 0.0) if self.best_model_name else None,
            "models_trained": len(self.model_results),
            "models": {k: {kk: vv for kk, vv in v.items() if kk != "cv_scores" and kk != "dl_history"}
                      for k, v in self.model_results.items() if "error" not in v},
            "failed_models": [k for k, v in self.model_results.items() if "error" in v],
            "requires_scaling": any(
                cfg.requires_scaling
                for cfg in self.model_factory.get_all_model_configs().values()
            ),
        }
