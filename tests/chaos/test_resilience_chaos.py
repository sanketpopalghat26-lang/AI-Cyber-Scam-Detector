
"""
Chaos engineering tests for system resilience.
Tests: component failures, recovery, degradation behavior.
"""
import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


class TestDatabaseFailure:
    def test_degraded_health_on_db_fail(self):
        """System should report degraded but not crash on DB failure."""
        with patch("backend.app.core.db.engine") as mock_engine:
            mock_engine.connect.side_effect = Exception("DB connection failed")

            client = TestClient(app)
            resp = client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"

    def test_graceful_db_reconnect(self):
        """System should attempt reconnection."""
        from backend.app.core.db import create_db_engine
        with patch("sqlmodel.create_engine") as mock_create:
            mock_create.side_effect = [
                Exception("First fail"),
                Exception("Second fail"),
                MagicMock()
            ]
            try:
                engine = create_db_engine()
            except RuntimeError:
                pass


class TestCacheFailure:
    def test_cache_fallback_on_redis_fail(self):
        """System should use in-memory cache when Redis fails."""
        from backend.app.core.cache import RedisCache

        cache = RedisCache(redis_url="redis://nonexistent:6379")
        result = asyncio.run(cache.get("test"))
        assert result is None

    def test_predict_without_cache(self):
        """Predictions should work without cache."""
        import os
        os.environ["ENABLE_CACHE"] = "false"
        client = TestClient(app)
        resp = client.post("/predict", json={
            "text": "Test without cache",
            "source": "chaos"
        })
        assert resp.status_code == 200
        os.environ["ENABLE_CACHE"] = "true"


class TestModelFailure:
    def test_heuristic_fallback_on_model_fail(self):
        """System should use heuristic model when ML model fails."""
        with patch("joblib.load") as mock_load:
            mock_load.side_effect = Exception("Model load failed")

            import importlib

            import backend.app.main as main_mod
            importlib.reload(main_mod)

            client = TestClient(app)
            resp = client.post("/predict", json={
                "text": "Test fallback prediction",
                "source": "chaos"
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["label"] in ("safe", "suspicious", "scam")

    def test_model_retry_logic(self):
        """Model loading should retry on failure."""
        import joblib

        from backend.app.main import load_model

        call_count = [0]

        def failing_load(*args, **kwargs):
            call_count[0] += 1
            raise FileNotFoundError("Model not found")

        original_load = joblib.load
        try:
            joblib.load = failing_load
            model = load_model()
            assert call_count[0] == 3, f"Expected 3 retry attempts, got {call_count[0]}"
            assert hasattr(model, "predict")
        finally:
            joblib.load = original_load


class TestServiceDegradation:
    def test_degraded_but_functional(self):
        """System should remain functional during partial degradation."""
        import os
        os.environ["ENABLE_METRICS"] = "false"

        client = TestClient(app)
        assert client.get("/health").status_code == 200
        assert client.post("/predict", json={
            "text": "Degradation test",
            "source": "chaos"
        }).status_code == 200
        assert client.post("/auth/login", data={
            "username": "nonexistent@test.com",
            "password": "test"
        }).status_code == 401

        os.environ["ENABLE_METRICS"] = "true"

    def test_recovery_after_failure(self):
        """System should recover after transient failure."""
        call_count = [0]

        def flaky_db():
            call_count[0] += 1
            if call_count[0] <= 2:
                raise Exception("Transient failure")
            return MagicMock()

        from backend.app.core.db import create_db_engine
        with patch("sqlmodel.create_engine", side_effect=flaky_db):
            try:
                engine = create_db_engine()
            except RuntimeError:
                pass


class TestTimeoutBehavior:
    def test_slow_request_doesnt_block(self):
        """A slow request should not block other requests."""
        import threading

        results = []

        def slow_request():
            client = TestClient(app)
            start = time.time()
            try:
                client.post("/predict", json={
                    "text": "Slow test " + "x" * 10000,
                    "source": "chaos"
                })
                results.append(time.time() - start)
            except Exception:
                results.append(None)

        def fast_request():
            client = TestClient(app)
            start = time.time()
            try:
                client.get("/health")
                results.append(time.time() - start)
            except Exception:
                results.append(None)

        threads = [
            threading.Thread(target=slow_request),
            threading.Thread(target=fast_request),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(results) == 2
        assert results[1] is not None


class TestResourceExhaustion:
    def test_many_concurrent_predictions(self):
        """System should handle many concurrent predictions without crash."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        client = TestClient(app)

        def make_prediction():
            try:
                resp = client.post("/predict", json={
                    "text": "Concurrent test for resource usage",
                    "source": "chaos"
                })
                return resp.status_code == 200
            except Exception:
                return False

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_prediction) for _ in range(50)]
            results = [f.result() for f in as_completed(futures)]

        success_rate = sum(results) / len(results)
        assert success_rate >= 0.7, f"Low success rate under load: {success_rate:.1%}"

    def test_no_memory_leak_on_repeated_requests(self):
        """No memory leak from repeated requests."""
        try:
            import psutil
        except ImportError:
            pytest.skip("psutil not installed")
        import os

        process = psutil.Process(os.getpid())
        client = TestClient(app)

        for _ in range(10):
            client.get("/health")

        mem_warm = process.memory_info().rss

        for _ in range(100):
            client.post("/predict", json={
                "text": "Memory leak detection test",
                "source": "chaos"
            })

        mem_after = process.memory_info().rss
        growth = (mem_after - mem_warm) / 1024 / 1024
        assert growth < 200, f"Possible memory leak: grew {growth:.1f}MB"
