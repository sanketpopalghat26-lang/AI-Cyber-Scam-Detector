"""
Backward-compatible re-export of security module.
All enterprise functionality has moved to backend/app/core/security.py
"""
from .core.security import (
    TokenPair,
    TokenPayload,
    check_permission,
    check_rate_limit,
    create_access_token,
    create_refresh_token,
    create_token_pair,
    hash_password,
    refresh_access_token,
    revoke_all_user_tokens,
    revoke_token,
    role_has_privilege,
    verify_password,
)
from .core.security import (
    decode_token as decode_access_token,
)

__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_access_token",
    "create_token_pair",
    "refresh_access_token",
    "revoke_token",
    "revoke_all_user_tokens",
    "check_permission",
    "role_has_privilege",
    "check_rate_limit",
    "TokenPair",
    "TokenPayload",
]

