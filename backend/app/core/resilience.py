"""
Enterprise Resilience Patterns
=================================
Circuit breaker, retry policies, bulkhead isolation,
timeout handling, and fallback mechanisms.
"""

import asyncio
import functools
import hashlib
import inspect
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from enum import Enum
from queue import Queue
from typing import Any

from loguru import logger

# =============================================================================
# Circuit Breaker
# =============================================================================

class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing — reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    Prevents cascading failures by stopping calls to a failing service.
    After a timeout, allows a single test request to check if the service recovered.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: datetime | None = None
        self.half_open_calls = 0

    def __enter__(self):
        if self.state == CircuitState.OPEN:
            if self.last_failure_time and (
                datetime.now(UTC) - self.last_failure_time
            ).total_seconds() >= self.recovery_timeout:
                logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Retry after {self.recovery_timeout}s"
                )

        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.half_open_max_calls:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is HALF_OPEN and "
                    f"max test calls ({self.half_open_max_calls}) reached"
                )
            self.half_open_calls += 1

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type and issubclass(exc_type, Exception):
            self._on_failure()
        else:
            self._on_success()

    def _on_success(self):
        self.success_count += 1
        if self.state == CircuitState.HALF_OPEN:
            logger.info(f"Circuit breaker '{self.name}' recovered — transitioning to CLOSED")
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.half_open_calls = 0
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success in CLOSED state
            self.failure_count = 0

    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = datetime.now(UTC)

        if self.state == CircuitState.HALF_OPEN:
            logger.warning(f"Circuit breaker '{self.name}' test call failed — back to OPEN")
            self.state = CircuitState.OPEN
        elif self.failure_count >= self.failure_threshold:
            logger.warning(
                f"Circuit breaker '{self.name}' OPENING after "
                f"{self.failure_count} failures"
            )
            self.state = CircuitState.OPEN

    def reset(self):
        """Manually reset the circuit breaker."""
        logger.info(f"Circuit breaker '{self.name}' manually reset")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0

    @property
    def is_available(self) -> bool:
        return self.state != CircuitState.OPEN

    def get_state(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "is_available": self.is_available,
        }


class CircuitBreakerOpenError(Exception):
    """Raised when a circuit breaker is open."""
    pass


# =============================================================================
# Retry Policy
# =============================================================================

class RetryPolicy:
    """
    Configurable retry policy with exponential backoff and jitter.

    Supports:
    - Max retries
    - Base delay (with exponential backoff)
    - Max delay
    - Jitter (randomizes delay to avoid thundering herd)
    - Retryable exceptions
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: tuple[type] | None = None,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or (ConnectionError, TimeoutError, OSError)

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for the given attempt number."""
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)

        if self.jitter:
            import random
            delay = delay * (0.5 + random.random() * 0.5)  # 50-100% of calculated delay

        return delay


def with_retry(
    retry_policy: RetryPolicy | None = None,
    circuit_breaker: CircuitBreaker | None = None,
):
    """
    Decorator that adds retry and circuit breaker support to async functions.

    Args:
        retry_policy: Retry configuration
        circuit_breaker: Circuit breaker instance
    """
    policy = retry_policy or RetryPolicy()

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None

            if circuit_breaker:
                try:
                    with circuit_breaker:
                        pass
                except CircuitBreakerOpenError:
                    raise

            for attempt in range(policy.max_retries + 1):
                try:
                    if circuit_breaker:
                        with circuit_breaker:
                            result = await func(*args, **kwargs)
                    else:
                        result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    last_exception = e

                    if not isinstance(e, policy.retryable_exceptions):
                        raise

                    if attempt < policy.max_retries:
                        delay = policy.get_delay(attempt)
                        logger.warning(
                            f"Retry {attempt + 1}/{policy.max_retries} for "
                            f"{func.__name__} after {delay:.2f}s: {str(e)}"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"All {policy.max_retries} retries exhausted for "
                            f"{func.__name__}: {str(e)}"
                        )
                        raise

            raise last_exception  # Shouldn't reach here

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            import time as sync_time
            last_exception = None

            if circuit_breaker:
                try:
                    with circuit_breaker:
                        pass
                except CircuitBreakerOpenError:
                    raise

            for attempt in range(policy.max_retries + 1):
                try:
                    if circuit_breaker:
                        with circuit_breaker:
                            result = func(*args, **kwargs)
                    else:
                        result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    last_exception = e

                    if not isinstance(e, policy.retryable_exceptions):
                        raise

                    if attempt < policy.max_retries:
                        delay = policy.get_delay(attempt)
                        logger.warning(
                            f"Retry {attempt + 1}/{policy.max_retries} for "
                            f"{func.__name__} after {delay:.2f}s: {str(e)}"
                        )
                        sync_time.sleep(delay)

            raise last_exception

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# =============================================================================
# Bulkhead Pattern
# =============================================================================

