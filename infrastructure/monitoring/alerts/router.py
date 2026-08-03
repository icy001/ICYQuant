"""
Alert router.

Routes alert events to appropriate
notification channels based on alert
level, rule, and configured routing
rules.

Supports level-based routing,
rule-specific channel overrides,
and suppression/escalation integration.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..alert_models import AlertEvent, AlertLevel
from .escalation import EscalationPolicy
from .notification import (
    BaseChannel,
    LogChannel,
    NotificationChannel,
)
from .suppression import AlertSuppression


class AlertRouter:
    """
    Alert notification router.

    Routes alert events to notification
    channels based on:
    - Alert level (info, warning, error, critical)
    - Rule-specific channel assignments
    - Suppression filtering
    - Escalation policy

    Usage:
        router = AlertRouter()

        # Add channels
        router.add_channel("log", LogChannel())
        router.add_channel("slack", SlackChannel(url))

        # Route by level
        router.route_level(AlertLevel.CRITICAL, ["log", "slack"])

        # Route alert
        await router.route(metric, rule)
    """

    def __init__(
        self,
        suppression: Optional[AlertSuppression] = None,
        escalation: Optional[EscalationPolicy] = None,
    ) -> None:
        """
        Initialize alert router.

        Args:
            suppression: Alert suppression manager.
            escalation: Escalation policy.
        """

        self._channels: Dict[str, BaseChannel] = {}
        self._level_routes: Dict[AlertLevel, List[str]] = {}
        self._rule_routes: Dict[str, List[str]] = {}
        self._suppression = suppression
        self._escalation = escalation

        # Default: log channel
        self._channels["log"] = LogChannel()

        # Default level routing
        self._level_routes[AlertLevel.INFO] = ["log"]
        self._level_routes[AlertLevel.WARNING] = ["log"]
        self._level_routes[AlertLevel.ERROR] = ["log"]
        self._level_routes[AlertLevel.CRITICAL] = ["log"]

    def add_channel(
        self,
        name: str,
        channel: BaseChannel,
    ) -> None:
        """
        Register a notification channel.

        Args:
            name: Unique channel name.
            channel: Channel instance.
        """

        self._channels[name] = channel

    def remove_channel(
        self,
        name: str,
    ) -> None:
        """
        Remove a notification channel.

        Args:
            name: Channel name.
        """

        self._channels.pop(name, None)

    def route_level(
        self,
        level: AlertLevel,
        channels: List[str],
    ) -> None:
        """
        Configure channel routing for a level.

        Args:
            level: Alert level.
            channels: List of channel names.
        """

        self._level_routes[level] = channels

    def route_rule(
        self,
        rule_name: str,
        channels: List[str],
    ) -> None:
        """
        Configure channel routing for a specific rule.

        Args:
            rule_name: Alert rule name.
            channels: List of channel names.
        """

        self._rule_routes[rule_name] = channels

    def _get_channels_for(
        self,
        event: AlertEvent,
    ) -> List[BaseChannel]:
        """
        Get channels for an alert event.

        Args:
            event: Alert event.

        Returns:
            List of channel instances.
        """

        channel_names: List[str] = []

        # Rule-specific routing takes priority
        if event.rule in self._rule_routes:
            channel_names = self._rule_routes[event.rule]
        else:
            channel_names = self._level_routes.get(
                event.level, ["log"]
            )

        channels: List[BaseChannel] = []
        for name in channel_names:
            channel = self._channels.get(name)
            if channel is not None:
                channels.append(channel)

        return channels

    async def route(
        self,
        event: AlertEvent,
    ) -> Dict[str, bool]:
        """
        Route an alert event to channels.

        Args:
            event: Alert event to route.

        Returns:
            Dict mapping channel name to send success.
        """

        results: Dict[str, bool] = {}

        # Check suppression
        if self._suppression is not None:
            allowed = await self._suppression.allow(
                event.fingerprint
            )
            if not allowed:
                return results

        # Get target channels
        channels = self._get_channels_for(event)

        for channel in channels:
            try:
                success = await channel.send(event)
                results[channel.name] = success
            except Exception:
                results[channel.name] = False

        # Record in suppression
        if self._suppression is not None:
            self._suppression.record(event)

        # Check escalation
        if self._escalation is not None:
            escalated = await self._escalation.check_escalation(
                event
            )
            if escalated is not None:
                esc_channels = self._get_channels_for(
                    escalated
                )
                for channel in esc_channels:
                    try:
                        await channel.send(escalated)
                    except Exception:
                        pass

        return results

    def acknowledge_alert(
        self,
        fingerprint: str,
    ) -> bool:
        """
        Acknowledge an alert to stop escalation.

        Args:
            fingerprint: Alert fingerprint.

        Returns:
            True if acknowledged.
        """

        if self._escalation is not None:
            return self._escalation.acknowledge(
                fingerprint
            )
        return False

    def resolve_alert(
        self,
        fingerprint: str,
    ) -> None:
        """
        Mark an alert as resolved.

        Args:
            fingerprint: Alert fingerprint.
        """

        if self._escalation is not None:
            self._escalation.resolve(fingerprint)

        if self._suppression is not None:
            self._suppression.reset(fingerprint)

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get router status.

        Returns:
            Status dictionary.
        """

        return {
            "channels": {
                name: ch.get_status()
                for name, ch in self._channels.items()
            },
            "level_routes": {
                level.value: channels
                for level, channels in self._level_routes.items()
            },
            "rule_routes": dict(self._rule_routes),
            "suppression": (
                self._suppression.get_status()
                if self._suppression
                else None
            ),
            "escalation": (
                self._escalation.get_status()
                if self._escalation
                else None
            ),
        }
