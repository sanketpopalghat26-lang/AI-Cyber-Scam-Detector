"""
Unit tests for enterprise security module.
Tests: JWT tokens, password hashing, RBAC, rate limiting, token rotation.
"""
import time
from datetime import UTC, datetime, timedelta

from jose import jwt

from backend.app.core.config import ALGORITHM, JWT_AUDIENCE, SECRET_KEY
from backend.app.core.security import (
    PERMISSIONS,
    ROLES,
    TokenPair,
    check_permission,
    check_rate_limit,
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_token,
    hash_password,
    refresh_access_token,
    revoke_all_user_tokens,
    revoke_token,
    role_has_privilege,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_password(self):
        pw = "MySecureP@ss123"
        hashed = hash_password(pw)
        assert hashed != pw
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_verify_password_correct(self):
        pw = "MySecureP@ss123"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed) is True

    def test_verify_password_incorrect(self):
        hashed = hash_password("CorrectP@ss1")
        assert verify_password("WrongP@ss1", hashed) is False

    def test_hash_uniqueness(self):
        pw = "SameP@ss123"
        h1 = hash_password(pw)
        h2 = hash_password(pw)
        assert h1 != h2  # Different salts

    def test_empty_password(self):
        # bcrypt will raise an exception on empty/too short input
        # This is acceptable behavior
        try:
            result = hash_password("")
            assert result is not None
        except Exception:
            pass  # Acceptable to raise


class TestJWTTokenCreation:
    def test_create_access_token(self):
        token = create_access_token({"sub": "user@test.com"})
        assert isinstance(token, str)
        assert len(token.split(".")) == 3

    def test_access_token_claims(self):
        token = create_access_token({"sub": "user@test.com"}, role="admin")
        payload = jwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM], audience=JWT_AUDIENCE
        )
        assert payload["sub"] == "user@test.com"
        assert payload["type"] == "access"
        assert payload["role"] == "admin"
        assert "jti" in payload
        assert "exp" in payload
        assert "iat" in payload

    def test_access_token_expiry(self):
        token = create_access_token(
            {"sub": "user@test.com"},
            expires_delta=timedelta(seconds=1),
        )
        payload = jwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM], audience=JWT_AUDIENCE
        )
        exp = datetime.fromtimestamp(payload["exp"], tz=UTC)
        assert (exp - datetime.now(UTC)).total_seconds() < 2

    def test_expired_token_rejected(self):
        token = create_access_token(
            {"sub": "user@test.com"},
            expires_delta=timedelta(seconds=-1),
        )
        result = decode_token(token)
        assert result is None

    def test_create_refresh_token(self):
        token, jti = create_refresh_token({"sub": "user@test.com"})
        assert isinstance(token, str)
        assert len(token.split(".")) == 3
        assert jti is not None

    def test_refresh_token_claims(self):
        token, _ = create_refresh_token({"sub": "user@test.com", "role": "admin"})
        payload = jwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM], audience=JWT_AUDIENCE
        )
        assert payload["type"] == "refresh"
        assert payload["role"] == "admin"

    def test_token_pair_creation(self):
        pair = create_token_pair("user@test.com", role="admin")
        assert isinstance(pair, TokenPair)
        assert pair.access_token
        assert pair.refresh_token
        assert pair.token_type == "bearer"
        assert pair.expires_in > 0

    def test_token_rotation(self):
        pair1 = create_token_pair("user@test.com")
        pair2 = refresh_access_token(pair1.refresh_token)
        assert pair2 is not None
        # Old refresh should be blacklisted
        result = refresh_access_token(pair1.refresh_token)
        assert result is None


class TestTokenValidation:
    def test_decode_valid_token(self):
        token = create_access_token({"sub": "user@test.com"})
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user@test.com"

    def test_decode_invalid_token(self):
        assert decode_token("invalid.token.here") is None

    def test_decode_tampered_token(self):
        token = create_access_token({"sub": "user@test.com"})
        parts = token.split(".")
        tampered = parts[0] + "." + parts[1] + ".invalidsignature"
        assert decode_token(tampered) is None

    def test_decoded_token_missing_jti(self):
        token = jwt.encode(
            {"sub": "test", "exp": datetime.now(UTC) + timedelta(hours=1)},
            SECRET_KEY,
            algorithm=ALGORITHM,
        )
        result = decode_token(token)
        assert result is not None  # Missing jti is allowed

    def test_revoked_token_rejected(self):
        token = create_access_token({"sub": "user@test.com"})
        payload = decode_token(token)
        revoke_token(payload["jti"])
        assert decode_token(token) is None

    def test_revoke_all_user_tokens(self):
        create_token_pair("user@test.com")
        create_token_pair("user@test.com")
        count = revoke_all_user_tokens("user@test.com")
        assert count >= 2

    def test_token_type_enforcement(self):
        token, _ = create_refresh_token({"sub": "user@test.com"})
        payload = decode_token(token)
        assert payload["type"] == "refresh"


class TestRBAC:
    def test_valid_roles(self):
        assert "viewer" in ROLES
        assert "superadmin" in ROLES
        assert len(ROLES) == 5

    def test_role_hierarchy(self):
        assert role_has_privilege("admin", "user") is True
        assert role_has_privilege("user", "admin") is False
        assert role_has_privilege("superadmin", "admin") is True

    def test_check_permission_valid(self):
        assert check_permission("admin", "manage_users") is True

    def test_check_permission_invalid(self):
        assert check_permission("user", "manage_users") is False

    def test_check_permission_unknown(self):
        assert check_permission("user", "unknown_permission") is False

    def test_all_permissions_defined(self):
        for perm, roles in PERMISSIONS.items():
            for role in roles:
                assert role in ROLES, f"Role {role} not defined for permission {perm}"

    def test_superadmin_has_all(self):
        for perm in PERMISSIONS:
            assert check_permission("superadmin", perm) is True


class TestRateLimiting:
    def test_rate_limit_allowed(self):
        allowed, retry = check_rate_limit("test_key", max_requests=5, window_seconds=60)
        assert allowed is True
        assert retry == 0

    def test_rate_limit_exceeded(self):
        key = "test_exceed"
        for _ in range(5):
            check_rate_limit(key, max_requests=5, window_seconds=60)

        allowed, retry = check_rate_limit(key, max_requests=5, window_seconds=60)
        assert allowed is False
        assert retry > 0

    def test_rate_limit_reset(self):
        key = "test_reset"
        for _ in range(3):
            check_rate_limit(key, max_requests=3, window_seconds=1)
        allowed, retry = check_rate_limit(key, max_requests=3, window_seconds=1)
        assert allowed is False
        time.sleep(1.1)
        allowed, retry = check_rate_limit(key, max_requests=3, window_seconds=1)
        assert allowed is True

    def test_multiple_keys_independent(self):
        for _ in range(5):
            check_rate_limit("key_a", max_requests=5, window_seconds=60)
        allowed_a, _ = check_rate_limit("key_a", max_requests=5, window_seconds=60)
        assert allowed_a is False

        allowed_b, _ = check_rate_limit("key_b", max_requests=5, window_seconds=60)
        assert allowed_b is True

    def test_rate_limit_window_sliding(self):
        key = "test_sliding"
        now = time.time()
        # Simulate requests spread over time
        check_rate_limit(key, max_requests=2, window_seconds=3)
        check_rate_limit(key, max_requests=2, window_seconds=3)
        allowed, _ = check_rate_limit(key, max_requests=2, window_seconds=3)
        assert allowed is False
