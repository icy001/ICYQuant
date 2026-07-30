"""
Notification Manager — alerts and notifications for MLOps events.

Supports multiple channels: email, Slack, webhook, logging.
Sends alerts for drift, training failures, rollbacks, and deployments.
"""

import enum
import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class NotificationChannel(str, enum.Enum):
    """Channels for sending notifications."""
    LOG = "log"
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    CONSOLE = "console"


class NotificationPriority(str, enum.Enum):
    """Priority levels for notifications."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Alert:
    """A notification alert."""

    alert_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    title: str = ""
    message: str = ""
    priority: NotificationPriority = NotificationPriority.MEDIUM

    # Context
    source: str = ""  # Which component generated this
    model_name: str = ""
    model_version: str = ""

    # Channels to use
    channels: List[NotificationChannel] = field(
        default_factory=lambda: [NotificationChannel.LOG]
    )

    # Timing
    created_at: float = field(default_factory=time.time)
    sent_at: Optional[float] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "title": self.title,
            "message": self.message,
            "priority": self.priority.value,
            "source": self.source,
            "model_name": self.model_name,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


@dataclass
class NotificationConfig:
    """Configuration for the notification manager."""

    # Channels
    enabled_channels: List[NotificationChannel] = field(
        default_factory=lambda: [NotificationChannel.LOG]
    )

    # Channel-specific configs
    email_recipients: List[str] = field(default_factory=list)
    email_smtp_host: str = ""
    email_smtp_port: int = 587
    email_from: str = "mlops@icyquant.local"

    slack_webhook_url: str = ""
    slack_channel: str = "#mlops-alerts"

    webhook_url: str = ""
    webhook_headers: Dict[str, str] = field(default_factory=dict)

    # Rate limiting
    max_alerts_per_minute: int = 10
    cooldown_seconds: float = 60.0

    # Priority filters
    min_priority: NotificationPriority = NotificationPriority.LOW

    # Suppression
    suppress_duplicates: bool = True
    duplicate_window_seconds: float = 300.0  # 5 min


# ---------------------------------------------------------------------------
# Notification Manager
# ---------------------------------------------------------------------------

class NotificationManager:
    """Manages MLOps notifications across multiple channels.

    Routes alerts to configured channels (log, email, Slack, webhook)
    with rate limiting, priority filtering, and deduplication.

    Usage::

        nm = NotificationManager(config)
        nm.alert(
            title="Model Drift Detected",
            message="Alpha_v38 has prediction PSI of 0.45",
            priority=NotificationPriority.HIGH,
            source="drift_detector",
            model_name="Alpha_v38",
        )
    """

    def __init__(self, config: NotificationConfig):
        self.config = config
        self._alerts: List[Alert] = []
        self._sent_alerts: List[Alert] = []
        self._recent_alerts: List[float] = []  # timestamps for rate limiting
        self._channel_handlers: Dict[NotificationChannel, Callable] = {}

        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """Register built-in channel handlers."""
        self._channel_handlers[NotificationChannel.LOG] = self._send_log
        self._channel_handlers[NotificationChannel.CONSOLE] = self._send_console

    # ------------------------------------------------------------------
    # Alert Sending
    # ------------------------------------------------------------------

    def alert(
        self,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        source: str = "",
        model_name: str = "",
        model_version: str = "",
        channels: Optional[List[NotificationChannel]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Alert]:
        """Send an alert notification.

        Args:
            title: Alert title.
            message: Alert body.
            priority: Alert priority.
            source: Originating component.
            model_name: Related model.
            model_version: Related model version.
            channels: Override channels (defaults to config).
            metadata: Additional metadata.

        Returns:
            The Alert if sent, None if suppressed.
        """
        # Priority filter
        priority_order = {
            NotificationPriority.LOW: 0,
            NotificationPriority.MEDIUM: 1,
            NotificationPriority.HIGH: 2,
            NotificationPriority.CRITICAL: 3,
        }
        if priority_order[priority] < priority_order[self.config.min_priority]:
            return None

        # Rate limiting
        if not self._check_rate_limit():
            logger.warning("Rate limit exceeded, suppressing alert")
            return None

        # Deduplication
        if self.config.suppress_duplicates:
            if self._is_duplicate(title, message):
                logger.debug(f"Suppressing duplicate alert: {title}")
                return None

        alert = Alert(
            title=title,
            message=message,
            priority=priority,
            source=source,
            model_name=model_name,
            model_version=model_version,
            channels=channels or self.config.enabled_channels,
            metadata=metadata or {},
        )

        self._alerts.append(alert)

        # Send through each channel
        for channel in alert.channels:
            if channel not in self.config.enabled_channels:
                continue
            handler = self._channel_handlers.get(channel)
            if handler:
                try:
                    handler(alert)
                except Exception as e:
                    logger.error(f"Failed to send alert via {channel.value}: {e}")

        alert.sent_at = time.time()
        self._sent_alerts.append(alert)
        self._recent_alerts.append(time.time())

        # Trim recent timestamps
        now = time.time()
        self._recent_alerts = [
            t for t in self._recent_alerts
            if now - t < 60.0
        ]

        return alert

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    def notify_drift(
        self, model_name: str, drift_type: str, severity: str, details: str
    ) -> Optional[Alert]:
        """Send a drift detection notification."""
        return self.alert(
            title=f"Drift Detected: {model_name}",
            message=f"{drift_type} drift detected (severity={severity}). {details}",
            priority=(
                NotificationPriority.CRITICAL if severity in ("high", "critical")
                else NotificationPriority.HIGH
            ),
            source="drift_detector",
            model_name=model_name,
        )

    def notify_training_failed(
        self, model_name: str, error: str, job_id: str
    ) -> Optional[Alert]:
        """Send a training failure notification."""
        return self.alert(
            title=f"Training Failed: {model_name}",
            message=f"Training job {job_id} failed: {error}",
            priority=NotificationPriority.HIGH,
            source="trainer",
            model_name=model_name,
            metadata={"job_id": job_id, "error": error},
        )

    def notify_rollback(
        self, model_name: str, from_version: str, to_version: str, reason: str
    ) -> Optional[Alert]:
        """Send a rollback notification."""
        return self.alert(
            title=f"ROLLBACK: {model_name}",
            message=(
                f"Model {model_name} rolled back from v{from_version} "
                f"to v{to_version}. Reason: {reason}"
            ),
            priority=NotificationPriority.CRITICAL,
            source="rollback_manager",
            model_name=model_name,
            metadata={
                "from_version": from_version,
                "to_version": to_version,
                "reason": reason,
            },
        )

    def notify_deployment(
        self, model_name: str, model_version: str, strategy: str
    ) -> Optional[Alert]:
        """Send a deployment notification."""
        return self.alert(
            title=f"Model Deployed: {model_name} v{model_version}",
            message=f"Deployed {model_name} v{model_version} via {strategy}",
            priority=NotificationPriority.MEDIUM,
            source="deployment",
            model_name=model_name,
            model_version=model_version,
        )

    def notify_champion_promoted(
        self, old_champion: str, new_champion: str
    ) -> Optional[Alert]:
        """Send a champion promotion notification."""
        return self.alert(
            title=f"New Champion: {new_champion}",
            message=f"Champion changed: {old_champion} → {new_champion}",
            priority=NotificationPriority.MEDIUM,
            source="champion_challenger",
            model_name=new_champion,
        )

    def notify_approval_required(
        self, model_name: str, model_version: str, requested_by: str
    ) -> Optional[Alert]:
        """Send an approval request notification."""
        return self.alert(
            title=f"Approval Required: {model_name} v{model_version}",
            message=f"Model promotion requested by {requested_by}",
            priority=NotificationPriority.MEDIUM,
            source="approval",
            model_name=model_name,
            model_version=model_version,
        )

    # ------------------------------------------------------------------
    # Channel Handlers
    # ------------------------------------------------------------------

    def register_channel(
        self, channel: NotificationChannel, handler: Callable
    ) -> None:
        """Register a custom channel handler.

        Args:
            channel: Channel type.
            handler: Function that receives an Alert.
        """
        self._channel_handlers[channel] = handler

    def _send_log(self, alert: Alert) -> None:
        """Send alert via logging."""
        log_fn = {
            NotificationPriority.LOW: logger.info,
            NotificationPriority.MEDIUM: logger.info,
            NotificationPriority.HIGH: logger.warning,
            NotificationPriority.CRITICAL: logger.error,
        }.get(alert.priority, logger.info)

        log_fn(f"[{alert.priority.value.upper()}] {alert.title}: {alert.message}")

    def _send_console(self, alert: Alert) -> None:
        """Send alert to console."""
        print(f"[{alert.priority.value.upper()}] [{alert.source}] {alert.title}")
        print(f"  {alert.message}")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_alerts(
        self,
        priority: Optional[NotificationPriority] = None,
        source: Optional[str] = None,
        limit: int = 50,
    ) -> List[Alert]:
        """Get alerts with filters."""
        alerts = self._sent_alerts
        if priority:
            alerts = [a for a in alerts if a.priority == priority]
        if source:
            alerts = [a for a in alerts if a.source == source]
        return sorted(alerts, key=lambda a: a.created_at, reverse=True)[:limit]

    def get_recent_alerts(self, limit: int = 20) -> List[Alert]:
        """Get most recent alerts."""
        return sorted(
            self._sent_alerts,
            key=lambda a: a.created_at,
            reverse=True,
        )[:limit]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_rate_limit(self) -> bool:
        """Check if we're within the rate limit."""
        if self.config.max_alerts_per_minute <= 0:
            return True
        now = time.time()
        recent = [t for t in self._recent_alerts if now - t < 60.0]
        return len(recent) < self.config.max_alerts_per_minute

    def _is_duplicate(self, title: str, message: str) -> bool:
        """Check if a similar alert was sent recently."""
        now = time.time()
        for alert in reversed(self._sent_alerts):
            if now - alert.created_at > self.config.duplicate_window_seconds:
                break
            if alert.title == title and alert.message == message:
                return True
        return False

    def reset(self) -> None:
        """Reset state (for testing)."""
        self._alerts.clear()
        self._sent_alerts.clear()
        self._recent_alerts.clear()
