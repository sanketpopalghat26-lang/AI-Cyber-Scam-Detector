"""
Unit tests for resilience patterns.
Tests: circuit breaker, retry policy, bulkhead, timeout, idempotency, fallback.
"""
import asyncio
import time

import pytest

from backend.app.core.resilience import (
    Bulkhead,
    BulkheadFullError,
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
    FallbackHandler,
    IdempotencyStore,
    ResilienceManager,
    RetryPolicy,
    resilience_manager,
    with_retry,
    with_timeout,
)


class TestCircuitBreaker:
    def test_initial_state_closed(self):
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED
        assert cb.is_available is True

    def test_open_after_failures(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=60)
        for _ in range(3):
            try:
                with cb:
                    raise ConnectionError("fail")
            except ConnectionError:
                pass
        assert cb.state == CircuitState.OPEN
        assert cb.is_available is False

    def test_rejects_when_open(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=60)
        try:
            with cb:
                raise ConnectionError("fail")
        except ConnectionError:
            pass

        with pytest.raises(CircuitBreakerOpenError), cb:
            pass

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)
        try:
            with cb:
                raise ConnectionError("fail")
        except ConnectionError:
            pass

        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        # Entering the context when OPEN and recovery timeout elapsed should auto‑transition
        # to HALF_OPEN. Since half_open_max_calls=1, entering once succeeds,
        # but entering again raises CircuitBreakerOpenError.
        with cb:
            pass  # First entry transitions to HALF_OPEN and succeeds
        # Circuit is now CLOSED after the successful half-open call

    def test_half_open_success_closes(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)
        try:
            with cb:
                raise ConnectionError("fail")
        except ConnectionError:
            pass

        time.sleep(0.15)
        # After recovery timeout, __enter__ transitions to HALF_OPEN automatically
        with cb:
            pass  # Should succeed and transition to CLOSED
        assert cb.state == CircuitState.CLOSED

    def test_reset(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=60)
        try:
            with cb:
                raise ConnectionError("fail")
        except ConnectionError:
            pass

        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.is_available is True

    def test_success_resets_count(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=60)
        # Two failures
        for _ in range(2):
            try:
                with cb:
                    raise ConnectionError("fail")
            except ConnectionError:
                pass
        # One success
        with cb:
            pass
        assert cb.failure_count == 0

    def test_get_state(self):
        cb = CircuitBreaker("test", failure_threshold=5, recovery_timeout=30)
        state = cb.get_state()
        assert state["name"] == "test"
        assert state["state"] == "closed"
        assert state["failure_threshold"] == 5
        assert state["is_available"] is True


class TestRetryPolicy:
    def test_max_retries(self):
        call_count = 0

        async def failing_func():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("fail")

        policy = RetryPolicy(max_retries=2, base_delay=0.01)
        decorated = with_retry(retry_policy=policy)(failing_func)

        with pytest.raises(ConnectionError):
            asyncio.run(decorated())
        assert call_count == 3  # initial + 2 retries

    def test_success_no_retry(self):
        call_count = 0

        async def success_func():
            nonlocal call_count
            call_count += 1
            return "ok"

        policy = RetryPolicy(max_retries=3, base_delay=0.01)
        decorated = with_retry(retry_policy=policy)(success_func)
        result = asyncio.run(decorated())
        assert result == "ok"
        assert call_count == 1

    def test_non_retryable_exception(self):
        async def failing_func():
            raise ValueError("not retryable")

        policy = RetryPolicy(max_retries=2, base_delay=0.01,
                             retryable_exceptions=(ConnectionError,))
        decorated = with_retry(retry_policy=policy)(failing_func)

        with pytest.raises(ValueError):
            asyncio.run(decorated())

    def test_delay_increases(self):
        policy = RetryPolicy(max_retries=2, base_delay=1.0, exponential_base=2.0, jitter=False)
        delays = [policy.get_delay(i) for i in range(3)]
        assert delays[1] >= delays[0]
        assert delays[2] >= delays[1]

    def test_max_delay_capped(self):
        policy = RetryPolicy(max_retries=5, base_delay=10.0, max_delay=30.0, jitter=False)
        delay = policy.get_delay(5)
        assert delay <= 30.0


