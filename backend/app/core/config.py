
"""
Enterprise Configuration
=========================
Centralized configuration with environment variable support.
All secrets and settings are loaded from environment in production.
"""

import os

# =============================================================================
# Core Application Settings
# =============================================================================
APP_NAME = "AI Cyber Scam Detector"
APP_VERSION = os.getenv("APP_VERSION", "2.0.0")
APP_ENV = os.getenv("APP_ENV", "development")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# =============================================================================
# Security Settings
# =============================================================================
_SECRET_KEY_DEFAULT = "dev-secret-key-do-not-use-in-prod"
SECRET_KEY = os.getenv("SECRET_KEY", _SECRET_KEY_DEFAULT)
if SECRET_KEY == _SECRET_KEY_DEFAULT and os.getenv("APP_ENV", "development") == "production":
    from .secrets import SecretsValidator
    SECRET_KEY = SecretsValidator.generate_secret_key(64)
    import warnings
    warnings.warn("Auto-generated SECRET_KEY. Set SECRET_KEY environment variable for consistency across restarts.", stacklevel=2)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))

# CORS
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://localhost:8000"
).split(",")

# JWT issuer/audience (hardening)
JWT_ISSUER = os.getenv("JWT_ISSUER", "ai-cyber-scam-detector")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "ai-cyber-scam-detector-api")

# Account lockout policy
ACCOUNT_LOCKOUT_THRESHOLD = int(os.getenv("ACCOUNT_LOCKOUT_THRESHOLD", "5"))
ACCOUNT_LOCKOUT_WINDOW_SECONDS = int(os.getenv("ACCOUNT_LOCKOUT_WINDOW_SECONDS", "900"))
ACCOUNT_LOCKOUT_DURATION_SECONDS = int(os.getenv("ACCOUNT_LOCKOUT_DURATION_SECONDS", "900"))

# Rate Limiting
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX", "100"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

# Password policy
PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "12"))
PASSWORD_REQUIRE_SPECIAL = os.getenv("PASSWORD_REQUIRE_SPECIAL", "true").lower() == "true"
PASSWORD_REQUIRE_UPPER = os.getenv("PASSWORD_REQUIRE_UPPER", "true").lower() == "true"
PASSWORD_REQUIRE_DIGIT = os.getenv("PASSWORD_REQUIRE_DIGIT", "true").lower() == "true"

# =============================================================================
# Database Settings
# =============================================================================
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dev.db")
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "20"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "40"))
DB_ECHO = os.getenv("DB_ECHO", "false").lower() == "true"

# =============================================================================
# Redis / Cache Settings
# =============================================================================
REDIS_URL = os.getenv("REDIS_URL", "")
CACHE_DEFAULT_TTL = int(os.getenv("CACHE_DEFAULT_TTL", "300"))  # 5 minutes
CACHE_PREDICTION_TTL = int(os.getenv("CACHE_PREDICTION_TTL", "600"))  # 10 minutes

# =============================================================================
# Model Settings
# =============================================================================
MODEL_PATH = os.getenv("MODEL_PATH", "/app/model/best_model.joblib")

# =============================================================================
# Observability Settings
# =============================================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
OTLP_ENDPOINT = os.getenv("OTLP_ENDPOINT", "")
PROMETHEUS_MULTIPROC_DIR = os.getenv("PROMETHEUS_MULTIPROC_DIR", "")

# =============================================================================
# Monitoring and Alerting
# =============================================================================
SLOW_REQUEST_THRESHOLD_MS = int(os.getenv("SLOW_REQUEST_THRESHOLD_MS", "1000"))
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")

# =============================================================================
# Audit Settings
# =============================================================================
AUDIT_LOG_DIR = os.getenv("AUDIT_LOG_DIR", "logs/audit")
AUDIT_RETENTION_DAYS = int(os.getenv("AUDIT_RETENTION_DAYS", "90"))

# =============================================================================
# Deployment Settings
# =============================================================================
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")
TRUSTED_PROXIES = os.getenv("TRUSTED_PROXIES", "").split(",")

# =============================================================================
# Feature Flags
# =============================================================================
ENABLE_METRICS = os.getenv("ENABLE_METRICS", "true").lower() == "true"
ENABLE_TRACING = os.getenv("ENABLE_TRACING", "false").lower() == "true"
ENABLE_CACHE = os.getenv("ENABLE_CACHE", "true").lower() == "true"
ENABLE_RATE_LIMITING = os.getenv("ENABLE_RATE_LIMITING", "true").lower() == "true"

# =============================================================================
# Enterprise Module Feature Flags
# =============================================================================
ENABLE_THREAT_INTEL = os.getenv("ENABLE_THREAT_INTEL", "true").lower() == "true"
ENABLE_EXPLAINABILITY = os.getenv("ENABLE_EXPLAINABILITY", "true").lower() == "true"
ENABLE_INVESTIGATION = os.getenv("ENABLE_INVESTIGATION", "true").lower() == "true"
ENABLE_MONITORING = os.getenv("ENABLE_MONITORING", "true").lower() == "true"
ENABLE_CHAT = os.getenv("ENABLE_CHAT", "true").lower() == "true"
ENABLE_NOTIFICATIONS = os.getenv("ENABLE_NOTIFICATIONS", "true").lower() == "true"
ENABLE_EXECUTIVE = os.getenv("ENABLE_EXECUTIVE", "true").lower() == "true"

# =============================================================================
# Helper to get all config as dict
# =============================================================================
def get_all_config() -> dict[str, object]:
    """Return all configuration as a dictionary (excluding secrets)."""
    return {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "app_env": APP_ENV,
        "debug": DEBUG,
        "algorithm": ALGORITHM,
        "access_token_expire_minutes": ACCESS_TOKEN_EXPIRE_MINUTES,
        "refresh_token_expire_days": REFRESH_TOKEN_EXPIRE_DAYS,
        "cors_origins": CORS_ORIGINS,
        "rate_limit_max": RATE_LIMIT_MAX_REQUESTS,
        "rate_limit_window": RATE_LIMIT_WINDOW_SECONDS,
        "password_min_length": PASSWORD_MIN_LENGTH,
        "db_pool_size": DB_POOL_SIZE,
        "db_max_overflow": DB_MAX_OVERFLOW,
        "cache_default_ttl": CACHE_DEFAULT_TTL,
        "cache_prediction_ttl": CACHE_PREDICTION_TTL,
        "log_level": LOG_LEVEL,
        "slow_request_threshold_ms": SLOW_REQUEST_THRESHOLD_MS,
        "audit_retention_days": AUDIT_RETENTION_DAYS,
        "enable_metrics": ENABLE_METRICS,
        "enable_tracing": ENABLE_TRACING,
        "enable_cache": ENABLE_CACHE,
        "enable_rate_limiting": ENABLE_RATE_LIMITING,
    }

