"""
Notification channels.

Provides notification channel implementations
for various alert delivery mechanisms including
Email, Webhook, Slack, Enterprise WeChat,
DingTalk, and PagerDuty.

Each channel implements the NotificationChannel
protocol with an async send() method.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Protocol

from ..alert_models import AlertEvent


class NotificationChannel(Protocol):
    """
    Notification channel protocol.

    All alert delivery mechanisms must
    implement this protocol.
    """

    name: str

    async def send(
        self,
        event: AlertEvent,
    ) -> bool:
        """
        Send an alert notification.

        Args:
            event: Alert event to notify.

        Returns:
            True if sent successfully.
        """

        ...


class BaseChannel:
    """
    Base notification channel.

    Provides common functionality for
    all notification channels including
    message formatting and send tracking.
    """

    def __init__(
        self,
        name: str = "base",
    ) -> None:
        """
        Initialize base channel.

        Args:
            name: Channel name.
        """

        self._name = name
        self._sent_count: int = 0
        self._failed_count: int = 0
        self._last_sent: Optional[float] = None

    @property
    def name(
        self,
    ) -> str:
        """Get channel name."""
        return self._name

    @property
    def sent_count(
        self,
    ) -> int:
        """Get total sent count."""
        return self._sent_count

    @property
    def failed_count(
        self,
    ) -> int:
        """Get total failed count."""
        return self._failed_count

    def format_message(
        self,
        event: AlertEvent,
    ) -> str:
        """
        Format alert event as message string.

        Args:
            event: Alert event.

        Returns:
            Formatted message string.
        """

        return (
            f"[{event.level.value.upper()}] "
            f"{event.message}\n"
            f"Rule: {event.rule}\n"
            f"Metric: {event.metric}\n"
            f"Value: {event.value}\n"
            f"Threshold: {event.threshold}\n"
            f"Time: {event.timestamp.isoformat()}"
        )

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get channel status.

        Returns:
            Status dictionary.
        """

        return {
            "name": self._name,
            "sent": self._sent_count,
            "failed": self._failed_count,
            "last_sent": self._last_sent,
        }


class LogChannel(BaseChannel):
    """
    Log-based notification channel.

    Writes alert events to the Python
    logging system. Useful for development
    and testing.
    """

    def __init__(
        self,
        logger: Optional[Any] = None,
    ) -> None:
        """
        Initialize log channel.

        Args:
            logger: Optional logger instance.
        """

        super().__init__(name="log")
        self._logger = logger

    async def send(
        self,
        event: AlertEvent,
    ) -> bool:
        """
        Send alert to log.

        Args:
            event: Alert event.

        Returns:
            True always.
        """

        import logging
        import time

        logger = self._logger or logging.getLogger(
            "icyquant.monitoring.alerts"
        )
        message = self.format_message(event)

        if event.level.value == "critical":
            logger.critical(message)
        elif event.level.value == "error":
            logger.error(message)
        elif event.level.value == "warning":
            logger.warning(message)
        else:
            logger.info(message)

        self._sent_count += 1
        self._last_sent = time.time()
        return True


class WebhookChannel(BaseChannel):
    """
    Webhook notification channel.

    Sends alert events as JSON POST
    requests to a configured webhook URL.

    Usage:
        channel = WebhookChannel(
            url="https://example.com/webhook",
        )
    """

    def __init__(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
    ) -> None:
        """
        Initialize webhook channel.

        Args:
            url: Webhook URL.
            headers: Additional HTTP headers.
            timeout: Request timeout in seconds.
        """

        super().__init__(name="webhook")
        self._url = url
        self._headers = headers or {
            "Content-Type": "application/json"
        }
        self._timeout = timeout

    async def send(
        self,
        event: AlertEvent,
    ) -> bool:
        """
        Send alert via webhook.

        Args:
            event: Alert event.

        Returns:
            True if sent successfully.
        """

        import time

        payload = json.dumps(
            event.to_dict()
        ).encode("utf-8")

        try:
            import urllib.request

            req = urllib.request.Request(
                self._url,
                data=payload,
                headers=self._headers,
                method="POST",
            )
            urllib.request.urlopen(
                req, timeout=self._timeout
            )
            self._sent_count += 1
            self._last_sent = time.time()
            return True
        except Exception:
            self._failed_count += 1
            return False


class EmailChannel(BaseChannel):
    """
    Email notification channel.

    Sends alert events via email using
    SMTP. Requires mail server configuration.
    """

    def __init__(
        self,
        recipients: List[str],
        smtp_host: str = "localhost",
        smtp_port: int = 25,
        sender: str = "alerts@icyquant.com",
    ) -> None:
        """
        Initialize email channel.

        Args:
            recipients: List of email recipients.
            smtp_host: SMTP server host.
            smtp_port: SMTP server port.
            sender: Sender email address.
        """

        super().__init__(name="email")
        self._recipients = recipients
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._sender = sender

    async def send(
        self,
        event: AlertEvent,
    ) -> bool:
        """
        Send alert via email.

        Args:
            event: Alert event.

        Returns:
            True if sent successfully.
        """

        import smtplib
        import time
        from email.mime.text import MIMEText

        subject = (
            f"[{event.level.value.upper()}] "
            f"{event.rule}"
        )
        body = self.format_message(event)

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = self._sender
        msg["To"] = ", ".join(self._recipients)

        try:
            with smtplib.SMTP(
                self._smtp_host, self._smtp_port
            ) as server:
                server.sendmail(
                    self._sender,
                    self._recipients,
                    msg.as_string(),
                )
            self._sent_count += 1
            self._last_sent = time.time()
            return True
        except Exception:
            self._failed_count += 1
            return False