class TestBulkhead:
    @pytest.mark.asyncio
    async def test_acquire_release(self):
        bh = Bulkhead("test", max_concurrent=2, max_queue=10)
        acquired = await bh.acquire()
        assert acquired is True
        assert bh.active_calls == 1
        bh.release()
        assert bh.active_calls == 0

    @pytest.mark.asyncio
    async def test_max_concurrent(self):
        bh = Bulkhead("test", max_concurrent=1, max_queue=1)
        await bh.acquire()
        acquired = await bh.acquire()
        assert acquired is False

    @pytest.mark.asyncio
    async def test_context_manager(self):
        bh = Bulkhead("test", max_concurrent=5, max_queue=10)
        async with bh:
            assert bh.active_calls == 1
        assert bh.active_calls == 0

    @pytest.mark.asyncio
    async def test_full_error(self):
        bh = Bulkhead("test", max_concurrent=1, max_queue=0)
        await bh.acquire()
        with pytest.raises(BulkheadFullError):
            async with bh:
                pass

    def test_get_state(self):
        bh = Bulkhead("test", max_concurrent=10, max_queue=100)
        state = bh.get_state()
        assert state["name"] == "test"
        assert state["max_concurrent"] == 10
        assert state["max_queue"] == 100


class TestTimeout:
    @pytest.mark.asyncio
    async def test_completes_within_timeout(self):
        async def quick():
            await asyncio.sleep(0.01)
            return "done"

        result = await with_timeout(quick(), timeout_seconds=5)
        assert result == "done"

    @pytest.mark.asyncio
    async def test_timeout_exception(self):
        async def slow():
            await asyncio.sleep(10)

        with pytest.raises(TimeoutError):
            await with_timeout(slow(), timeout_seconds=0.05)

    @pytest.mark.asyncio
    async def test_fallback_on_timeout(self):
        async def slow():
            await asyncio.sleep(10)

        result = await with_timeout(slow(), timeout_seconds=0.05, fallback="fallback")
        assert result == "fallback"


class TestIdempotencyStore:
    def test_set_and_get(self):
        store = IdempotencyStore(ttl_seconds=3600)
        key = "test_key"
        store.set_key(key, {"result": "ok"})
        result = store.get_key(key)
        assert result == {"result": "ok"}

    def test_missing_key(self):
        store = IdempotencyStore()
        assert store.get_key("nonexistent") is None

    def test_ttl_expiry(self):
        store = IdempotencyStore(ttl_seconds=0)
        store.set_key("test", "value")
        assert store.get_key("test") is None

    def test_generate_key(self):
        store = IdempotencyStore()
        key1 = store.generate_key({"a": 1, "b": 2})
        key2 = store.generate_key({"b": 2, "a": 1})  # Same data, different order
        key3 = store.generate_key({"a": 1, "b": 3})
        assert key1 == key2  # Deterministic
        assert key1 != key3  # Different data

    def test_delete_after_ttl(self):
        store = IdempotencyStore(ttl_seconds=1)
        store.set_key("test", "value")
        assert store.get_key("test") == "value"
        time.sleep(1.1)
        assert store.get_key("test") is None


class TestFallbackHandler:
    def test_fallback_prediction(self):
        fallback = FallbackHandler.get_fallback_prediction()
        assert fallback["label"] == "safe"
        assert "explanation" in fallback
        assert fallback["explanation"]["source"] == "fallback_handler"

    def test_fallback_dashboard(self):
        fallback = FallbackHandler.get_fallback_dashboard()
        assert fallback["total_scans"] == 0
        assert "message" in fallback


class TestResilienceManager:
    def test_add_circuit_breaker(self):
        mgr = ResilienceManager()
        cb = mgr.add_circuit_breaker("test_cb", failure_threshold=3, recovery_timeout=30)
        assert cb.name == "test_cb"
        assert "test_cb" in mgr.circuit_breakers

    def test_add_bulkhead(self):
        mgr = ResilienceManager()
        bh = mgr.add_bulkhead("test_bh", max_concurrent=5, max_queue=20)
        assert bh.name == "test_bh"
        assert "test_bh" in mgr.bulkheads

    def test_add_retry_policy(self):
        mgr = ResilienceManager()
        rp = mgr.add_retry_policy("test_rp", max_retries=3, base_delay=1.0)
        assert rp.max_retries == 3

    def test_get_status(self):
        mgr = ResilienceManager()
        mgr.add_circuit_breaker("cb1")
        mgr.add_bulkhead("bh1")
        status = mgr.get_status()
        assert "circuit_breakers" in status
        assert "bulkheads" in status
        assert "idempotency_store_size" in status

    def test_global_instance(self):
        assert resilience_manager is not None
        assert hasattr(resilience_manager, "circuit_breakers")
        assert hasattr(resilience_manager, "bulkheads")

