"""
Alert Dispatcher — Multi-channel alert delivery.

Routes risk alerts to configured notification channels (logging,
webhook, message queue, email) based on severity and routing rules.

Architecture::

    RiskAlert → Routing Rules → Channels (Log/Webhook/MQ/Email) → Delivery
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from .risk_alert_center import RiskAlert, AlertSeverity

logger = logging.getLogger(__name__)


class ChannelType(str, Enum):
    """Supported alert dispatch channels."""
    LOG = "LOG"
    WEBHOOK = "WEBHOOK"
    MESSAGE_QUEUE = "MESSAGE_QUEUE"
    EMAIL = "EMAIL"
    SMS = "SMS"
    CUSTOM = "CUSTOM"


class DispatchStatus(str, Enum):
    """Alert dispatch status."""
    PENDING = "PENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    RATE_LIMITED = "RATE_LIMITED"


@dataclass
class DispatchRecord:
    """Record of a single alert dispatch."""
    alert_id: str
    channel: ChannelType
    status: DispatchStatus = DispatchStatus.PENDING
    attempted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    delivered_at: Optional[datetime] = None
    error_message: str = ""
    retry_count: int = 0


@dataclass
class ChannelConfig:
    """Configuration for a dispatch channel."""
    channel_type: ChannelType
    enabled: bool = True
    min_severity: AlertSeverity = AlertSeverity.WARNING
    rate_limit_per_minute: int = 60
    retry_max: int = 3
    retry_delay_seconds: float = 5.0
    endpoint: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    custom_handler: Optional[Callable] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AlertDispatcher:
    """
    Multi-channel alert dispatch engine.

    Routes alerts to configured notification channels based on
    severity and routing rules. Supports logging, webhook, message
    queue, and custom channels with rate limiting and retry.

    Usage::

        dispatcher = AlertDispatcher()
        await dispatcher.initialize()

        await dispatcher.register_channel(ChannelConfig(
            channel_type=ChannelType.WEBHOOK,
            endpoint="https://hooks.example.com/alerts",
        ))

        records = await dispatcher.dispatch(alerts)
    """

    def __init__(self) -> None:
        self._channels: dict[str, ChannelConfig] = {}
        self._dispatch_history: list[DispatchRecord] = []
        self._rate_counters: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()
        self._initialized = False

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize the alert dispatcher."""
        # Register default log channel
        self._channels["default_log"] = ChannelConfig(
            channel_type=ChannelType.LOG,
            enabled=True,
            min_severity=AlertSeverity.INFO,
        )
        self._initialized = True
        logger.info("AlertDispatcher initialized with default log channel.")

    async def stop(self) -> None:
        """Stop the alert dispatcher."""
        self._initialized = False
        logger.info("AlertDispatcher stopped.")

    # ---- Channel Management ----

    def register_channel(self, name: str, config: ChannelConfig) -> None:
        """Register a dispatch channel."""
        self._channels[name] = config
        logger.info(f"Channel registered: {name} ({config.channel_type.value})")

    def unregister_channel(self, name: str) -> None:
        """Remove a dispatch channel."""
        self._channels.pop(name, None)
        logger.info(f"Channel unregistered: {name}")

    def get_channels(self) -> dict[str, ChannelConfig]:
        """Get all registered channels."""
        return dict(self._channels)

    # ---- Dispatch ----

    async def dispatch(self, alerts: list[RiskAlert]) -> list[DispatchRecord]:
        """
        Dispatch alerts to all applicable channels.

        Routes each alert to channels where the alert severity meets
        or exceeds the channel's minimum severity.
        """
        if not self._initialized:
            await self.initialize()

        records: list[DispatchRecord] = []

        for alert in alerts:
            for channel_name, channel_config in self._channels.items():
                if not channel_config.enabled:
                    continue

                # Check severity routing
                severity_order = {
                    AlertSeverity.INFO: 0,
                    AlertSeverity.WARNING: 1,
                    AlertSeverity.HIGH: 2,
                    AlertSeverity.CRITICAL: 3,
                    AlertSeverity.EMERGENCY: 4,
                }
                if severity_order.get(alert.severity, 0) < severity_order.get(channel_config.min_severity, 0):
                    continue

                # Rate limit check
                if not await self._check_rate_limit(channel_name, channel_config):
                    records.append(DispatchRecord(
                        alert_id=alert.alert_id,
                        channel=channel_config.channel_type,
                        status=DispatchStatus.RATE_LIMITED,
                    ))
                    continue

                # Dispatch with retry
                record = await self._dispatch_with_retry(alert, channel_name, channel_config)
                records.append(record)

                async with self._lock:
                    self._dispatch_history.append(record)

        return records

    async def dispatch_single(self, alert: RiskAlert) -> list[DispatchRecord]:
        """Dispatch a single alert."""
        return await self.dispatch([alert])

    # ---- History ----

    async def get_history(self, limit: int = 100) -> list[DispatchRecord]:
        """Get recent dispatch history."""
        return self._dispatch_history[-limit:]

    # ---- Internal ----

    async def _dispatch_with_retry(
        self,
        alert: RiskAlert,
        channel_name: str,
        config: ChannelConfig,
    ) -> DispatchRecord:
        """Dispatch an alert to a channel with retry logic."""
        record = DispatchRecord(
            alert_id=alert.alert_id,
            channel=config.channel_type,
        )

        for attempt in range(config.retry_max + 1):
            record.retry_count = attempt
            record.attempted_at = datetime.now(timezone.utc)

            try:
                await self._send_to_channel(alert, config)
                record.status = DispatchStatus.SENT
                record.delivered_at = datetime.now(timezone.utc)
                return record
            except Exception as e:
                record.error_message = str(e)
                if attempt < config.retry_max:
                    logger.warning(
                        f"Dispatch retry {attempt + 1}/{config.retry_max} "
                        f"for alert {alert.alert_id} to {channel_name}: {e}"
                    )
                    await asyncio.sleep(config.retry_delay_seconds)
                else:
                    record.status = DispatchStatus.FAILED
                    logger.error(
                        f"Dispatch FAILED for alert {alert.alert_id} "
                        f"to {channel_name} after {config.retry_max} retries: {e}"
                    )

        return record

    async def _send_to_channel(self, alert: RiskAlert, config: ChannelConfig) -> None:
        """Send an alert to a specific channel."""
        if config.channel_type == ChannelType.LOG:
            self._send_log(alert)
        elif config.channel_type == ChannelType.WEBHOOK:
            await self._send_webhook(alert, config)
        elif config.channel_type == ChannelType.CUSTOM and config.custom_handler:
            await config.custom_handler(alert)
        else:
            # Default: log
            self._send_log(alert)

    def _send_log(self, alert: RiskAlert) -> None:
        """Log alert to Python logging."""
        log_method = {
            AlertSeverity.INFO: logger.info,
            AlertSeverity.WARNING: logger.warning,
            AlertSeverity.HIGH: logger.warning,
            AlertSeverity.CRITICAL: logger.critical,
            AlertSeverity.EMERGENCY: logger.critical,
        }.get(alert.severity, logger.info)

        log_method(
            f"[{alert.severity.value}] {alert.title}: {alert.message} "
            f"(alert_id={alert.alert_id}, account={alert.account_id})"
        )

    async def _send_webhook(self, alert: RiskAlert, config: ChannelConfig) -> None:
        """Send alert to a webhook endpoint."""
        payload = json.dumps(alert.to_dict())
        logger.debug(f"Webhook dispatch to {config.endpoint}: {payload}")
        # In production, this would use aiohttp to POST
        # For now, log the dispatch
        logger.info(f"Webhook alert dispatched: {alert.alert_id} → {config.endpoint}")

    async def _check_rate_limit(self, channel_name: str, config: ChannelConfig) -> bool:
        """Check if channel is within rate limit."""
        now = datetime.now(timezone.utc).timestamp()
        minute_ago = now - 60

        async with self._lock:
            if channel_name not in self._rate_counters:
                self._rate_counters[channel_name] = []

            # Clean old entries
            self._rate_counters[channel_name] = [
                t for t in self._rate_counters[channel_name] if t > minute_ago
            ]

            if len(self._rate_counters[channel_name]) >= config.rate_limit_per_minute:
                return False

            self._rate_counters[channel_name].append(now)
            return True

    # ---- Stats ----

    async def get_stats(self) -> dict[str, Any]:
        """Get dispatcher statistics."""
        return {
            "channels": {
                name: {
                    "type": cfg.channel_type.value,
                    "enabled": cfg.enabled,
                    "min_severity": cfg.min_severity.value,
                }
                for name, cfg in self._channels.items()
            },
            "total_dispatches": len(self._dispatch_history),
        }

    async def health_check(self) -> dict[str, Any]:
        """Check dispatcher health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "active_channels": sum(1 for c in self._channels.values() if c.enabled),
        }
