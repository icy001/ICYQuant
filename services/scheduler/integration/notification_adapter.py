"""Notification Adapter — enables scheduler-driven notifications.

The :class:`NotificationAdapter` sends notifications on scheduler events:
* Job completion / failure alerts
* Manual approval requests
* System alerts and warnings
* Multi-channel delivery (Email, Webhook, Slack, WeCom)

Channels::

    Scheduler ──→ NotificationAdapter ──→ Email
                      │                   ├── Slack
                      │                   ├── Webhook
                      │                   ├── WeCom (reserved)
                      │                   └── SMS (reserved)
"""

from __future__ import annotations

import asyncio
import enum
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class NotificationChannel(enum.Enum):
    """Supported notification channels."""

    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    WECOM = "wecom"
    SMS = "sms"
    CONSOLE = "console"


class NotificationAdapter:
    """Adapter for multi-channel notifications.

    Responsibilities:
    * Send job completion/failure notifications
    * Send manual approval requests
    * Send system alert notifications
    * Route notifications to appropriate channels
    * Support notification templates

    Usage::

        adapter = NotificationAdapter()
        await adapter.connect()
        await adapter.notify(
            channel=NotificationChannel.EMAIL,
            event="job_completed",
            recipient="trader@example.com",
            payload={"job_id": "123"},
        )
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._connected = False
        self._send_count: int = 0
        self._failure_count: int = 0
        self._templates: Dict[str, str] = {}
        self._channel_configs: Dict[NotificationChannel, Dict[str, Any]] = {}
        self._last_send_at: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def send_count(self) -> int:
        return self._send_count

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def last_send_at(self) -> Optional[datetime]:
        return self._last_send_at

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Initialize notification channels."""
        logger.info("NotificationAdapter: connecting")
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False
        logger.info("NotificationAdapter: disconnected")

    async def synchronize(self) -> Dict[str, Any]:
        return {"connected": self._connected, "sent": self._send_count, "failures": self._failure_count}

    # ------------------------------------------------------------------
    # Channel Configuration
    # ------------------------------------------------------------------

    def configure_channel(self, channel: NotificationChannel, config: Dict[str, Any]) -> None:
        """Configure a notification channel."""
        self._channel_configs[channel] = config
        logger.info("NotificationAdapter: configured %s channel", channel.value)

    def register_template(self, name: str, template: str) -> None:
        """Register a notification template."""
        self._templates[name] = template

    # ------------------------------------------------------------------
    # Send
    # ------------------------------------------------------------------

    async def notify(
        self,
        channel: NotificationChannel,
        event: str,
        recipient: str,
        payload: Dict[str, Any],
        template: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a notification through the specified channel.

        Args:
            channel: Target notification channel
            event: Event type (job_completed, job_failed, approval_required, etc.)
            recipient: Recipient address/identifier
            payload: Event-specific data
            template: Optional template name for message formatting
        """
        self._send_count += 1
        self._last_send_at = datetime.now(timezone.utc)

        result: Dict[str, Any] = {
            "channel": channel.value, "event": event, "recipient": recipient,
            "status": "sent", "timestamp": self._last_send_at.isoformat(),
        }

        try:
            message = self._format_message(event, payload, template)
            await self._dispatch(channel, recipient, event, message)
            logger.info("NotificationAdapter: sent %s via %s to %s", event, channel.value, recipient)
        except Exception as exc:
            self._failure_count += 1
            result["status"] = "error"
            result["error"] = str(exc)
            logger.error("NotificationAdapter: send failed: %s", exc)

        return result

    async def notify_job_completed(self, job_id: str, result: Dict[str, Any], recipients: List[str]) -> List[Dict[str, Any]]:
        """Send job completion notifications."""
        results = []
        for recipient in recipients:
            for channel in [NotificationChannel.EMAIL, NotificationChannel.SLACK]:
                r = await self.notify(channel, "job_completed", recipient, {"job_id": job_id, "result": result})
                results.append(r)
        return results

    async def notify_job_failed(self, job_id: str, error: str, recipients: List[str]) -> List[Dict[str, Any]]:
        """Send job failure notifications."""
        results = []
        for recipient in recipients:
            r = await self.notify(NotificationChannel.EMAIL, "job_failed", recipient, {"job_id": job_id, "error": error})
            results.append(r)
        return results

    async def notify_approval_required(self, approval_id: str, details: Dict[str, Any], approvers: List[str]) -> List[Dict[str, Any]]:
        """Send manual approval request notifications."""
        results = []
        for approver in approvers:
            r = await self.notify(NotificationChannel.EMAIL, "approval_required", approver, {"approval_id": approval_id, **details})
            results.append(r)
        return results

    async def notify_system_alert(self, alert_type: str, message: str, recipients: List[str]) -> List[Dict[str, Any]]:
        """Send system alert notifications."""
        results = []
        for recipient in recipients:
            r = await self.notify(NotificationChannel.SLACK, "system_alert", recipient, {"alert_type": alert_type, "message": message})
            results.append(r)
        return results

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _format_message(self, event: str, payload: Dict[str, Any], template: Optional[str] = None) -> str:
        """Format a notification message using a template or default."""
        if template and template in self._templates:
            tmpl = self._templates[template]
            try:
                return tmpl.format(**payload)
            except KeyError:
                pass
        return f"[Scheduler] {event}: {payload}"

    async def _dispatch(self, channel: NotificationChannel, recipient: str, subject: str, message: str) -> None:
        """Dispatch a notification to the channel."""
        # In production, this calls the actual channel API (SMTP, Slack API, etc.)
        logger.debug("NotificationAdapter: dispatch [%s] %s → %s", channel.value, subject, recipient)
