
"""
Enterprise Notification Center Service
=========================================
Event-driven notification delivery with:
  - In-app notifications
  - Email delivery
  - WebSocket delivery
  - Webhook delivery
  - Retry queue with exponential backoff
  - Notification history & querying
  - User preferences (per channel & type)
  - Audit logging
  - Prometheus delivery metrics
"""

import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger
from sqlmodel import Session, select

from ..core.audit import get_audit_logger
from ..core.observability import (
    notification_delivery_total,
    notification_delivery_duration_seconds,
)
from .config import DEFAULT_CHANNELS, NotificationConfig
from .models import (
    DeliveryChannel,
    DeliveryStatus,
    Notification,
    NotificationPreference,
    NotificationRetry,
    NotificationSeverity,
    NotificationType,
)


class NotificationService:
    """Enterprise notification delivery service."""

    def __init__(self, config: NotificationConfig | None = None):
        self.config = config or NotificationConfig.from_env()

    # =========================================================================
    # Preference helpers
    # =========================================================================
    def _is_channel_enabled(
        self,
        session: Session,
        user_id: int | None,
        channel: DeliveryChannel,
        notification_type: NotificationType,
    ) -> bool:
        """Check whether a channel is enabled for a user + type."""
        global_default = DEFAULT_CHANNELS.get(channel.value, True)
        if user_id is None:
            return global_default
        pref = session.exec(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.channel == channel,
                NotificationPreference.notification_type == notification_type,
            )
        ).first()
        if pref is not None:
            return pref.enabled
        # Fall back to type-agnostic preference
        pref = session.exec(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.channel == channel,
                NotificationPreference.notification_type == NotificationType.GENERAL,
            )
).first()
        if pref is not None:
            return pref.enabled
        return global_default

    # =========================================================================
    # Delivery primitives
    # =========================================================================
    async def _deliver_in_app(self, notification: Notification) -> bool:
        """In-app delivery is always considered delivered (persisted record)."""
        # In-app is persisted by the notification row itself; mark delivered.
        return True

    async def _deliver_email(self, notification: Notification) -> bool:
        """Deliver via email (best-effort; SMTP optional)."""
        if not self.config.email_enabled:
            return True  # Treated as delivered (disabled channel, no-op)
        if not self.config.smtp_host:
            # No SMTP configured: log and treat as delivered to avoid blocking.
            logger.debug(
                "Email channel enabled but SMTP not configured; skipping",
                notification_id=notification.id,
            )
            return True
        try:
            import smtplib
            from email.mime.text import MIMEText

            msg = MIMEText(notification.body, "plain", "utf-8")
            msg["Subject"] = notification.title
            msg["From"] = self.config.email_from
            # SMTP delivery requires a recipient; if none, skip.
            if not notification.user_id:
                return True
            with smtplib.SMTP(
                self.config.smtp_host, self.config.smtp_port, timeout=10
            ) as server:
                server.starttls()
                if self.config.smtp_user:
                    server.login(self.config.smtp_user, self.config.smtp_password or "")
                server.sendmail(self.config.email_from, [str(notification.user_id)], msg.as_string())
            return True
        except Exception as e:  # pragma: no cover - external SMTP
            logger.warning(f"Email delivery failed for notification {notification.id}: {e}")
            return False

    async def _deliver_websocket(self, notification: Notification) -> bool:
        """Deliver via WebSocket (best-effort; no-op if no subscribers)."""
        if not self.config.websocket_enabled:
            return True
        # WebSocket fan-out is handled by the router's connection manager.
        # Persisted delivery is considered complete; live push is best-effort.
        return True

    async def _deliver_webhook(self, notification: Notification) -> bool:
        """Deliver via generic webhook (best-effort)."""
        if not self.config.webhook_url:
            return True
        try:
            import httpx

            payload = {
                "id": notification.id,
                "title": notification.title,
                "body": notification.body,
                "type": notification.notification_type.value,
                "severity": notification.severity.value,
                "user_id": notification.user_id,
                "ref_type": notification.ref_type,
                "ref_id": notification.ref_id,
                "created_at": notification.created_at.isoformat(),
            }
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self.config.webhook_url, json=payload)
                return resp.status_code < 400
        except Exception as e:  # pragma: no cover - external webhook
            logger.warning(f"Webhook delivery failed for notification {notification.id}: {e}")
            return False

    async def _deliver(self, session: Session, notification: Notification) -> bool:
        """Dispatch a notification to its configured channel."""
        channel = notification.channel
        if channel == DeliveryChannel.IN_APP:
            return await self._deliver_in_app(notification)
        if channel == DeliveryChannel.EMAIL:
            return await self._deliver_email(notification)
        if channel == DeliveryChannel.WEBSOCKET:
            return await self._deliver_websocket(notification)
        if channel == DeliveryChannel.WEBHOOK:
            return await self._deliver_webhook(notification)
        return True

    # =========================================================================
    # Create & dispatch
    # =========================================================================
    async def notify(
        self,
        session: Session,
        *,
        user_id: int | None,
        title: str,
        body: str = "",
        notification_type: NotificationType = NotificationType.GENERAL,
        severity: NotificationSeverity = NotificationSeverity.INFO,
        channel: DeliveryChannel = DeliveryChannel.IN_APP,
        ref_type: str | None = None,
        ref_id: int | None = None,
        metadata: dict[str, Any] | None = None,
        actor: str | None = None,
    ) -> Notification:
        """Create and dispatch a notification."""
        start = time.time()

        notification = Notification(
            user_id=user_id,
            notification_type=notification_type,
            severity=severity,
            title=title,
            body=body,
            channel=channel,
            ref_type=ref_type,
            ref_id=ref_id,
            metadata_json=json.dumps(metadata or {}, default=str),
        )
        session.add(notification)
        session.commit()
        session.refresh(notification)

        # Attempt immediate delivery
        delivered = await self._deliver(session, notification)
        if delivered:
            notification.status = DeliveryStatus.DELIVERED
            notification.sent_at = datetime.now(UTC)
        else:
            notification.status = DeliveryStatus.FAILED
            notification.error_message = "Delivery failed on first attempt"
            self._enqueue_retry(session, notification)
        session.commit()
        session.refresh(notification)

        # Metrics + audit
        duration = time.time() - start
        notification_delivery_total.labels(
            channel=channel.value,
            status=notification.status.value,
        ).inc()
        notification_delivery_duration_seconds.labels(
            channel=channel.value
        ).observe(duration)

        get_audit_logger().log(
            action="notification.dispatch",
            actor=actor or "system",
            resource="notification",
            resource_id=str(notification.id),
            result=notification.status.value,
            details={
                "channel": channel.value,
                "type": notification_type.value,
                "severity": severity.value,
                "user_id": user_id,
            },
        )

        return notification

    # =========================================================================
    # Retry queue
    # =========================================================================
    def _enqueue_retry(self, session: Session, notification: Notification) -> None:
        """Add a notification to the retry queue."""
        retry = NotificationRetry(
            notification_id=notification.id,
            attempt=1,
            next_attempt_at=datetime.now(UTC)
            + timedelta(seconds=self.config.retry_base_delay_seconds),
            last_error=notification.error_message,
        )
        session.add(retry)

    async def process_retry_queue(self, session: Session) -> dict[str, int]:
        """Process due retry entries. Returns {processed, succeeded, failed}."""
        now = datetime.now(UTC)
        due = session.exec(
            select(NotificationRetry)
            .where(
                NotificationRetry.is_completed == False,  # noqa: E712
                NotificationRetry.next_attempt_at <= now,
            )
            .limit(self.config.batch_size)
        ).all()

        processed = succeeded = failed = 0
        for entry in due:
            notification = session.get(Notification, entry.notification_id)
            if notification is None:
                entry.is_completed = True
                session.add(entry)
                processed += 1
                continue

            if entry.attempt >= self.config.max_retries:
                entry.is_completed = True
                notification.status = DeliveryStatus.FAILED
                notification.error_message = "Max retries exceeded"
                session.add(entry)
                session.add(notification)
                processed += 1
                failed += 1
                continue

            delivered = await self._deliver(session, notification)
            if delivered:
                entry.is_completed = True
                notification.status = DeliveryStatus.DELIVERED
                notification.sent_at = datetime.now(UTC)
                succeeded += 1
            else:
                entry.attempt += 1
                backoff = self.config.retry_base_delay_seconds * (2 ** (entry.attempt - 1))
                entry.next_attempt_at = datetime.now(UTC) + timedelta(seconds=backoff)
                entry.last_error = f"Attempt {entry.attempt} failed"
                notification.status = DeliveryStatus.RETRYING
                failed += 1
            session.add(entry)
            session.add(notification)
            processed += 1

        session.commit()
        return {"processed": processed, "succeeded": succeeded, "failed": failed}

    # =========================================================================
    # Query & management
    # =========================================================================
    def list_notifications(
        self,
        session: Session,
        user_id: int | None,
        page: int = 1,
        page_size: int = 20,
        unread_only: bool = False,
    ) -> tuple[list[Notification], int, int]:
        """List notifications for a user with pagination."""
        stmt = select(Notification)
        if user_id is not None:
            stmt = stmt.where(
                (Notification.user_id == user_id) | (Notification.user_id.is_(None))
            )
        if unread_only:
            stmt = stmt.where(Notification.read_at.is_(None))
        total = len(session.exec(stmt).all())
        stmt = stmt.order_by(Notification.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size)
        items = session.exec(stmt).all()
        unread = len(
            session.exec(
                select(Notification).where(
                    Notification.read_at.is_(None),
                    Notification.user_id == user_id,
                )
            ).all()
        )
        return list(items), total, unread

    def mark_read(self, session: Session, notification_id: int, user_id: int) -> Notification | None:
        """Mark a notification as read."""
        notification = session.get(Notification, notification_id)
        if notification is None:
            return None
        if notification.user_id is not None and notification.user_id != user_id:
            return None
        notification.status = DeliveryStatus.READ
        notification.read_at = datetime.now(UTC)
        session.add(notification)
        session.commit()
        session.refresh(notification)
        return notification

    def mark_all_read(self, session: Session, user_id: int) -> int:
        """Mark all of a user's notifications as read."""
        stmt = select(Notification).where(
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
        )
        items = session.exec(stmt).all()
        now = datetime.now(UTC)
        for n in items:
            n.status = DeliveryStatus.READ
            n.read_at = now
            session.add(n)
        session.commit()
        return len(items)

    def get_stats(self, session: Session, user_id: int | None) -> dict[str, Any]:
        """Aggregate notification statistics."""
        stmt = select(Notification)
        if user_id is not None:
            stmt = stmt.where(
                (Notification.user_id == user_id) | (Notification.user_id.is_(None))
            )
        items = session.exec(stmt).all()
        total = len(items)
        unread = sum(1 for n in items if n.read_at is None)
        delivered = sum(1 for n in items if n.status == DeliveryStatus.DELIVERED)
        failed = sum(1 for n in items if n.status == DeliveryStatus.FAILED)
        by_type: dict[str, int] = {}
        by_channel: dict[str, int] = {}
        for n in items:
            by_type[n.notification_type.value] = by_type.get(n.notification_type.value, 0) + 1
            by_channel[n.channel.value] = by_channel.get(n.channel.value, 0) + 1
        return {
            "total": total,
            "unread": unread,
            "delivered": delivered,
            "failed": failed,
            "by_type": by_type,
            "by_channel": by_channel,
        }

    # =========================================================================
    # Preferences
    # =========================================================================
    def set_preference(
        self,
        session: Session,
        user_id: int,
        channel: DeliveryChannel,
        notification_type: NotificationType,
        enabled: bool,
    ) -> NotificationPreference:
        """Create or update a user preference."""
        pref = session.exec(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.channel == channel,
                NotificationPreference.notification_type == notification_type,
            )
        ).first()
        if pref is None:
            pref = NotificationPreference(
                user_id=user_id,
                channel=channel,
                notification_type=notification_type,
                enabled=enabled,
            )
            session.add(pref)
        else:
            pref.enabled = enabled
            session.add(pref)
        session.commit()
        session.refresh(pref)
        return pref

    def list_preferences(self, session: Session, user_id: int) -> list[NotificationPreference]:
        """List all preferences for a user."""
        return list(
            session.exec(
                select(NotificationPreference).where(
                    NotificationPreference.user_id == user_id
                )
            ).all()
        )

    # =========================================================================
    # Health
    # =========================================================================
    def health_check(self) -> dict[str, Any]:
        """Module health check."""
        return {
            "status": "healthy",
            "module": "notifications",
            "enabled": self.config.enabled,
            "email_enabled": self.config.email_enabled,
            "websocket_enabled": self.config.websocket_enabled,
            "max_retries": self.config.max_retries,
            "webhook_configured": bool(self.config.webhook_url),
            "timestamp": datetime.now(UTC).isoformat(),
        }


# Singleton instance
_service: NotificationService | None = None


def get_notification_service() -> NotificationService:
    """Get the global notification service singleton."""
    global _service
    if _service is None:
        _service = NotificationService()
    return _service
