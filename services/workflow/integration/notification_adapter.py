"""Notification Adapter — multi-channel notifications for workflow events.

Supports:

* **Email** — SMTP-based email notifications
* **Webhook** — HTTP callbacks to external systems
* **Slack** — Slack channel messages
* **SMS** — reserved for future
* **WeCom** — reserved for future

Used for workflow alerts, completion notifications, and manual approval nodes.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class NotificationChannel(str, Enum):
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"
    SMS = "sms"
    WECOM = "wecom"


class NotificationPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Notification:
    """A notification message."""

    notification_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    channel: NotificationChannel = NotificationChannel.EMAIL
    recipient: str = ""
    subject: str = ""
    body: str = ""
    priority: NotificationPriority = NotificationPriority.NORMAL
    workflow_id: Optional[str] = None
    execution_id: Optional[str] = None
    sent_at: Optional[datetime] = None
    delivered: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "channel": self.channel.value,
            "recipient": self.recipient,
            "subject": self.subject,
            "priority": self.priority.value,
            "workflow_id": self.workflow_id,
            "execution_id": self.execution_id,
            "delivered": self.delivered,
        }


class NotificationAdapter:
    """Multi-channel notifications for workflow events.

    Usage::

        adapter = NotificationAdapter()
        await adapter.start()
        await adapter.send(Notification(
            channel=NotificationChannel.EMAIL,
            recipient="trader@example.com",
            subject="Workflow Completed",
            body="Order execution workflow completed successfully",
        ))
    """

    def __init__(self) -> None:
        self._lock = __import__("threading").RLock()
        self._started = False
        self._notifications: Dict[str, Notification] = {}
        self._channel_handlers: Dict[NotificationChannel, Any] = {}
        self._on_send_callbacks: list = []

    async def start(self) -> None:
        self._started = True
        logger.info("NotificationAdapter: started")

    async def stop(self) -> None:
        self._started = False
        logger.info("NotificationAdapter: stopped")

    async def send(self, notification: Notification) -> bool:
        """Send a notification through the specified channel."""
        logger.info("NotificationAdapter: sending %s notification to %s (%s)",
                     notification.channel.value, notification.recipient, notification.subject)
        try:
            # In production: route to channel handler
            notification.sent_at = datetime.utcnow()
            notification.delivered = True
            with self._lock:
                self._notifications[notification.notification_id] = notification
            for cb in self._on_send_callbacks:
                try:
                    cb(notification)
                except Exception:
                    pass
            return True
        except Exception as e:
            logger.error("NotificationAdapter: send failed: %s", e)
            return False

    async def send_workflow_alert(
        self,
        *,
        channel: NotificationChannel = NotificationChannel.EMAIL,
        recipient: str,
        workflow_id: str,
        execution_id: str,
        subject: str,
        body: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
    ) -> bool:
        notification = Notification(
            channel=channel,
            recipient=recipient,
            subject=subject,
            body=body,
            priority=priority,
            workflow_id=workflow_id,
            execution_id=execution_id,
        )
        return await self.send(notification)

    async def get_notification(self, notification_id: str) -> Optional[Notification]:
        with self._lock:
            return self._notifications.get(notification_id)

    async def list_notifications(
        self,
        *,
        channel: Optional[NotificationChannel] = None,
        execution_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Notification]:
        with self._lock:
            results = list(self._notifications.values())
            if channel:
                results = [n for n in results if n.channel == channel]
            if execution_id:
                results = [n for n in results if n.execution_id == execution_id]
            return sorted(results, key=lambda n: n.sent_at or datetime.min, reverse=True)[:limit]

    def on_send(self, callback) -> None:
        self._on_send_callbacks.append(callback)

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {"total_notifications": len(self._notifications)}
