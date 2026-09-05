"""
Regression tests for the prediction-path robustness fix.

The `/predict` endpoint previously used `pred_proba.index(max(pred_proba))`
which crashes with `AttributeError: 'numpy.ndarray' object has no attribute
'index'` when the real scikit-learn model (which returns a `numpy.ndarray`)
is loaded. This test suite verifies the endpoint works for both a
`numpy.ndarray`-returning model and the list-returning HeuristicModel
fallback, guards against the exact regression, and validates the model path.
"""
import os

import numpy as np
import pytest

from backend.app.core.config import MODEL_PATH
from backend.app.main import MODEL, app


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c


def _predict(client, text="Free money! Click here now", source="regression"):
    return client.post(
        "/predict",
        json={"text": text, "source": source},
    )


def test_predict_with_numpy_proba():
    """
    Simulate a scikit-learn style model whose predict_proba returns a
    numpy.ndarray. The endpoint must not crash with AttributeError.
    """
    import backend.app.main as main

    original = MODEL

    class NumpyProbaModel:
        classes_ = np.array(["safe", "suspicious", "scam"])

        def predict_proba(self, texts):
            return np.array([[0.10, 0.15, 0.75]] * len(texts))

        def predict(self, texts):
            return ["scam"] * len(texts)

    main.MODEL = NumpyProbaModel()
    try:
        from fastapi.testclient import TestClient
        with TestClient(app) as c:
            resp = c.post("/predict", json={
                "text": "Urgent verify your bank account",
                "source": "regression",
            })
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["label"] == "scam"
            assert 0.0 <= body["confidence"] <= 1.0
    finally:
        main.MODEL = original


def test_predict_with_python_list_proba():
    """
    The HeuristicModel fallback returns Python lists. Ensure that path still
    works (no regression from the numpy fix).
    """
    import backend.app.main as main

    original = MODEL

    class ListProbaModel:
        classes_ = ["safe", "suspicious", "scam"]

        def predict_proba(self, texts):
            return [[0.10, 0.15, 0.75] for _ in texts]

        def predict(self, texts):
            return ["scam"] * len(texts)

    main.MODEL = ListProbaModel()
    try:
        from fastapi.testclient import TestClient
        with TestClient(app) as c:
            resp = c.post("/predict", json={
                "text": "Urgent verify your bank account",
                "source": "regression",
            })
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["label"] == "scam"
            assert 0.0 <= body["confidence"] <= 1.0
    finally:
        main.MODEL = original


def test_model_path_points_to_existing_artifact():
    """
    The authoritative trained artifact is models/exports/best_model.pkl (or a
    similarly registered path). Verify MODEL_PATH resolves to a real file so
    the real model is loaded (not the heuristic fallback) in local dev/tests.
    """
    assert os.path.exists(MODEL_PATH), (
        f"MODEL_PATH={MODEL_PATH} does not exist. The real model will not load "
        "and the heuristic fallback will be used."
    )


def test_predict_returns_valid_contract(client):
    """Basic contract check on the live prediction endpoint."""
    resp = _predict(client)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "label" in body
    assert "confidence" in body
    assert "explanation" in body
    assert isinstance(body["label"], str)
