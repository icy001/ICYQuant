"""Alert Notifier.

Multi-channel notification system for alerts.

Supports:
- Email
- Webhook
- Slack
- WeChat Work (企业微信) - extensible
- DingTalk (钉钉) - extensible

Usage::

    notifier = AlertNotifier()
    notifier.add_channel(NotificationChannel(
        name="ops_slack",
        channel_type="slack",
        config={"webhook_url": "https://hooks.slack.com/..."},
    ))
    notifier.send(alert, channel_names=["ops_slack"])
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from services.monitoring.alert.rule_engine import Alert, AlertSeverity


class NotificationChannel(str, Enum):
    """Supported notification channel types."""

    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"
    WECHAT_WORK = "wechat_work"
    DINGTALK = "dingtalk"
    CONSOLE = "console"


@dataclass
class ChannelConfig:
    """Configuration for a notification channel."""

    name: str
    channel_type: NotificationChannel
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    severity_filter: Optional[List[AlertSeverity]] = None

    def accepts_severity(self, severity: AlertSeverity) -> bool:
        """Check if this channel accepts the given severity."""
        if self.severity_filter is None:
            return True
        return severity in self.severity_filter


@dataclass
class Notification:
    """A notification sent through a channel."""

    channel: str
    channel_type: NotificationChannel
    alert_id: str
    success: bool
    timestamp: float = field(default_factory=time.time)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "channel": self.channel,
            "channel_type": self.channel_type.value,
            "alert_id": self.alert_id,
            "success": self.success,
            "timestamp": self.timestamp,
            "error": self.error,
        }


class AlertNotifier:
    """Sends alerts through configured notification channels.

    Each channel has its own config and can filter by severity.
    """

    def __init__(self) -> None:
        self._channels: Dict[str, ChannelConfig] = {}
        self._senders: Dict[NotificationChannel, Callable] = {}
        self._history: List[Notification] = []
        self._register_default_senders()

    def add_channel(self, channel: ChannelConfig) -> None:
        """Register a notification channel."""
        self._channels[channel.name] = channel

    def remove_channel(self, name: str) -> None:
        """Remove a notification channel."""
        self._channels.pop(name, None)

    def get_channel(self, name: str) -> Optional[ChannelConfig]:
        """Get channel config by name."""
        return self._channels.get(name)

    def list_channels(self) -> List[ChannelConfig]:
        """List all configured channels."""
        return list(self._channels.values())

    def send(
        self,
        alert: Alert,
        channel_names: Optional[List[str]] = None,
    ) -> List[Notification]:
        """Send an alert to specified channels (or all if not specified)."""
        targets = (
            [self._channels[n] for n in channel_names if n in self._channels]
            if channel_names
            else list(self._channels.values())
        )

        notifications: List[Notification] = []
        for ch in targets:
            if not ch.enabled:
                continue
            if not ch.accepts_severity(alert.severity):
                continue

            sender = self._senders.get(ch.channel_type)
            if sender is None:
                notifications.append(Notification(
                    channel=ch.name,
                    channel_type=ch.channel_type,
                    alert_id=alert.alert_id,
                    success=False,
                    error=f"No sender for channel type: {ch.channel_type.value}",
                ))
                continue

            try:
                sender(alert, ch.config)
                notifications.append(Notification(
                    channel=ch.name,
                    channel_type=ch.channel_type,
                    alert_id=alert.alert_id,
                    success=True,
                ))
            except Exception as e:
                notifications.append(Notification(
                    channel=ch.name,
                    channel_type=ch.channel_type,
                    alert_id=alert.alert_id,
                    success=False,
                    error=str(e),
                ))

        self._history.extend(notifications)
        return notifications

    def send_batch(
        self,
        alerts: List[Alert],
        channel_names: Optional[List[str]] = None,
    ) -> List[Notification]:
        """Send multiple alerts."""
        notifications: List[Notification] = []
        for alert in alerts:
            notifications.extend(self.send(alert, channel_names))
        return notifications

    def get_history(self, limit: int = 100) -> List[Notification]:
        """Get notification history."""
        return self._history[-limit:]

    # ------------------------------------------------------------------
    # Default senders
    # ------------------------------------------------------------------

    def _register_default_senders(self) -> None:
        self._senders[NotificationChannel.CONSOLE] = self._send_console
        self._senders[NotificationChannel.SLACK] = self._send_slack
        self._senders[NotificationChannel.WEBHOOK] = self._send_webhook
        self._senders[NotificationChannel.EMAIL] = self._send_email

    @staticmethod
    def _send_console(alert: Alert, config: Dict[str, Any]) -> None:
        """Log alert to console."""
        emoji = {
            AlertSeverity.INFO: "[INFO]",
            AlertSeverity.WARNING: "[WARN]",
            AlertSeverity.CRITICAL: "[CRIT]",
            AlertSeverity.EMERGENCY: "[EMERG]",
        }.get(alert.severity, "[?]")
        print(f"{emoji} ALERT [{alert.alert_id}] {alert.rule_name}: {alert.message}")

    @staticmethod
    def _send_slack(alert: Alert, config: Dict[str, Any]) -> None:
        """Send alert to Slack webhook."""
        webhook_url = config.get("webhook_url", "")
        if not webhook_url:
            raise ValueError("Slack webhook_url is required")

        color = {
            AlertSeverity.INFO: "#36a64f",
            AlertSeverity.WARNING: "#ffcc00",
            AlertSeverity.CRITICAL: "#ff0000",
            AlertSeverity.EMERGENCY: "#8b0000",
        }.get(alert.severity, "#cccccc")

        payload = {
            "attachments": [{
                "color": color,
                "title": f"[{alert.severity.value.upper()}] {alert.rule_name}",
                "text": alert.message,
                "fields": [
                    {"title": "Category", "value": alert.category, "short": True},
                    {"title": "Alert ID", "value": alert.alert_id, "short": True},
                ],
                "footer": "ICYQuant Monitoring Center",
                "ts": int(alert.fired_at),
            }]
        }

        # In production, use httpx or aiohttp
        import urllib.request
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)

    @staticmethod
    def _send_webhook(alert: Alert, config: Dict[str, Any]) -> None:
        """Send alert to generic webhook."""
        url = config.get("url", "")
        if not url:
            raise ValueError("Webhook url is required")

        payload = alert.to_dict()
        import urllib.request
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)

    @staticmethod
    def _send_email(alert: Alert, config: Dict[str, Any]) -> None:
        """Send alert via email (stub - requires SMTP config in production)."""
        to = config.get("to", "")
        subject = f"[ICYQuant] {alert.severity.value.upper()}: {alert.rule_name}"
        # In production, use smtplib or a mail service
        print(f"[EMAIL] To: {to} | Subject: {subject} | {alert.message}")
