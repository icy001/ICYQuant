"""
Rotation notification system.

Dispatches rotation events through
multiple channels including EventBus,
email, webhooks, and Slack (placeholder).
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class RotationEventType(str, Enum):
    """Rotation event types."""

    ROTATION_STARTED = "rotation_started"
    ROTATION_SUCCESS = "rotation_success"
    ROTATION_FAILED = "rotation_failed"
    ROLLBACK_COMPLETED = "rollback_completed"
    CERTIFICATE_EXPIRED = "certificate_expired"
    APPROVAL_PENDING = "approval_pending"
    APPROVAL_APPROVED = "approval_approved"
    APPROVAL_REJECTED = "approval_rejected"
    EXPIRATION_WARNING = "expiration_warning"
    EXPIRATION_CRITICAL = "expiration_critical"


@dataclass
class RotationEvent:
    """
    A rotation notification event.

    Attributes:
        event_id: Unique event identifier.
        event_type: Type of event.
        secret_key: Associated secret key.
        message: Human-readable message.
        severity: Event severity (info, warning, error, critical).
        metadata: Additional event context.
        timestamp: When the event occurred.
    """

    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    event_type: RotationEventType = RotationEventType.ROTATION_STARTED
    secret_key: str = ""
    message: str = ""
    severity: str = "info"
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "secret_key": self.secret_key,
            "message": self.message,
            "severity": self.severity,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat() + "Z",
        }


class RotationNotifier:
    """
    Rotation event notifier.

    Dispatches rotation events through
    configured channels for real-time
    notification of rotation activities.

    Supported channels:
    - EventBus (in-process dispatch)
    - Webhook (HTTP POST)
    - Email (placeholder)
    - Slack (placeholder)

    Usage:
        notifier = RotationNotifier()
        notifier.add_channel("eventbus", eventbus_handler)
        await notifier.notify(event)
    """

    def __init__(
        self,
        eventbus: Optional[Any] = None,
        webhook_url: Optional[str] = None,
        email_config: Optional[Dict[str, Any]] = None,
        slack_webhook: Optional[str] = None,
    ) -> None:
        """
        Initialize notifier.

        Args:
            eventbus: EventBus instance for dispatch.
            webhook_url: Webhook endpoint URL.
            email_config: Email configuration dict.
            slack_webhook: Slack webhook URL.
        """
        self._eventbus = eventbus
        self._webhook_url = webhook_url
        self._email_config = email_config
        self._slack_webhook = slack_webhook
        self._custom_handlers: Dict[str, Callable] = {}
        self._sent_events: List[RotationEvent] = []

    def add_channel(
        self,
        name: str,
        handler: Callable[[RotationEvent], None],
    ) -> None:
        """
        Add a custom notification channel.

        Args:
            name: Channel name.
            handler: Handler function.
        """
        self._custom_handlers[name] = handler

    async def notify(
        self,
        event: RotationEvent,
    ) -> Dict[str, bool]:
        """
        Dispatch an event through all channels.

        Args:
            event: The rotation event to send.

        Returns:
            Dict mapping channel names to success status.
        """
        results: Dict[str, bool] = {}

        # 1. EventBus dispatch
        if self._eventbus:
            results["eventbus"] = await self._dispatch_eventbus(event)

        # 2. Webhook dispatch
        if self._webhook_url:
            results["webhook"] = await self._dispatch_webhook(event)

        # 3. Email
        if self._email_config:
            results["email"] = await self._dispatch_email(event)

        # 4. Slack
        if self._slack_webhook:
            results["slack"] = await self._dispatch_slack(event)

        # 5. Custom handlers
        for name, handler in self._custom_handlers.items():
            try:
                handler(event)
                results[name] = True
            except Exception as e:
                logger.error("Custom handler %s failed: %s", name, e)
                results[name] = False

        # Record event
        self._sent_events.append(event)
        if len(self._sent_events) > 200:
            self._sent_events = self._sent_events[-200:]

        return results

    async def _dispatch_eventbus(
        self,
        event: RotationEvent,
    ) -> bool:
        """Dispatch via EventBus."""
        try:
            if hasattr(self._eventbus, "publish"):
                self._eventbus.publish(
                    topic=f"secrets.rotation.{event.event_type.value}",
                    data=event.to_dict(),
                )
            elif hasattr(self._eventbus, "dispatch"):
                self._eventbus.dispatch(
                    event_type=event.event_type.value,
                    data=event.to_dict(),
                )
            return True
        except Exception as e:
            logger.error("EventBus dispatch failed: %s", e)
            return False

    async def _dispatch_webhook(
        self,
        event: RotationEvent,
    ) -> bool:
        """Dispatch via webhook."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._webhook_url,
                    json=event.to_dict(),
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    return resp.status < 400
        except ImportError:
            logger.warning("aiohttp not available for webhook dispatch")
            return False
        except Exception as e:
            logger.error("Webhook dispatch failed: %s", e)
            return False

    async def _dispatch_email(
        self,
        event: RotationEvent,
    ) -> bool:
        """Dispatch via email (placeholder)."""
        try:
            logger.info(
                "Email notification would be sent: %s - %s",
                event.event_type.value, event.message,
            )
            return True
        except Exception:
            return False

    async def _dispatch_slack(
        self,
        event: RotationEvent,
    ) -> bool:
        """Dispatch via Slack (placeholder)."""
        try:
            logger.info(
                "Slack notification would be sent: %s - %s",
                event.event_type.value, event.message,
            )
            return True
        except Exception:
            return False

    def create_event(
        self,
        event_type: RotationEventType,
        secret_key: str = "",
        message: str = "",
        severity: str = "info",
        **kwargs: Any,
    ) -> RotationEvent:
        """
        Create a rotation event.

        Args:
            event_type: Event type.
            secret_key: Associated secret key.
            message: Event message.
            severity: Event severity level.
            **kwargs: Additional metadata.

        Returns:
            Created RotationEvent.
        """
        return RotationEvent(
            event_type=event_type,
            secret_key=secret_key,
            message=message,
            severity=severity,
            metadata=kwargs,
        )

    def get_recent_events(
        self,
        event_type: Optional[RotationEventType] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get recent notification events."""
        events = list(reversed(self._sent_events))
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return [e.to_dict() for e in events[:limit]]

    def get_stats(self) -> Dict[str, Any]:
        """Get notifier statistics."""
        return {
            "total_events_sent": len(self._sent_events),
            "channels": {
                "eventbus": self._eventbus is not None,
                "webhook": self._webhook_url is not None,
                "email": self._email_config is not None,
                "slack": self._slack_webhook is not None,
                "custom": list(self._custom_handlers.keys()),
            },
        }
