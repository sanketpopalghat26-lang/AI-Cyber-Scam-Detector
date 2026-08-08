"""
Enterprise Security Module
===========================
Implements:
- JWT access & refresh tokens
- Token rotation & revocation
- RBAC (Role-Based Access Control)
- Password hashing with bcrypt
- Session management
- Account lockout (Phase 7: Advanced Authentication)
- JWT issuer/audience/token-version hardening (Phase 7)
"""

import contextlib
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

# =============================================================================
# Password Hashing (using bcrypt directly to avoid passlib compatibility issues)
# =============================================================================
import bcrypt as _bcrypt_lib
from jose import JWTError, jwt
from pydantic import BaseModel

from .config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ACCOUNT_LOCKOUT_DURATION_SECONDS,
    ACCOUNT_LOCKOUT_THRESHOLD,
    ACCOUNT_LOCKOUT_WINDOW_SECONDS,
    ALGORITHM,
    JWT_AUDIENCE,
    JWT_ISSUER,
    SECRET_KEY,
)
from .token_store import get_token_store


def hash_password(password: str) -> str:
    """Hash a password with bcrypt directly (avoiding passlib compatibility issues)."""
    # Truncate to 72 bytes to avoid bcrypt limit
    password_bytes = password.encode("utf-8")[:72]
    salt = _bcrypt_lib.gensalt(rounds=12)
    return _bcrypt_lib.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash using bcrypt directly."""
    password_bytes = plain_password.encode("utf-8")[:72]
    hashed_bytes = hashed_password.encode("utf-8")
    return _bcrypt_lib.checkpw(password_bytes, hashed_bytes)


# =============================================================================
# Token Management
# =============================================================================

# Distributed token store (Redis-backed with in-memory fallback)
# Keeping module-level references for backward compatibility with tests.
_token_blacklist: set[str] = set()
_refresh_token_store: dict[str, dict[str, Any]] = {}

# Configuration
REFRESH_TOKEN_EXPIRE_DAYS = 30
ACCESS_TOKEN_EXPIRE_MINUTES_VAL = ACCESS_TOKEN_EXPIRE_MINUTES or (60 * 24)
TOKEN_VERSION = 1


class TokenPair(BaseModel):
    """Access + refresh token pair."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    """Decoded token payload."""
    sub: str  # Subject (user email)
    exp: datetime
    iat: datetime
    jti: str  # JWT ID (unique token identifier)
    type: str  # "access" or "refresh"
    role: str = "user"  # RBAC role
    scopes: list[str] = []


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
    role: str = "user",
    scopes: list[str] | None = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        data: Claims to include (must contain 'sub')
        expires_delta: Token expiration time
        role: User role for RBAC
        scopes: Permission scopes

    Returns:
        Encoded JWT string
    """
    to_encode = data.copy()
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES_VAL))

    to_encode.update({
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
        "type": "access",
        "role": role,
        "scopes": scopes or [],
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "token_version": TOKEN_VERSION,
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict[str, Any]) -> tuple[str, str]:
    """
    Create a refresh token (long-lived).

    Returns:
        Tuple of (refresh_token_jwt, jti)
    """
    to_encode = data.copy()
    now = datetime.now(UTC)
    expire = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    jti = str(uuid.uuid4())

    to_encode.update({
        "exp": expire,
        "iat": now,
        "jti": jti,
        "type": "refresh",
        "role": data.get("role", "user"),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "token_version": TOKEN_VERSION,
    })
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    # Store refresh token for rotation (distributed store with memory fallback)
    with contextlib.suppress(Exception):
        get_token_store().store_refresh_token(
            jti, data.get("sub") or "", REFRESH_TOKEN_EXPIRE_DAYS * 86400
        )
    _refresh_token_store[jti] = {
        "sub": data.get("sub"),
        "created_at": now.isoformat(),
        "expires_at": expire.isoformat(),
    }

    return token, jti


def decode_token(token: str) -> dict[str, Any] | None:
    """
    Decode and validate a JWT token.
    Returns None if token is invalid or blacklisted.
    """
    try:
        # python-jose validates the `aud` claim against `audience` when
        # verify_aud is enabled (default). Tokens issued before Phase 7 lack
        # the `aud` claim, so we pass `audience` only when the token carries
        # one to remain backward compatible. We intentionally disable the
        # strict aud verification here and enforce it manually below so that
        # legacy tokens without an audience are still accepted.
        claims = jwt.get_unverified_claims(token)
        verify_aud = bool(claims.get("aud"))
        options = {"verify_aud": False}
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options=options,
            audience=JWT_AUDIENCE if verify_aud else None,
        )
        # Validate issuer/audience when present (backward compatible: tokens
        # issued before Phase 7 hardening lack these claims and are still
        # accepted). New tokens include iss/aud and are validated strictly.
        if payload.get("iss") and payload.get("iss") != JWT_ISSUER:
            return None
        audience = payload.get("aud")
        if audience is not None:
            audiences = audience if isinstance(audience, list) else [audience]
            if JWT_AUDIENCE not in audiences:
                return None
        jti = payload.get("jti")
        if jti and (get_token_store().is_blacklisted(jti) or jti in _token_blacklist):
            return None
        return payload
    except JWTError:
        return None


def create_token_pair(
    subject: str,
    role: str = "user",
    scopes: list[str] | None = None,
) -> TokenPair:
    """Create a complete token pair (access + refresh)."""
    access_token = create_access_token(
        {"sub": subject},
        role=role,
        scopes=scopes,
    )
    refresh_token, _ = create_refresh_token({"sub": subject, "role": role})
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES_VAL * 60,
    )


