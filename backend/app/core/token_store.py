"""
Enterprise Distributed Token Store
====================================
Redis-backed token blacklist, refresh token store, and rate-limit store.

Falls back to in-memory implementation when Redis is unavailable so the
application remains functional in development and tests.
"""

import time
from datetime import UTC, datetime
from typing import Any

from loguru import logger


class DistributedTokenStore:
    """
    Distributed token and rate-limit store backed by Redis.

    Provides:
    - Token blacklist (revoked JTI)
    - Refresh token registry (for rotation/release)
    - Per-key rate limiting (counters with TTL)
    """

    # Redis key prefixes
    BLACKLIST_PREFIX = "scamdetector:blacklist:"
    REFRESH_PREFIX = "scamdetector:refresh:"
    RATE_PREFIX = "scamdetector:ratelimit:"

    def __init__(self, redis_url: str | None = None):
        self.redis_url = redis_url
        self._redis = None
        self._redis_available = False
        # In-memory fallback
        self._blacklist: set[str] = set()
        self._refresh: dict[str, dict[str, Any]] = {}
        self._rate: dict[str, list[datetime]] = {}

        if redis_url:
            self._connect()

    def _connect(self) -> None:
        """Attempt to connect to Redis."""
        try:
            import redis as redis_sync
            self._redis = redis_sync.from_url(
                self.redis_url,
                socket_connect_timeout=2,
                socket_timeout=2,
                decode_responses=True,
            )
            self._redis.ping()
            self._redis_available = True
            logger.info("DistributedTokenStore connected to Redis")
        except Exception as e:  # pragma: no cover
            logger.warning(f"DistributedTokenStore Redis unavailable, using memory fallback: {e}")

    def is_redis_available(self) -> bool:
        """Whether Redis is currently backing the store."""
        return self._redis_available

    # ------------------------------------------------------------------
    # Blacklist
    # ------------------------------------------------------------------
    def blacklist_token(self, jti: str, ttl_seconds: int = 86400) -> None:
        """Add a JTI to the blacklist with a TTL."""
        if self._redis_available and self._redis:
            try:
                self._redis.setex(f"{self.BLACKLIST_PREFIX}{jti}", ttl_seconds, "1")
                return
            except Exception as e:
                logger.debug(f"Redis blacklist set failed: {e}")
                self._redis_available = False
        self._blacklist.add(jti)

    def is_blacklisted(self, jti: str) -> bool:
        """Check if a JTI is blacklisted."""
        if self._redis_available and self._redis:
            try:
                return bool(self._redis.exists(f"{self.BLACKLIST_PREFIX}{jti}"))
            except Exception as e:
                logger.debug(f"Redis blacklist check failed: {e}")
                self._redis_available = False
        return jti in self._blacklist

    # ------------------------------------------------------------------
    # Refresh token registry
    # ------------------------------------------------------------------
    def store_refresh_token(self, jti: str, subject: str, ttl_seconds: int) -> None:
        """Store a refresh token for rotation tracking."""
        value = f"{subject}|{int(time.time())}"
        if self._redis_available and self._redis:
            try:
                self._redis.setex(f"{self.REFRESH_PREFIX}{jti}", ttl_seconds, value)
                return
            except Exception as e:
                logger.debug(f"Redis refresh set failed: {e}")
                self._redis_available = False
        self._refresh[jti] = {"sub": subject}

    def get_refresh_subject(self, jti: str) -> str | None:
        """Get the subject for a stored refresh token."""
        if self._redis_available and self._redis:
            try:
                raw = self._redis.get(f"{self.REFRESH_PREFIX}{jti}")
                if raw:
                    subject = raw.split("|")[0]
                    return subject
                return None
            except Exception:
                self._redis_available = False
        entry = self._refresh.get(jti)
        return entry.get("sub") if entry else None

    def revoke_refresh_token(self, jti: str) -> None:
        """Revoke a refresh token (remove from registry + blacklist)."""
        if self._redis_available and self._redis:
            try:
                self._redis.delete(f"{self.REFRESH_PREFIX}{jti}")
                self.blacklist_token(jti)
                return
            except Exception:
                self._redis_available = False
        self._refresh.pop(jti, None)
        self._blacklist.add(jti)

    def revoke_all_user_refresh(self, subject: str) -> int:
        """Revoke all refresh tokens for a user. Returns count (memory only)."""
        if self._redis_available:
            # With Redis, we don't maintain a per-user index by default.
            # Return 0 (caller handles). Actual revocation via JWT versioning.
            return 0
        count = 0
        for jti, entry in list(self._refresh.items()):
            if entry.get("sub") == subject:
                self._refresh.pop(jti, None)
                self._blacklist.add(jti)
                count += 1
        return count

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------
    def rate_limit_check(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        """
        Check and record a rate-limited action.

        Returns (is_allowed, retry_after_seconds).
        """
        if self._redis_available and self._redis:
            try:
                rk = f"{self.RATE_PREFIX}{key}"
                pipe = self._redis.pipeline()
                pipe.incr(rk)
                pipe.expire(rk, window_seconds)
                count, _ = pipe.execute()
                if count > max_requests:
                    ttl = self._redis.ttl(rk)
                    return False, max(ttl, 1)
                return True, 0
            except Exception:
                self._redis_available = False
        # In-memory fallback
        now = datetime.now(UTC)
        window_start = now.timestamp() - window_seconds
        if key in self._rate:
            self._rate[key] = [t for t in self._rate[key] if t.timestamp() > window_start]
        else:
            self._rate[key] = []
        if len(self._rate[key]) >= max_requests:
            oldest = min(self._rate[key])
            retry_after = int(oldest.timestamp() + window_seconds - now.timestamp())
            return False, max(retry_after, 1)
        self._rate[key].append(now)
        return True, 0

    def clear(self) -> None:
        """Clear all local in-memory state (tests)."""
        self._blacklist.clear()
        self._refresh.clear()
        self._rate.clear()


# Global singleton
_store_instance: DistributedTokenStore | None = None


def get_token_store() -> DistributedTokenStore:
    """Get the global token store instance."""
    global _store_instance
    if _store_instance is None:
        import os
        _store_instance = DistributedTokenStore(redis_url=os.getenv("REDIS_URL"))
    return _store_instance
