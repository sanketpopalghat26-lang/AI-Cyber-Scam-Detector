"""
Enterprise Caching Module
===========================
Redis-backed caching with connection pooling,
cache-aside pattern, and TTL management.
"""

import asyncio
import contextlib
import fnmatch
import hashlib
import inspect
import os
import pickle
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from loguru import logger

T = TypeVar("T")


class RedisCache:
    """
    Redis-based cache with connection pooling.
    Falls back to in-memory cache if Redis is unavailable.
    """

    def __init__(
        self,
        redis_url: str | None = None,
        default_ttl: int = 300,
        max_connections: int = 10,
        prefix: str = "scamdetector:",
    ):
        self.redis_url = redis_url or os.getenv("REDIS_URL")
        self.default_ttl = default_ttl
        self.prefix = prefix
        self._redis = None
        self._redis_available = False
        self._memory_cache: dict[str, tuple[Any, float | None]] = {}
        self._memory_max_size = 1000

        if self.redis_url:
            self._connect()

    def _connect(self) -> None:
        """Attempt Redis connection."""
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                self.redis_url,
                max_connections=10,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=True,
                decode_responses=False,
            )
            # redis.asyncio.from_url() is lazy: the connection is established on
            # first use. We mark the backend as available and degrade to the
            # in-memory fallback automatically if a later operation fails.
            self._redis_available = True
            logger.info("Redis cache connected")
        except ImportError:
            logger.warning("redis-py not installed. Using in-memory cache fallback.")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Using in-memory cache fallback.")

    def _make_key(self, key: str) -> str:
        """Create a namespaced cache key."""
        return f"{self.prefix}{key}"

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        full_key = self._make_key(key)

        if self._redis_available and self._redis:
            try:
                data = await self._redis.get(full_key)
                if data:
                    return pickle.loads(data)
            except Exception as e:
                logger.debug(f"Redis get failed: {e}")
                self._redis_available = False

        # Fallback to in-memory cache
        return self._memory_get(full_key)

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> bool:
        """Set value in cache with TTL."""
        full_key = self._make_key(key)
        ttl = ttl if ttl is not None else self.default_ttl

        # Always write to the local memory layer as a write-through cache.
        # This provides a fast local fallback if Redis becomes unavailable.
        self._memory_set(full_key, value, ttl)

        if self._redis_available and self._redis:
            try:
                data = pickle.dumps(value)
                await self._redis.setex(full_key, ttl, data)
                return True
            except Exception as e:
                logger.debug(f"Redis set failed: {e}")
                self._redis_available = False

        return True

    async def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        full_key = self._make_key(key)

        if self._redis_available and self._redis:
            with contextlib.suppress(Exception):
                await self._redis.delete(full_key)

        self._memory_delete(full_key)
        return True

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        full_key = self._make_key(key)

        if self._redis_available and self._redis:
            try:
                result = await self._redis.exists(full_key)
                return bool(result)
            except Exception:
                pass

        return self._memory_exists(full_key)

    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching a pattern."""
        full_pattern = self._make_key(pattern)
        count = 0

        if self._redis_available and self._redis:
            try:
                cursor = 0
                while True:
                    cursor, keys = await self._redis.scan(
                        cursor=cursor, match=full_pattern, count=100
                    )
                    if keys:
                        await self._redis.delete(*keys)
                        count += len(keys)
                    if cursor == 0:
                        break
            except Exception:
                pass

        # Also clear matching in-memory cache entries
        keys_to_delete = [
            k for k in self._memory_cache
            if fnmatch.fnmatch(k, full_pattern)
        ]
        for k in keys_to_delete:
            del self._memory_cache[k]
        count += len(keys_to_delete)

        return count

    async def increment(self, key: str, amount: int = 1) -> int | None:
        """Increment a counter."""
        full_key = self._make_key(key)

        if self._redis_available and self._redis:
            try:
                return await self._redis.incrby(full_key, amount)
            except Exception:
                pass

        return None

    # In-memory fallback methods
    def _memory_get(self, key: str) -> Any | None:
        entry = self._memory_cache.get(key)
        if entry is None:
            return None
        value, expiry = entry
        if expiry is not None and time.time() > expiry:
            del self._memory_cache[key]
            return None
        return value

    def _memory_set(self, key: str, value: Any, ttl: int) -> None:
        # ttl=0 means "expire immediately"; None means "never expire".
        expiry = time.time() + ttl if ttl is not None else None
        if len(self._memory_cache) >= self._memory_max_size:
            # Evict oldest entry
            with contextlib.suppress(StopIteration):
                self._memory_cache.pop(next(iter(self._memory_cache)))
        self._memory_cache[key] = (value, expiry)

    def _memory_delete(self, key: str) -> None:
        self._memory_cache.pop(key, None)

    def _memory_exists(self, key: str) -> bool:
        return key in self._memory_cache

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()

    def health_check(self) -> dict[str, Any]:
        """Check cache health."""
        if self._redis_available:
            return {"status": "healthy", "backend": "redis", "url": self.redis_url}
        return {
            "status": "degraded",
            "backend": "memory",
            "size": len(self._memory_cache),
        }


# Singleton instance
_cache_instance: RedisCache | None = None


def get_cache() -> RedisCache:
    """Get the global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RedisCache()
    return _cache_instance


# =============================================================================
# Cache decorators
# =============================================================================

def cached(ttl: int | None = None, key_prefix: str = ""):
    """
    Decorator that caches function results.

    Args:
        ttl: Cache TTL in seconds
        key_prefix: Prefix for cache key

    Usage:
        @cached(ttl=300)
        async def get_prediction(text: str):
            ...
    """
    def decorator(func: Callable) -> Callable:
        is_coro = inspect.iscoroutinefunction(func)

        async def _fetch(*args, **kwargs) -> Any:
            """Execute the wrapped function whether sync or async."""
            if is_coro:
                return await func(*args, **kwargs)
            return func(*args, **kwargs)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            cache = get_cache()

            # Generate cache key from function name + args
            key_parts = [func.__name__, key_prefix]
            key_parts.extend(str(a) for a in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()

            # Try cache first
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Execute function
            result = await _fetch(*args, **kwargs)

            # Cache result
            await cache.set(cache_key, result, ttl=ttl)
            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(async_wrapper(*args, **kwargs))
            finally:
                loop.close()

        if is_coro:
            return async_wrapper
        return sync_wrapper

    return decorator


def invalidate_cache(pattern: str):
    """
    Decorator that invalidates cache entries matching a pattern after function execution.

    Args:
        pattern: Cache key pattern to invalidate (e.g., "predictions:*")
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            cache = get_cache()
            await cache.clear_pattern(pattern)
            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(get_cache().clear_pattern(pattern))
            finally:
                loop.close()
            return result

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