def refresh_access_token(refresh_token: str) -> TokenPair | None:
    """
    Rotate tokens: validate refresh token and issue new pair.
    Implements token rotation for security.
    """
    payload = decode_token(refresh_token)
    if not payload:
        return None
    if payload.get("type") != "refresh":
        return None

    subject = payload.get("sub")
    role = payload.get("role", "user")
    if not subject:
        return None

    # Revoke old refresh token
    jti = payload.get("jti")
    if jti:
        revoke_token(jti)

    # Issue new token pair
    return create_token_pair(subject, role=role)


def revoke_token(jti: str) -> None:
    """Revoke a token by its JWT ID."""
    get_token_store().blacklist_token(jti)
    _token_blacklist.add(jti)
    _refresh_token_store.pop(jti, None)


def revoke_all_user_tokens(subject: str) -> int:
    """Revoke all tokens for a given user."""
    count = 0
    for jti, info in list(_refresh_token_store.items()):
        if info.get("sub") == subject:
            get_token_store().blacklist_token(jti)
            _token_blacklist.add(jti)
            _refresh_token_store.pop(jti, None)
            count += 1
    return count


# =============================================================================
# RBAC (Role-Based Access Control)
# =============================================================================

# Role hierarchy: higher index = more privileges
ROLES = ["viewer", "user", "analyst", "admin", "superadmin"]
ROLE_HIERARCHY = {role: i for i, role in enumerate(ROLES)}

# Permission definitions
PERMISSIONS: dict[str, list[str]] = {
    "predict": ["user", "analyst", "admin", "superadmin"],
    "view_history": ["user", "analyst", "admin", "superadmin"],
    "view_dashboard": ["user", "analyst", "admin", "superadmin"],
    "view_reports": ["user", "analyst", "admin", "superadmin"],
    "manage_users": ["admin", "superadmin"],
    "manage_models": ["admin", "superadmin"],
    "view_audit_logs": ["admin", "superadmin"],
    "manage_system": ["superadmin"],
}


def check_permission(role: str, required_permission: str) -> bool:
    """Check if a role has a specific permission."""
    allowed_roles = PERMISSIONS.get(required_permission, [])
    return role in allowed_roles


def role_has_privilege(role: str, minimum_role: str) -> bool:
    """Check if a role meets or exceeds a minimum role level."""
    user_level = ROLE_HIERARCHY.get(role, -1)
    required_level = ROLE_HIERARCHY.get(minimum_role, 0)
    return user_level >= required_level


# =============================================================================
# Rate Limiting Store (distributed via Redis)
# =============================================================================
_rate_limit_store: dict[str, list[datetime]] = {}


def check_rate_limit(
    key: str,
    max_requests: int = 30,
    window_seconds: int = 60,
) -> tuple[bool, int]:
    """
    Check if a request is rate-limited.
    Returns (is_allowed, retry_after_seconds).
    """
    # Use distributed store when Redis available
    with contextlib.suppress(Exception):
        store = get_token_store()
        if store.is_redis_available():
            return store.rate_limit_check(key, max_requests, window_seconds)

    now = datetime.now(UTC)
    window_start = now - timedelta(seconds=window_seconds)

    # Clean old entries
    if key in _rate_limit_store:
        _rate_limit_store[key] = [
            ts for ts in _rate_limit_store[key] if ts > window_start
        ]
    else:
        _rate_limit_store[key] = []

    # Check limit
    if len(_rate_limit_store[key]) >= max_requests:
        oldest = min(_rate_limit_store[key])
        retry_after = int((oldest + timedelta(seconds=window_seconds) - now).total_seconds())
        return False, max(retry_after, 1)

    # Record request
    _rate_limit_store[key].append(now)
    return True, 0


# =============================================================================
# Account Lockout (Phase 7: Advanced Authentication)
# =============================================================================
# Tracks consecutive failed login attempts per subject (email) to enforce
# lockout after a threshold. In-memory with Redis-backed option via token store.
_account_lockout: dict[str, list[float]] = {}


def record_failed_login(subject: str) -> int:
    """
    Record a failed login attempt for a subject.

    Returns the current number of consecutive failures within the window.
    """
    now = time.time()
    window_start = now - ACCOUNT_LOCKOUT_WINDOW_SECONDS
    attempts = [ts for ts in _account_lockout.get(subject, []) if ts > window_start]
    attempts.append(now)
    _account_lockout[subject] = attempts
    return len(attempts)


def is_account_locked(subject: str) -> bool:
    """
    Check whether an account is currently locked out.

    An account is locked when the number of failed attempts within the
    lockout window reaches the configured threshold AND the lockout
    duration has not yet elapsed since the last failure.
    """
    now = time.time()
    window_start = now - ACCOUNT_LOCKOUT_WINDOW_SECONDS
    attempts = [ts for ts in _account_lockout.get(subject, []) if ts > window_start]
    if len(attempts) < ACCOUNT_LOCKOUT_THRESHOLD:
        return False
    # Locked until the last failure + lockout duration
    last_failure = max(attempts)
    return now < (last_failure + ACCOUNT_LOCKOUT_DURATION_SECONDS)


def get_lockout_remaining(subject: str) -> int:
    """
    Return the number of seconds remaining in the lockout (0 if not locked).
    """
    if not is_account_locked(subject):
        return 0
    now = time.time()
    last_failure = max(_account_lockout.get(subject, [0.0]))
    remaining = int(last_failure + ACCOUNT_LOCKOUT_DURATION_SECONDS - now)
    return max(remaining, 1)


def reset_failed_logins(subject: str) -> None:
    """Reset the failed-login counter for a subject (e.g., after successful login)."""
    _account_lockout.pop(subject, None)


def clear_lockout_state() -> None:
    """Clear all lockout tracking state (used in tests)."""
    _account_lockout.clear()
