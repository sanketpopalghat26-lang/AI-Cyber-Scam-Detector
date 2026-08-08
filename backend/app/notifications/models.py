"""
Enterprise Notification Center Models
========================================
SQLModel ORM models for notification records, delivery channels,
user preferences, and the delivery retry queue.
"""

import enum
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)


class NotificationType(str, enum.Enum):
    """Type of notification."""

    ALERT = "alert"
    PREDICTION = "prediction"
    THREAT = "threat"
    INVESTIGATION = "investigation"
    SYSTEM = "system"
    SECURITY = "security"
    GENERAL = "general"


class NotificationSeverity(str, enum.Enum):
    """Severity level of a notification."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DeliveryChannel(str, enum.Enum):
    """Delivery channel for a notification."""

    IN_APP = "in_app"
    EMAIL = "email"
    WEBSOCKET = "websocket"
    WEBHOOK = "webhook"


class DeliveryStatus(str, enum.Enum):
    """Delivery status of a notification."""

    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    READ = "read"


class Notification(SQLModel, table=True):
    """
    A single notification record.
    """

    __tablename__ = "notifications"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    notification_type: NotificationType = Field(
        default=NotificationType.GENERAL, index=True
    )
    severity: NotificationSeverity = Field(
        default=NotificationSeverity.INFO, index=True
    )
    title: str = Field(nullable=False, max_length=500)
    body: str = Field(default="", max_length=10000)
    channel: DeliveryChannel = Field(
        default=DeliveryChannel.IN_APP, index=True
    )
    status: DeliveryStatus = Field(default=DeliveryStatus.PENDING, index=True)
    # Reference to the entity that triggered the notification
    ref_type: str | None = Field(default=None, max_length=100, index=True)
    ref_id: int | None = Field(default=None, index=True)
    metadata_json: str = Field(default="{}", max_length=10000)
    retry_count: int = Field(default=0, ge=0)
    error_message: str | None = Field(default=None, max_length=2000)
    created_at: datetime = Field(default_factory=_utcnow, index=True)
    updated_at: datetime | None = Field(
        default=None, sa_column_kwargs={"onupdate": _utcnow}
    )
    sent_at: datetime | None = Field(default=None)
    read_at: datetime | None = Field(default=None)


class NotificationPreference(SQLModel, table=True):
    """
    Per-user delivery preferences per channel & type.
    """

    __tablename__ = "notification_preferences"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)
    channel: DeliveryChannel = Field(
        default=DeliveryChannel.IN_APP, index=True, nullable=False
    )
    notification_type: NotificationType = Field(
        default=NotificationType.GENERAL, index=True, nullable=False
    )
    enabled: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime | None = Field(
        default=None, sa_column_kwargs={"onupdate": _utcnow}
    )


class NotificationRetry(SQLModel, table=True):
    """
    Delivery retry queue entry for failed notifications.
    """

    __tablename__ = "notification_retries"

    id: int | None = Field(default=None, primary_key=True)
    notification_id: int = Field(
        foreign_key="notifications.id", index=True, nullable=False
    )
    attempt: int = Field(default=1, ge=1)
    next_attempt_at: datetime = Field(default_factory=_utcnow, index=True)
    last_error: str | None = Field(default=None, max_length=2000)
    is_completed: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime | None = Field(
        default=None, sa_column_kwargs={"onupdate": _utcnow}
    )
