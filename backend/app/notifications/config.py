"""
Enterprise Notification Center Configuration
===============================================
Centralized configuration for the notification service.
All settings loaded from environment variables.
"""

import os
from dataclasses import dataclass, field


@dataclass
class NotificationConfig:
    """Configuration for the Enterprise Notification Center."""

    enabled: bool = os.getenv("ENABLE_NOTIFICATIONS", "true").lower() == "true"

    # Delivery channels
    email_enabled: bool = os.getenv("NOTIFICATIONS_EMAIL_ENABLED", "true").lower() == "true"
    websocket_enabled: bool = os.getenv(
        "NOTIFICATIONS_WEBSOCKET_ENABLED", "true"
    ).lower() == "true"
    in_app_enabled: bool = os.getenv("NOTIFICATIONS_INAPP_ENABLED", "true").lower() == "true"

    # Retry / batching
    max_retries: int = int(os.getenv("NOTIFICATIONS_MAX_RETRIES", "5"))
    retry_base_delay_seconds: int = int(
        os.getenv("NOTIFICATIONS_RETRY_BASE_DELAY_SECONDS", "2")
    )
    batch_size: int = int(os.getenv("NOTIFICATIONS_BATCH_SIZE", "50"))

    # History / retention
    history_limit: int = int(os.getenv("NOTIFICATIONS_HISTORY_LIMIT", "200"))
    retention_days: int = int(os.getenv("NOTIFICATIONS_RETENTION_DAYS", "90"))

    # Email SMTP (optional; used only when email_enabled and endpoint set)
    smtp_host: str | None = os.getenv("NOTIFICATIONS_SMTP_HOST")
    smtp_port: int = int(os.getenv("NOTIFICATIONS_SMTP_PORT", "587"))
    smtp_user: str | None = os.getenv("NOTIFICATIONS_SMTP_USER")
    smtp_password: str | None = os.getenv("NOTIFICATIONS_SMTP_PASSWORD")
    email_from: str = os.getenv("NOTIFICATIONS_EMAIL_FROM", "no-reply@example.com")

    # Webhook endpoint (generic delivery)
    webhook_url: str | None = os.getenv("NOTIFICATIONS_WEBHOOK_URL")

    # Rate limiting
    rate_limit_max: int = int(os.getenv("NOTIFICATIONS_RATE_LIMIT_MAX", "100"))
    rate_limit_window: int = int(os.getenv("NOTIFICATIONS_RATE_LIMIT_WINDOW", "60"))

    @classmethod
    def from_env(cls) -> "NotificationConfig":
        """Create configuration from environment variables."""
        return cls()


# Default preference map: channel -> enabled
DEFAULT_CHANNELS: dict[str, bool] = {
    "in_app": True,
    "email": True,
    "websocket": True,
}
