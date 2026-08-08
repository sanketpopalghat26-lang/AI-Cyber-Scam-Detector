"""
Enterprise Notification Center Schemas
=========================================
Pydantic request/response models for the notification service.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .models import (
    DeliveryChannel,
    DeliveryStatus,
    NotificationSeverity,
    NotificationType,
)


def _utcnow() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)


# =============================================================================
# Request Models
# =============================================================================


class NotificationCreate(BaseModel):
    """Create a new notification."""

    user_id: int | None = Field(default=None, description="Target user ID")
    notification_type: NotificationType = Field(default=NotificationType.GENERAL)
    severity: NotificationSeverity = Field(default=NotificationSeverity.INFO)
    title: str = Field(..., min_length=1, max_length=500, description="Notification title")
    body: str = Field(default="", max_length=10000)
    channel: DeliveryChannel = Field(default=DeliveryChannel.IN_APP)
    ref_type: str | None = Field(default=None, max_length=100)
    ref_id: int | None = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PreferenceUpdate(BaseModel):
    """Update a user's notification preference for a channel/type."""

    channel: DeliveryChannel
    notification_type: NotificationType = Field(default=NotificationType.GENERAL)
    enabled: bool


# =============================================================================
# Response Models
# =============================================================================


class NotificationOut(BaseModel):
    """A notification record in responses."""

    id: int
    user_id: int | None = None
    notification_type: NotificationType
    severity: NotificationSeverity
    title: str
    body: str
    channel: DeliveryChannel
    status: DeliveryStatus
    ref_type: str | None = None
    ref_id: int | None = None
    retry_count: int = Field(default=0)
    created_at: str
    sent_at: str | None = None
    read_at: str | None = None

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    """Paginated list of notifications."""

    items: list[NotificationOut]
    total: int
    page: int
    page_size: int
    unread_count: int


class PreferenceOut(BaseModel):
    """A user notification preference."""

    id: int
    user_id: int
    channel: DeliveryChannel
    notification_type: NotificationType
    enabled: bool

    model_config = ConfigDict(from_attributes=True)


class NotificationStats(BaseModel):
    """Aggregate notification statistics."""

    total: int = Field(..., ge=0)
    unread: int = Field(..., ge=0)
    delivered: int = Field(..., ge=0)
    failed: int = Field(..., ge=0)
    by_type: dict[str, int] = Field(default_factory=dict)
    by_channel: dict[str, int] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=_utcnow)
