"""
Alert suppression.

Prevents alert storms by implementing
cooldown, deduplication, and rate
limiting for fired alerts.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from ..alert_models import AlertEvent


class AlertSuppression:
    """
    Alert suppression manager.

    Prevents alert storms through:
    - Cooldown: Minimum time between
      repeated alerts for the same rule.
    - Deduplication: Suppress duplicate
      alerts with the same fingerprint.
    - Rate limiting: Maximum alerts
      per time window.

    Usage:
        suppression = AlertSuppression(
            cooldown_seconds=300,
            max_alerts_per_minute=10,
        )

        if await suppression.allow(alert_id):
            # Send alert
    """

    def __init__(
        self,
        cooldown_seconds: int = 300,
        max_alerts_per_minute: int = 10,
        max_alerts_per_hour: int = 100,
        dedup_window: int = 60,
    ) -> None:
        """
        Initialize suppression manager.

        Args:
            cooldown_seconds: Min seconds between same-rule alerts.
            max_alerts_per_minute: Rate limit per minute.
            max_alerts_per_hour: Rate limit per hour.
            dedup_window: Dedup window in seconds.
        """

        self._cooldown_seconds = cooldown_seconds
        self._max_per_minute = max_alerts_per_minute
        self._max_per_hour = max_alerts_per_hour
        self._dedup_window = dedup_window

        self._last_alert_time: Dict[str, float] = {}
        self._minute_counts: List[float] = []
        self._hour_counts: List[float] = []
        self._recent_fingerprints: Dict[str, float] = {}

    async def allow(
        self,
        alert_id: str,
    ) -> bool:
        """
        Check if an alert should be allowed.

        Args:
            alert_id: Unique alert identifier
                     (typically the fingerprint).

        Returns:
            True if alert should be sent.
        """

        now = time.time()

        # Check cooldown
        last = self._last_alert_time.get(alert_id)
        if last is not None:
            elapsed = now - last
            if elapsed < self._cooldown_seconds:
                return False

        # Check dedup
        dedup_time = self._recent_fingerprints.get(
            alert_id
        )
        if dedup_time is not None:
            if now - dedup_time < self._dedup_window:
                return False

        # Check rate limits
        self._minute_counts = [
            t
            for t in self._minute_counts
            if now - t < 60
        ]
        if len(self._minute_counts) >= (
            self._max_per_minute
        ):
            return False

        self._hour_counts = [
            t
            for t in self._hour_counts
            if now - t < 3600
        ]
        if len(self._hour_counts) >= (
            self._max_per_hour
        ):
            return False

        # Allow
        self._last_alert_time[alert_id] = now
        self._minute_counts.append(now)
        self._hour_counts.append(now)
        self._recent_fingerprints[alert_id] = now
        return True

    def record(
        self,
        event: AlertEvent,
    ) -> None:
        """
        Record a fired alert for tracking.

        Args:
            event: Alert event that was fired.
        """

        now = time.time()
        self._last_alert_time[event.fingerprint] = now
        self._recent_fingerprints[
            event.fingerprint
        ] = now
        self._minute_counts.append(now)
        self._hour_counts.append(now)

    def reset(
        self,
        alert_id: Optional[str] = None,
    ) -> None:
        """
        Reset suppression state.

        Args:
            alert_id: Specific alert to reset,
                      or None for all.
        """

        if alert_id:
            self._last_alert_time.pop(
                alert_id, None
            )
            self._recent_fingerprints.pop(
                alert_id, None
            )
        else:
            self._last_alert_time.clear()
            self._recent_fingerprints.clear()
            self._minute_counts.clear()
            self._hour_counts.clear()

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get suppression status.

        Returns:
            Status dictionary.
        """

        now = time.time()
        self._minute_counts = [
            t
            for t in self._minute_counts
            if now - t < 60
        ]
        self._hour_counts = [
            t
            for t in self._hour_counts
            if now - t < 3600
        ]

        return {
            "cooldown_seconds": self._cooldown_seconds,
            "alerts_last_minute": len(
                self._minute_counts
            ),
            "alerts_last_hour": len(
                self._hour_counts
            ),
            "max_per_minute": self._max_per_minute,
            "max_per_hour": self._max_per_hour,
            "tracked_alerts": len(
                self._last_alert_time
            ),
        }