class SlackChannel(BaseChannel):
    """
    Slack notification channel.

    Sends alert events as Slack
    incoming webhook messages.
    """

    def __init__(
        self,
        webhook_url: str,
        channel: str = "#alerts",
    ) -> None:
        """
        Initialize Slack channel.

        Args:
            webhook_url: Slack webhook URL.
            channel: Target Slack channel.
        """

        super().__init__(name="slack")
        self._webhook_url = webhook_url
        self._channel = channel

    async def send(
        self,
        event: AlertEvent,
    ) -> bool:
        """
        Send alert to Slack.

        Args:
            event: Alert event.

        Returns:
            True if sent successfully.
        """

        import time

        color_map = {
            "info": "#36a64f",
            "warning": "#ffcc00",
            "error": "#ff0000",
            "critical": "#b71c1c",
        }

        payload = json.dumps({
            "channel": self._channel,
            "attachments": [{
                "color": color_map.get(
                    event.level.value, "#36a64f"
                ),
                "title": f"[{event.level.value.upper()}] {event.rule}",
                "text": event.message,
                "fields": [
                    {
                        "title": "Metric",
                        "value": event.metric,
                        "short": True,
                    },
                    {
                        "title": "Value",
                        "value": str(event.value),
                        "short": True,
                    },
                    {
                        "title": "Threshold",
                        "value": str(event.threshold),
                        "short": True,
                    },
                ],
                "ts": int(
                    event.timestamp.timestamp()
                ),
            }],
        }).encode("utf-8")

        try:
            import urllib.request

            req = urllib.request.Request(
                self._webhook_url,
                data=payload,
                headers={
                    "Content-Type": "application/json"
                },
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
            self._sent_count += 1
            self._last_sent = time.time()
            return True
        except Exception:
            self._failed_count += 1
            return False


class DingTalkChannel(BaseChannel):
    """
    DingTalk notification channel.

    Sends alert events as DingTalk
    robot webhook messages.
    """

    def __init__(
        self,
        webhook_url: str,
    ) -> None:
        """
        Initialize DingTalk channel.

        Args:
            webhook_url: DingTalk robot webhook URL.
        """

        super().__init__(name="dingtalk")
        self._webhook_url = webhook_url

    async def send(
        self,
        event: AlertEvent,
    ) -> bool:
        """
        Send alert to DingTalk.

        Args:
            event: Alert event.

        Returns:
            True if sent successfully.
        """

        import time

        payload = json.dumps({
            "msgtype": "text",
            "text": {
                "content": self.format_message(event)
            },
        }).encode("utf-8")

        try:
            import urllib.request

            req = urllib.request.Request(
                self._webhook_url,
                data=payload,
                headers={
                    "Content-Type": "application/json"
                },
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
            self._sent_count += 1
            self._last_sent = time.time()
            return True
        except Exception:
            self._failed_count += 1
            return False


class EnterpriseWeChatChannel(BaseChannel):
    """
    Enterprise WeChat notification channel.

    Sends alert events to Enterprise WeChat
    group chat via robot webhook.
    """

    def __init__(
        self,
        webhook_url: str,
    ) -> None:
        """
        Initialize Enterprise WeChat channel.

        Args:
            webhook_url: WeChat Work robot webhook URL.
        """

        super().__init__(name="wechat")
        self._webhook_url = webhook_url

    async def send(
        self,
        event: AlertEvent,
    ) -> bool:
        """
        Send alert to Enterprise WeChat.

        Args:
            event: Alert event.

        Returns:
            True if sent successfully.
        """

        import time

        payload = json.dumps({
            "msgtype": "text",
            "text": {
                "content": self.format_message(event)
            },
        }).encode("utf-8")

        try:
            import urllib.request

            req = urllib.request.Request(
                self._webhook_url,
                data=payload,
                headers={
                    "Content-Type": "application/json"
                },
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
            self._sent_count += 1
            self._last_sent = time.time()
            return True
        except Exception:
            self._failed_count += 1
            return False


class PagerDutyChannel(BaseChannel):
    """
    PagerDuty notification channel.

    Sends critical alerts to PagerDuty
    for on-call escalation.
    """

    def __init__(
        self,
        integration_key: str,
    ) -> None:
        """
        Initialize PagerDuty channel.

        Args:
            integration_key: PagerDuty integration key.
        """

        super().__init__(name="pagerduty")
        self._integration_key = integration_key

    async def send(
        self,
        event: AlertEvent,
    ) -> bool:
        """
        Send alert to PagerDuty.

        Args:
            event: Alert event.

        Returns:
            True if sent successfully.
        """

        import time

        severity_map = {
            "info": "info",
            "warning": "warning",
            "error": "error",
            "critical": "critical",
        }

        payload = json.dumps({
            "routing_key": self._integration_key,
            "event_action": "trigger",
            "severity": severity_map.get(
                event.level.value, "warning"
            ),
            "source": event.rule,
            "summary": event.message,
            "timestamp": event.timestamp.isoformat(),
            "custom_details": {
                "metric": event.metric,
                "value": event.value,
                "threshold": event.threshold,
            },
        }).encode("utf-8")

        try:
            import urllib.request

            req = urllib.request.Request(
                "https://events.pagerduty.com/v2/enqueue",
                data=payload,
                headers={
                    "Content-Type": "application/json"
                },
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
            self._sent_count += 1
            self._last_sent = time.time()
            return True
        except Exception:
            self._failed_count += 1
            return False


