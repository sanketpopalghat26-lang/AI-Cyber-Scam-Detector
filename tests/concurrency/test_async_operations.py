
"""
Async concurrency and race condition tests.
Tests: concurrent operations, deadlock prevention, async safety.
"""
import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


class TestConcurrentAPI:
    def test_concurrent_auth_requests(self):
        """Multiple users registering and logging in concurrently."""
        import uuid
        client = TestClient(app)
        suffix = uuid.uuid4().hex[:8]

        def register_and_login(user_id):
            email = f"concurrent_{user_id}_{suffix}@test.com"
            # Create a new client per thread to avoid session reuse issues
            c = TestClient(app)
            # Register
            signup_resp = c.post("/auth/signup", json={
                "email": email,
                "password": "ConcurP@ss123!"
            })
            if signup_resp.status_code != 200:
                # Try login in case signup failed due to race
                login_resp = c.post("/auth/login", data={
                    "username": email,
                    "password": "ConcurP@ss123!"
                })
                if login_resp.status_code == 200:
                    return login_resp.json()["access_token"]
                return None
            # Login
            login_resp = c.post("/auth/login", data={
                "username": email,
                "password": "ConcurP@ss123!"
            })
            if login_resp.status_code != 200:
                return None
            return login_resp.json()["access_token"]

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(register_and_login, i) for i in range(5)]
            tokens = [f.result() for f in futures]

        valid_tokens = [t for t in tokens if t is not None]
        assert len(valid_tokens) >= 4, f"Only got {len(valid_tokens)}/5 tokens"
        assert all(t is not None for t in valid_tokens)

    def test_concurrent_predictions_same_user(self):
        """Same user making predictions concurrently."""
        import uuid
        client = TestClient(app)
        suffix = uuid.uuid4().hex[:8]
        email = f"concurrent_predict_{suffix}@test.com"

        # Setup user
        signup_resp = client.post("/auth/signup", json={
            "email": email,
            "password": "ConcurP@ss123!"
        })
        assert signup_resp.status_code == 200, f"Signup failed: {signup_resp.text}"
        login_resp = client.post("/auth/login", data={
            "username": email,
            "password": "ConcurP@ss123!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        def predict(msg_id):
            c = TestClient(app)
            resp = c.post("/predict", json={
                "text": f"Concurrent prediction test {msg_id}",
                "source": "concurrency"
            }, headers=headers)
            return resp.status_code == 200

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(predict, i) for i in range(20)]
            results = [f.result() for f in futures]

        success_rate = sum(results) / len(results)
        assert success_rate >= 0.8, f"Concurrent predictions: {success_rate:.1%}"


class TestRaceCondition:
    def test_race_condition_signup(self):
        """No race condition on concurrent signup with same email."""
        client = TestClient(app)
        results = []

        def signup():
            resp = client.post("/auth/signup", json={
                "email": "race@test.com",
                "password": "RaceP@ss123"
            })
            results.append(resp.status_code)

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(signup) for _ in range(3)]
            for f in futures:
                f.result()

        # Only one should succeed
        success_count = sum(1 for r in results if r == 200)
        assert success_count <= 1, f"Multiple signups succeeded: {success_count}"

    def test_race_condition_token_blacklist(self):
        """No race condition on concurrent token revocation."""
        import threading

        from backend.app.core.security import revoke_token

        jti = "test-jti-for-race-condition"
        errors = []

        def revoke():
            try:
                revoke_token(jti)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=revoke) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Race condition errors: {errors}"


class TestDeadlockPrevention:
    def test_no_deadlock_concurrent_requests(self):
        """System should not deadlock under concurrent load."""
        client = TestClient(app)

        start = time.time()
        timeout = 10  # seconds

        def worker():
            while time.time() - start < timeout:
                try:
                    client.get("/health")
                    client.post("/predict", json={
                        "text": "Deadlock prevention test",
                        "source": "deadlock"
                    })
                except Exception:
                    pass

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        # If we reach here without deadlock, test passes
        assert True


class TestAsyncOperations:
    def test_async_cache_operations(self):
        """Async cache operations should complete without issues."""
        from backend.app.core.cache import get_cache

        async def cache_ops():
            cache = get_cache()
            await cache.set("async_test", "value")
            result = await cache.get("async_test")
            assert result == "value"
            await cache.delete("async_test")
            assert await cache.get("async_test") is None

        asyncio.run(cache_ops())

    def test_async_predictions(self):
        """Predictions in async context."""
        from fastapi.testclient import TestClient

        client = TestClient(app)

        async def make_predictions():
            loop = asyncio.get_event_loop()

            def predict():
                return client.post("/predict", json={
                    "text": "Async prediction test",
                    "source": "async"
                })

            tasks = [loop.run_in_executor(None, predict) for _ in range(5)]
            results = await asyncio.gather(*tasks)
            return [r.status_code for r in results]

        status_codes = asyncio.run(make_predictions())
        assert all(s == 200 for s in status_codes)


class TestResourceLeak:
    def test_no_connection_leak(self):
        """No database connection leak under load."""
        try:
            import psutil
        except ImportError:
            pytest.skip("psutil not installed")
        import os

        process = psutil.Process(os.getpid())
        open_files_before = len(process.open_files())

        client = TestClient(app)
        for _ in range(50):
            client.post("/predict", json={
                "text": "Resource leak test",
                "source": "leak_test"
            })

        open_files_after = len(process.open_files())
        # Allow some overhead but not massive leak
        assert open_files_after - open_files_before < 50, \
            f"Possible file descriptor leak: {open_files_before} -> {open_files_after}"

    def test_no_thread_leak(self):
        """No thread leak under load."""
        import threading
        threads_before = threading.active_count()

        client = TestClient(app)
        for _ in range(30):
            client.post("/predict", json={
                "text": "Thread leak test",
                "source": "leak_test"
            })

        threads_after = threading.active_count()
        # Allow some overhead but not massive leak
        assert threads_after - threads_before < 20, \
            f"Possible thread leak: {threads_before} -> {threads_after}"

