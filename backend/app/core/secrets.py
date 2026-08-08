"""
Enterprise Secrets Management
==============================
Validates and manages all secrets on startup.
Prevents running with default/insecure secrets in production.
"""

import os
import re
import sys


class SecretsValidationError(Exception):
    """Raised when secrets validation fails."""
    pass


class SecretsValidator:
    """Validates all secrets and configuration on startup."""

    MIN_SECRET_KEY_LENGTH = 32
    MIN_PASSWORD_LENGTH = 12
    REQUIRED_ENV_VARS_PRODUCTION = [
        "SECRET_KEY",
        "DATABASE_URL",
        "REDIS_PASSWORD",
    ]
    OPTIONAL_ENV_VARS = [
        "MODEL_PATH",
        "LOG_LEVEL",
        "CORS_ORIGINS",
        "PROMETHEUS_MULTIPROC_DIR",
    ]

    @classmethod
    def validate_all(cls, environment: str | None = None) -> list[str]:
        """
        Validate all secrets and configuration.
        Returns list of warnings. Raises on critical failures.
        """
        env = environment or os.getenv("APP_ENV", "development")
        warnings: list[str] = []

        # Validate SECRET_KEY
        secret_key = os.getenv("SECRET_KEY", "")
        if not secret_key:
            if env == "production":
                raise SecretsValidationError(
                    "SECRET_KEY is not set. Generate a strong key with: "
                    "openssl rand -hex 32"
                )
            warnings.append(
                "WARNING: SECRET_KEY is not set. Using default (development only)."
            )
        elif len(secret_key) < cls.MIN_SECRET_KEY_LENGTH:
            warnings.append(
                f"WARNING: SECRET_KEY is too short ({len(secret_key)} chars). "
                f"Minimum recommended: {cls.MIN_SECRET_KEY_LENGTH} chars."
            )

        # Independent check so a short-but-obvious default still fails closed in production.
        if secret_key in {"changeme123", "secret", "dev-secret-key-do-not-use-in-prod"}:
            if env == "production":
                raise SecretsValidationError(
                    "SECRET_KEY is set to an obvious default value. "
                    "This is a critical security risk."
                )
            warnings.append("WARNING: SECRET_KEY is a known default value.")

        # Validate password complexity (check for common weak patterns)
        if secret_key and re.match(r"^[a-z0-9]+$", secret_key, re.IGNORECASE):
            warnings.append(
                "WARNING: SECRET_KEY is alphanumeric only. "
                "Consider using a mix of symbols, numbers, and letters."
            )

        # Validate DATABASE_URL
        db_url = os.getenv("DATABASE_URL", "")
        if not db_url and env == "production":
            raise SecretsValidationError("DATABASE_URL is not set for production.")
        if db_url and "localhost" in db_url and env == "production":
            warnings.append("WARNING: DATABASE_URL points to localhost in production.")

        # Validate REDIS_PASSWORD
        redis_password = os.getenv("REDIS_PASSWORD", "")
        if not redis_password and env == "production":
            warnings.append(
                "WARNING: REDIS_PASSWORD is not set. Redis will be unsecured."
            )

        # Check for required env vars in production
        if env == "production":
            for var in cls.REQUIRED_ENV_VARS_PRODUCTION:
                if not os.getenv(var):
                    raise SecretsValidationError(
                        f"Required environment variable {var} is not set."
                    )

        # Check for insecure SQLite in production
        if db_url and db_url.startswith("sqlite") and env == "production":
            warnings.append(
                "WARNING: Using SQLite in production is not recommended. "
                "Use PostgreSQL instead."
            )

        return warnings

    @classmethod
    def generate_secret_key(cls, length: int = 64) -> str:
        """Generate a cryptographically secure secret key."""
        import secrets as sec
        return sec.token_hex(length // 2)

    @classmethod
    def validate_password_strength(cls, password: str) -> list[str]:
        """
        Validate password strength.
        Returns list of missing requirements.
        """
        errors: list[str] = []

        if len(password) < cls.MIN_PASSWORD_LENGTH:
            errors.append(
                f"Password must be at least {cls.MIN_PASSWORD_LENGTH} characters long."
            )

        if not re.search(r"[A-Z]", password):
            errors.append("Password must contain at least one uppercase letter.")

        if not re.search(r"[a-z]", password):
            errors.append("Password must contain at least one lowercase letter.")

        if not re.search(r"\d", password):
            errors.append("Password must contain at least one digit.")

        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            errors.append("Password must contain at least one special character.")

        if re.search(r"(.)\1{2,}", password):
            errors.append("Password must not contain repeated characters (3+ times).")

        common_patterns = [
            "password", "12345", "qwerty", "abc123", "admin",
            "letmein", "welcome", "monkey", "dragon", "master",
        ]
        if any(pattern in password.lower() for pattern in common_patterns):
            errors.append("Password contains a common pattern.")

        return errors


def validate_on_startup() -> None:
    """Called during application startup to validate configuration."""
    warnings = SecretsValidator.validate_all()
    for warning in warnings:
        print(f"[SECURITY] {warning}", file=sys.stderr)

    db_url = os.getenv("DATABASE_URL", "")
    if db_url and not db_url.startswith("sqlite"):
        print("[SECURITY] Database URL detected. Verifying connection string safety...")
        if "?" not in db_url:
            print(
                "[SECURITY] WARNING: Database URL has no SSL parameters. "
                "Consider adding ?sslmode=require for production."
            )