class Bulkhead:
    """
    Bulkhead isolation pattern.

    Limits concurrent calls to a service to prevent resource exhaustion.
    Uses a semaphore-based approach.
    """

    def __init__(self, name: str, max_concurrent: int = 10, max_queue: int = 100):
        self.name = name
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent) if hasattr(asyncio, "Semaphore") else None
        self._queue: Queue = Queue(maxsize=max_queue)
        self.active_calls = 0
        self.queued_calls = 0
        self.rejected_calls = 0

    async def acquire(self) -> bool:
        """Try to acquire a slot. Returns False if at capacity."""
        if self.active_calls >= self.max_concurrent:
            if self.queued_calls >= self._queue.maxsize:
                self.rejected_calls += 1
                logger.warning(f"Bulkhead '{self.name}' at capacity — rejecting call")
                return False
            self.queued_calls += 1
            return False

        if self.semaphore:
            await self.semaphore.acquire()
        self.active_calls += 1
        return True

    def release(self):
        """Release a slot."""
        self.active_calls -= 1
        if self.queued_calls > 0:
            self.queued_calls -= 1
        if self.semaphore:
            self.semaphore.release()

    async def __aenter__(self):
        acquired = await self.acquire()
        if not acquired:
            raise BulkheadFullError(
                f"Bulkhead '{self.name}' is full "
                f"({self.active_calls}/{self.max_concurrent} active, "
                f"{self.queued_calls} queued)"
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.release()

    def get_state(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "active_calls": self.active_calls,
            "max_concurrent": self.max_concurrent,
            "queued_calls": self.queued_calls,
            "max_queue": self._queue.maxsize,
            "rejected_calls": self.rejected_calls,
        }


class BulkheadFullError(Exception):
    """Raised when bulkhead is at capacity."""
    pass


# =============================================================================
# Timeout Handler
# =============================================================================

async def with_timeout(coro: Awaitable, timeout_seconds: float, fallback: Any = None):
    """
    Execute a coroutine with a timeout.
    Returns fallback value on timeout.
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except TimeoutError:
        logger.warning(f"Operation timed out after {timeout_seconds}s")
        if fallback is not None:
            return fallback
        raise TimeoutError(f"Operation timed out after {timeout_seconds}s")


# =============================================================================
# Idempotency Key Store
# =============================================================================

class IdempotencyStore:
    """
    Idempotency key store to prevent duplicate processing.
    Uses in-memory dict (replace with Redis in production).
    """

    def __init__(self, ttl_seconds: int = 3600):
        self._store: dict[str, dict[str, Any]] = {}
        self.ttl_seconds = ttl_seconds

    def get_key(self, key: str) -> dict[str, Any] | None:
        """Get result for an idempotency key."""
        entry = self._store.get(key)
        if not entry:
            return None

        # Check TTL
        created = entry.get("created_at")
        if created:
            age = (datetime.now(UTC) - created).total_seconds()
            if age > self.ttl_seconds:
                del self._store[key]
                return None

        return entry.get("result")

    def set_key(self, key: str, result: Any) -> None:
        """Store result for an idempotency key."""
        self._store[key] = {
            "result": result,
            "created_at": datetime.now(UTC),
        }

    def generate_key(self, data: dict[str, Any]) -> str:
        """Generate a deterministic idempotency key from request data."""
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()


# =============================================================================
# Fallback Handler
# =============================================================================

class FallbackHandler:
    """
    Provides fallback responses when services are unavailable.
    """

    @staticmethod
    def get_fallback_prediction() -> dict[str, Any]:
        """Return a safe fallback prediction when model is unavailable."""
        return {
            "label": "safe",
            "confidence": 0.5,
            "explanation": {
                "keywords": ["fallback", "model_unavailable"],
                "reason": "The AI model is currently unavailable. "
                          "Showing safe result as a precaution.",
                "risk_level": "unknown",
                "safety_advice": "Please try again later. "
                                 "In the meantime, exercise caution with the content.",
                "simple_explanation": "Our AI system is temporarily unavailable. "
                                      "Please resubmit your query later.",
                "source": "fallback_handler",
                "confidence": 0.5,
            },
        }

    @staticmethod
    def get_fallback_dashboard() -> dict[str, Any]:
        """Return fallback dashboard data."""
        return {
            "total_scans": 0,
            "scam_percentage": 0.0,
            "safe_percentage": 0.0,
            "recent_scans": [],
            "message": "Dashboard data is currently unavailable. Showing empty state.",
        }


# =============================================================================
# Resilience Manager
# =============================================================================

class ResilienceManager:
    """
    Manages all resilience patterns.
    Provides a centralized registry for circuit breakers and bulkheads.
    """

    def __init__(self):
        self.circuit_breakers: dict[str, CircuitBreaker] = {}
        self.bulkheads: dict[str, Bulkhead] = {}
        self.retry_policies: dict[str, RetryPolicy] = {}
        self.fallback = FallbackHandler()
        self.idempotency = IdempotencyStore()

    def add_circuit_breaker(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ) -> CircuitBreaker:
        """Register a circuit breaker."""
        cb = CircuitBreaker(name, failure_threshold, recovery_timeout)
        self.circuit_breakers[name] = cb
        return cb

    def add_bulkhead(
        self,
        name: str,
        max_concurrent: int = 10,
        max_queue: int = 100,
    ) -> Bulkhead:
        """Register a bulkhead."""
        bh = Bulkhead(name, max_concurrent, max_queue)
        self.bulkheads[name] = bh
        return bh

    def add_retry_policy(
        self,
        name: str,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> RetryPolicy:
        """Register a retry policy."""
        rp = RetryPolicy(max_retries, base_delay)
        self.retry_policies[name] = rp
        return rp

    def get_status(self) -> dict[str, Any]:
        """Get status of all resilience components."""
        return {
            "circuit_breakers": {
                name: cb.get_state()
                for name, cb in self.circuit_breakers.items()
            },
            "bulkheads": {
                name: bh.get_state()
                for name, bh in self.bulkheads.items()
            },
            "idempotency_store_size": len(self.idempotency._store),
        }


# Global resilience manager
resilience_manager = ResilienceManager()

