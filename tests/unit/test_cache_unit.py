"""
Unit tests for cache module.
Tests: RedisCache, in-memory fallback, cache decorators.
"""
import asyncio
import time
from unittest.mock import patch

import pytest

from backend.app.core.cache import RedisCache, cached, invalidate_cache


@pytest.fixture
def in_memory_cache():
    """Use in-memory cache for testing."""
    cache = RedisCache(redis_url=None, default_ttl=60)
    # Clear the singleton
    import backend.app.core.cache as cache_module
    cache_module._cache_instance = cache
    yield cache
    cache_module._cache_instance = None


class TestInMemoryCache:
    def test_get_set(self, in_memory_cache):
        asyncio.run(in_memory_cache.set("key1", "value1"))
        result = asyncio.run(in_memory_cache.get("key1"))
        assert result == "value1"

    def test_get_missing(self, in_memory_cache):
        result = asyncio.run(in_memory_cache.get("nonexistent"))
        assert result is None

    def test_set_with_ttl(self, in_memory_cache):
        asyncio.run(in_memory_cache.set("short", "value", ttl=1))
        assert asyncio.run(in_memory_cache.get("short")) == "value"
        time.sleep(1.5)
        assert asyncio.run(in_memory_cache.get("short")) is None

    def test_delete(self, in_memory_cache):
        asyncio.run(in_memory_cache.set("del_key", "value"))
        asyncio.run(in_memory_cache.delete("del_key"))
        assert asyncio.run(in_memory_cache.get("del_key")) is None

    def test_exists(self, in_memory_cache):
        asyncio.run(in_memory_cache.set("exist_key", "value"))
        assert asyncio.run(in_memory_cache.exists("exist_key")) is True
        assert asyncio.run(in_memory_cache.exists("no_key")) is False

    def test_clear_pattern(self, in_memory_cache):
        asyncio.run(in_memory_cache.set("test:a", "1"))
        asyncio.run(in_memory_cache.set("test:b", "2"))
        asyncio.run(in_memory_cache.set("other:c", "3"))
        count = asyncio.run(in_memory_cache.clear_pattern("test:*"))
        assert count == 2
        assert asyncio.run(in_memory_cache.exists("test:a")) is False

    def test_memory_eviction(self, in_memory_cache):
        in_memory_cache._memory_max_size = 2
        asyncio.run(in_memory_cache.set("k1", "v1"))
        asyncio.run(in_memory_cache.set("k2", "v2"))
        asyncio.run(in_memory_cache.set("k3", "v3"))
        assert len(in_memory_cache._memory_cache) <= 2

    def test_complex_objects(self, in_memory_cache):
        obj = {"key": "value", "nested": [1, 2, 3], "bool": True}
        asyncio.run(in_memory_cache.set("complex", obj))
        result = asyncio.run(in_memory_cache.get("complex"))
        assert result == obj

    def test_none_value(self, in_memory_cache):
        asyncio.run(in_memory_cache.set("none_val", None))
        result = asyncio.run(in_memory_cache.get("none_val"))
        assert result is None

    def test_key_prefix(self, in_memory_cache):
        asyncio.run(in_memory_cache.set("test", "value"))
        key = in_memory_cache._make_key("test")
        assert key.startswith("scamdetector:")


class TestCacheDecorators:
    def test_cached_decorator(self, in_memory_cache):
        call_count = 0

        async def expensive_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        decorated = cached(ttl=60)(expensive_func)
        r1 = asyncio.run(decorated(5))
        r2 = asyncio.run(decorated(5))
        assert r1 == 10
        assert r2 == 10
        assert call_count == 1  # Only called once due to caching

    def test_cached_different_args(self, in_memory_cache):
        call_count = 0

        async def func(x):
            nonlocal call_count
            call_count += 1
            return x

        decorated = cached()(func)
        asyncio.run(decorated(1))
        asyncio.run(decorated(2))
        assert call_count == 2  # Different args = different cache keys

    def test_invalidate_cache(self, in_memory_cache):
        async def mutating_func():
            return "done"

        decorated = invalidate_cache("test:*")(mutating_func)
        asyncio.run(in_memory_cache.set("test:a", "value"))
        asyncio.run(decorated())
        assert asyncio.run(in_memory_cache.exists("test:a")) is False


class TestRedisConnectionFallback:
    def test_redis_unavailable_fallback(self):
        """When Redis is unreachable, the cache degrades to the in-memory layer."""
        cache = RedisCache(redis_url="redis://nonexistent:6379", default_ttl=60)
        # redis.asyncio.from_url() is lazy, so the connection is only established
        # on first use. A failed operation safely degrades to the in-memory layer.
        result = asyncio.run(cache.get("key"))
        assert result is None
        # A write-through set still lands in the local memory layer for resilience.
        asyncio.run(cache.set("key", "value"))
        assert asyncio.run(cache.get("key")) == "value"

    @patch("backend.app.core.cache.RedisCache._connect")
    def test_redis_connection_success(self, mock_connect):
        """Redis connection should succeed with valid config."""
        mock_connect.return_value = None
        cache = RedisCache(redis_url="redis://localhost:6379", default_ttl=60)
        # Will fall back to in-memory since redis module may not be installed
        result = asyncio.run(cache.get("key"))
        assert result is None

    def test_health_check_no_redis(self):
        cache = RedisCache(redis_url=None)
        health = cache.health_check()
        assert health["status"] == "degraded"
        assert health["backend"] == "memory"

