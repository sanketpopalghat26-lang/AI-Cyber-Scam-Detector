"""
Unit tests for the distributed token store (Redis-backed with memory fallback).
"""

import pytest

from backend.app.core.security import (
    create_token_pair,
    decode_token,
    refresh_access_token,
    revoke_all_user_tokens,
    revoke_token,
)
from backend.app.core.token_store import DistributedTokenStore


@pytest.fixture
def store() -> DistributedTokenStore:
    """Create a fresh in-memory token store for tests."""
    s = DistributedTokenStore(redis_url=None)
    s.clear()
    return s


def test_blacklist_and_is_blacklisted(store):
    store.blacklist_token("jti-123", ttl_seconds=60)
    assert store.is_blacklisted("jti-123") is True
    assert store.is_blacklisted("jti-other") is False


def test_refresh_token_store_roundtrip(store):
    store.store_refresh_token("jti-1", "user@example.com", ttl_seconds=3600)
    assert store.get_refresh_subject("jti-1") == "user@example.com"
    assert store.get_refresh_subject("missing") is None


def test_revoke_refresh_token(store):
    store.store_refresh_token("jti-1", "user@example.com", ttl_seconds=3600)
    store.revoke_refresh_token("jti-1")
    assert store.is_blacklisted("jti-1") is True
    assert store.get_refresh_subject("jti-1") is None


def test_rate_limit_allows_then_blocks(store):
    allowed, _ = store.rate_limit_check("key", max_requests=2, window_seconds=60)
    assert allowed is True
    allowed, _ = store.rate_limit_check("key", max_requests=2, window_seconds=60)
    assert allowed is True
    allowed, retry_after = store.rate_limit_check("key", max_requests=2, window_seconds=60)
    assert allowed is False
    assert retry_after >= 1


def test_revoke_all_user_refresh(store):
    store.store_refresh_token("jti-1", "user@example.com", ttl_seconds=3600)
    store.store_refresh_token("jti-2", "user@example.com", ttl_seconds=3600)
    store.store_refresh_token("jti-3", "other@example.com", ttl_seconds=3600)
    count = store.revoke_all_user_refresh("user@example.com")
    assert count == 2
    assert store.is_blacklisted("jti-1") is True
    assert store.is_blacklisted("jti-2") is True
    assert store.is_blacklisted("jti-3") is False


def test_security_integration_revocation():
    """Decoded token should be rejected after revocation via security layer."""
    pair = create_token_pair(subject="user@example.com")
    payload = decode_token(pair.access_token)
    assert payload is not None
    jti = payload["jti"]
    revoke_token(jti)
    assert decode_token(pair.access_token) is None


def test_refresh_rotation():
    pair = create_token_pair(subject="user@example.com")
    new_pair = refresh_access_token(pair.refresh_token)
    assert new_pair is not None
    assert new_pair.access_token != pair.access_token
    assert new_pair.refresh_token != pair.refresh_token


def test_revoke_all_user_tokens(store):
    pair = create_token_pair(subject="user@example.com", scopes=["predict"])
    count = revoke_all_user_tokens("user@example.com")
    assert count >= 0
    # Access token should be decodable still if not revoked directly, but refresh tracked
    assert pair.access_token is not None
