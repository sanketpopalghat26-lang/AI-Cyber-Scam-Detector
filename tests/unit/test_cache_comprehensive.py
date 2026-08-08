"""Comprehensive unit tests for the cache module."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.core.cache import RedisCache, cached, get_cache, invalidate_cache


# =============================================================================
# RedisCache Tests
# =============================================================================
class TestRedisCacheInit:
    def test_init_with_redis_url(self):
        with patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379"}):
            with patch("backend.app.core.cache.RedisCache._connect") as mock_connect:
                cache = RedisCache(redis_url="redis://localhost:6379")
                mock_connect.assert_called_once()

    def test_init_without_redis_url(self):
        with patch.dict("os.environ", {}, clear=True):
            cache = RedisCache()
            assert cache._redis is None
            assert cache._redis_available is False

    def test_init_with_defaults(self):
        cache = RedisCache()
        assert cache.default_ttl == 300
        assert cache.prefix == "scamdetector:"
        assert cache._memory_max_size == 1000

    def test_connect_success(self):
        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_redis = MagicMock()
            mock_from_url.return_value = mock_redis
            cache = RedisCache(redis_url="redis://localhost:6379")
            assert cache._redis_available is True

    def test_connect_import_error(self):
        with patch("builtins.__import__", side_effect=ImportError("No module")):
            cache = RedisCache(redis_url="redis://localhost:6379")
            assert cache._redis_available is False

    def test_connect_connection_error(self):
        with patch("redis.asyncio.from_url", side_effect=Exception("Connection refused")):
            cache = RedisCache(redis_url="redis://localhost:6379")
            assert cache._redis_available is False


class TestRedisCacheOperations:
    @pytest.fixture
    def cache(self):
        return RedisCache()

    @pytest.mark.asyncio
    async def test_get_set_basic(self, cache):
        await cache.set("test_key", "test_value", ttl=60)
        result = await cache.get("test_key")
        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_get_missing(self, cache):
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_with_default_ttl(self, cache):
        await cache.set("key1", "value1")
        result = await cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_delete(self, cache):
        await cache.set("del_key", "value")
        await cache.delete("del_key")
        assert await cache.get("del_key") is None

    @pytest.mark.asyncio
    async def test_exists(self, cache):
        await cache.set("exist_key", "value")
        assert await cache.exists("exist_key") is True
        assert await cache.exists("nonexistent") is False

    @pytest.mark.asyncio
    async def test_ttl_expiry(self, cache):
        await cache.set("ttl_key", "value", ttl=0)
        await asyncio.sleep(0.1)
        result = await cache.get("ttl_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_complex_objects(self, cache):
        obj = {"nested": {"list": [1, 2, 3], "bool": True}, "number": 42}
        await cache.set("complex", obj)
        result = await cache.get("complex")
        assert result == obj

    @pytest.mark.asyncio
    async def test_none_value(self, cache):
        await cache.set("none_key", None)
        result = await cache.get("none_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_key_prefix(self, cache):
        await cache.set("prefixed", "val")
        assert "scamdetector:prefixed" in cache._memory_cache

    @pytest.mark.asyncio
    async def test_clear_pattern(self, cache):
        await cache.set("user:1", "data1")
        await cache.set("user:2", "data2")
        await cache.set("other", "data3")
        count = await cache.clear_pattern("user:*")
        assert count >= 2
        assert await cache.get("user:1") is None
        assert await cache.get("other") == "data3"

    @pytest.mark.asyncio
    async def test_increment(self, cache):
        result = await cache.increment("counter")
        assert result is None  # No Redis, returns None

    @pytest.mark.asyncio
    async def test_memory_eviction(self, cache):
        cache._memory_max_size = 2
        await cache.set("key1", "val1")
        await cache.set("key2", "val2")
        await cache.set("key3", "val3")
        assert len(cache._memory_cache) <= 2

    @pytest.mark.asyncio
    async def test_health_check_degraded(self, cache):
        health = cache.health_check()
        assert health["status"] == "degraded"
        assert health["backend"] == "memory"

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, cache):
        cache._redis_available = True
        cache.redis_url = "redis://localhost:6379"
        health = cache.health_check()
        assert health["status"] == "healthy"
        assert health["backend"] == "redis"

    @pytest.mark.asyncio
    async def test_close(self, cache):
        cache._redis = AsyncMock()
        await cache.close()
        cache._redis.close.assert_called_once()


class TestRedisCacheRedisFallback:
    @pytest.mark.asyncio
    async def test_redis_get_fallback_to_memory(self):
        cache = RedisCache()
        cache._redis_available = True
        cache._redis = AsyncMock()
        cache._redis.get.side_effect = Exception("Redis down")
        await cache.set("key", "mem_value")
        cache._redis_available = True
        result = await cache.get("key")
        assert result == "mem_value"
        assert cache._redis_available is False

    @pytest.mark.asyncio
    async def test_redis_set_fallback_to_memory(self):
        cache = RedisCache()
        cache._redis_available = True
        cache._redis = AsyncMock()
        cache._redis.setex.side_effect = Exception("Redis down")
        result = await cache.set("key", "value")
        assert result is True
        assert await cache.get("key") == "value"
        assert cache._redis_available is False

    @pytest.mark.asyncio
    async def test_redis_delete_fallback(self):
        cache = RedisCache()
        cache._redis_available = True
        cache._redis = AsyncMock()
        cache._redis.delete.side_effect = Exception("Redis down")
        await cache.set("key", "value")
        result = await cache.delete("key")
        assert result is True
        assert await cache.get("key") is None

    @pytest.mark.asyncio
    async def test_redis_exists_fallback(self):
        cache = RedisCache()
        cache._redis_available = True
        cache._redis = AsyncMock()
        cache._redis.exists.side_effect = Exception("Redis down")
        await cache.set("key", "value")
        assert await cache.exists("key") is True

    @pytest.mark.asyncio
    async def test_redis_clear_pattern_fallback(self):
        cache = RedisCache()
        cache._redis_available = True
        cache._redis = AsyncMock()
        cache._redis.scan.side_effect = Exception("Redis down")
        await cache.set("key1", "val1")
        count = await cache.clear_pattern("key*")
        assert count >= 1


class TestRedisCacheRedisSuccess:
    @pytest.mark.asyncio
    async def test_redis_get_success(self):
        cache = RedisCache()
        cache._redis_available = True
        cache._redis = AsyncMock()
        import pickle
        cache._redis.get.return_value = pickle.dumps("redis_value")
        result = await cache.get("key")
        assert result == "redis_value"

    @pytest.mark.asyncio
    async def test_redis_set_success(self):
        cache = RedisCache()
        cache._redis_available = True
        cache._redis = AsyncMock()
        result = await cache.set("key", "value", ttl=60)
        assert result is True
        cache._redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_delete_success(self):
        cache = RedisCache()
        cache._redis_available = True
        cache._redis = AsyncMock()
        result = await cache.delete("key")
        assert result is True

    @pytest.mark.asyncio
    async def test_redis_exists_success(self):
        cache = RedisCache()
        cache._redis_available = True
        cache._redis = AsyncMock()
        cache._redis.exists.return_value = 1
        assert await cache.exists("key") is True

    @pytest.mark.asyncio
    async def test_redis_increment_success(self):
        cache = RedisCache()
        cache._redis_available = True
        cache._redis = AsyncMock()
        cache._redis.incrby.return_value = 5
        result = await cache.increment("counter", 5)
        assert result == 5

    @pytest.mark.asyncio
    async def test_redis_clear_pattern_success(self):
        cache = RedisCache()
        cache._redis_available = True
        cache._redis = AsyncMock()
        cache._redis.scan.return_value = (0, ["key1", "key2"])
        count = await cache.clear_pattern("key*")
        assert count == 2


# =============================================================================
# get_cache Tests
# =============================================================================
class TestGetCache:
    def test_get_cache_singleton(self):
        cache1 = get_cache()
        cache2 = get_cache()
        assert cache1 is cache2

    def test_get_cache_creates_instance(self):
        from backend.app.core.cache import _cache_instance
        _cache_instance = None
        cache = get_cache()
        assert cache is not None


# =============================================================================
# cached Decorator Tests
# =============================================================================
class TestCachedDecorator:
    @pytest.mark.asyncio
    async def test_cached_decorator_async(self):
        call_count = 0

        @cached(ttl=60)
        async def test_func(val):
            nonlocal call_count
            call_count += 1
            return f"result_{val}"

        result1 = await test_func("hello")
        result2 = await test_func("hello")
        assert result1 == "result_hello"
        assert result2 == "result_hello"
        assert call_count == 1  # Second call should be cached

    @pytest.mark.asyncio
    async def test_cached_decorator_different_args(self):
        call_count = 0

        @cached(ttl=60)
        async def test_func(val):
            nonlocal call_count
            call_count += 1
            return f"result_{val}"

        result1 = await test_func("a")
        result2 = await test_func("b")
        assert result1 == "result_a"
        assert result2 == "result_b"
        assert call_count == 2  # Different args, different cache

    def test_cached_decorator_sync(self):
        call_count = 0

        @cached(ttl=60)
        def sync_func(val):
            nonlocal call_count
            call_count += 1
            return f"result_{val}"

        result1 = sync_func("hello")
        result2 = sync_func("hello")
        assert result1 == "result_hello"
        assert result2 == "result_hello"
        assert call_count == 1


# =============================================================================
# invalidate_cache Decorator Tests
# =============================================================================
class TestInvalidateCacheDecorator:
    @pytest.mark.asyncio
    async def test_invalidate_cache_async(self):
        cache = get_cache()
        await cache.set("test:key1", "val1")
        await cache.set("test:key2", "val2")

        @invalidate_cache(pattern="test:*")
        async def update_data():
            return "updated"

        result = await update_data()
        assert result == "updated"
        assert await cache.get("test:key1") is None
        assert await cache.get("test:key2") is None

    def test_invalidate_cache_sync(self):
        cache = get_cache()

        @invalidate_cache(pattern="sync:*")
        def sync_update():
            return "done"

        result = sync_update()
        assert result == "done"
