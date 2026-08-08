"""
Load and stress tests for the API.
Tests: concurrent requests, throughput, response times, resource usage.
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


class TestConcurrentLoad:
    def test_sequential_health_checks(self):
        """Baseline: sequential health check performance."""
        client = TestClient(app)
        times = []
        for _ in range(50):
            start = time.time()
            resp = client.get("/health")
            times.append(time.time() - start)
            assert resp.status_code == 200

        avg = sum(times) / len(times)
        assert avg < 0.5, f"Average health check too slow: {avg:.3f}s"

    def test_sequential_predictions(self):
        """Baseline: sequential prediction performance."""
        client = TestClient(app)
        times = []
        for _ in range(20):
            start = time.time()
            resp = client.post("/predict", json={
                "text": "This is a test message for load testing purposes",
                "source": "load_test"
            })
            times.append(time.time() - start)
            assert resp.status_code == 200

        avg = sum(times) / len(times)
        assert avg < 1.0, f"Average prediction too slow: {avg:.3f}s"

    def test_concurrent_health_requests(self):
        """Concurrent health check throughput."""
        client = TestClient(app)

        def health_check():
            resp = client.get("/health")
            return resp.status_code == 200

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(health_check) for _ in range(100)]
            results = [f.result() for f in as_completed(futures)]

        assert all(results), "Some health checks failed"
        assert len(results) == 100

    def test_concurrent_predictions(self):
        """Concurrent prediction throughput."""
        client = TestClient(app)

        def predict():
            resp = client.post("/predict", json={
                "text": "Concurrent load test prediction",
                "source": "load_test"
            })
            return resp.status_code == 200

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(predict) for _ in range(30)]
            results = [f.result() for f in as_completed(futures)]

        success_rate = sum(results) / len(results)
        assert success_rate >= 0.9, f"Only {success_rate:.1%} success rate"

    def test_mixed_concurrent_load(self):
        """Mixed load: auth + predict + dashboard."""
        client = TestClient(app)

        def worker():
            # Signup
            client.post("/auth/signup", json={
                "email": f"load_{time.time_ns()}@test.com",
                "password": "LoadP@ss123"
            })
            # Predict
            client.post("/predict", json={"text": "Load test", "source": "load"})
            # Dashboard
            client.get("/dashboard")

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker) for _ in range(10)]
            for f in as_completed(futures):
                f.result()  # Will raise if failed


class TestResponseTime:
    def test_fast_health_response(self):
        client = TestClient(app)
        start = time.time()
        client.get("/health")
        duration = time.time() - start
        assert duration < 2.0, f"Health endpoint too slow: {duration:.3f}s"

    def test_fast_prediction_response(self):
        client = TestClient(app)
        start = time.time()
        client.post("/predict", json={
            "text": "Fast response test",
            "source": "test"
        })
        duration = time.time() - start
        assert duration < 3.0, f"Prediction too slow: {duration:.3f}s"

    def test_multiple_endpoints(self):
        client = TestClient(app)
        endpoints = [
            ("GET", "/health", None),
            ("GET", "/dashboard", None),
            ("GET", "/metrics", None),
        ]
        for method, path, body in endpoints:
            start = time.time()
            if method == "GET":
                client.get(path)
            duration = time.time() - start
            assert duration < 2.0, f"{path} too slow: {duration:.3f}s"


class TestStress:
    def test_high_frequency_requests(self):
        """Stress test: rapid-fire requests."""
        client = TestClient(app)
        start = time.time()
        count = 0
        while time.time() - start < 2:  # 2 second burst
            resp = client.get("/health")
            if resp.status_code == 200:
                count += 1
        assert count > 10, f"Only {count} requests in 2s"

    def test_sustained_load(self):
        """Sustained load over 5 seconds."""
        client = TestClient(app)
        start = time.time()
        count = 0
        errors = 0
        while time.time() - start < 5:
            try:
                resp = client.post("/predict", json={
                    "text": "Sustained load test",
                    "source": "stress"
                })
                if resp.status_code == 200:
                    count += 1
                else:
                    errors += 1
            except Exception:
                errors += 1

        assert count > 10, f"Only {count} successful requests in 5s"
        error_rate = errors / (count + errors) if (count + errors) > 0 else 0
        assert error_rate < 0.5, f"Error rate too high: {error_rate:.1%}"


class TestMemoryUsage:
    def test_memory_stable_under_load(self):
        """Check memory doesn't grow unbounded under load."""
        try:
            import psutil
        except ImportError:
            pytest.skip("psutil not installed")
        import os

        process = psutil.Process(os.getpid())
        mem_before = process.memory_info().rss

        client = TestClient(app)
        for _ in range(50):
            client.post("/predict", json={
                "text": "Memory test " + "x" * 1000,
                "source": "memory_test"
            })

        mem_after = process.memory_info().rss
        growth = (mem_after - mem_before) / 1024 / 1024  # MB
        assert growth < 100, f"Memory grew by {growth:.1f}MB (possible leak)"

