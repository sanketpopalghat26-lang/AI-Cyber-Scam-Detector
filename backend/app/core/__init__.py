"""
Enterprise Core Package
=======================
Enterprise-grade security, monitoring, and reliability infrastructure.
"""

from .audit import AuditLogger, AuditMiddleware, get_audit_logger
from .config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    DATABASE_URL,
    SECRET_KEY,
)
from .middleware import register_middleware
from .secrets import SecretsValidationError, SecretsValidator, validate_on_startup
from .security import (
    TokenPair,
    TokenPayload,
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

__all__ = [
    # Config
    "DATABASE_URL",
    "SECRET_KEY",
    "ALGORITHM",
    "ACCESS_TOKEN_EXPIRE_MINUTES",

    # Secrets
    "SecretsValidator",
    "validate_on_startup",
    "SecretsValidationError",

    # Security
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "create_token_pair",
    "refresh_access_token",
    "revoke_token",
    "revoke_all_user_tokens",
    "check_permission",
    "role_has_privilege",
    "check_rate_limit",
    "TokenPair",
    "TokenPayload",

    # Middleware
    "register_middleware",

    # Audit
    "AuditLogger",
    "get_audit_logger",
    "AuditMiddleware",
]

