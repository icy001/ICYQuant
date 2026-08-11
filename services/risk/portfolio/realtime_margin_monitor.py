"""
Real-Time Margin Monitor — Continuous margin usage monitoring.

Tracks margin utilization, available margin, margin calls, and
margin ratio trends with real-time updates.

Architecture::

    Positions → Margin Used → Margin Available → Margin Ratio → Alerts
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class MarginStatus:
    """Current margin status for an account."""
    account_id: str
    margin_used: float = 0.0
    margin_available: float = 0.0
    margin_limit: float = 0.0
    margin_ratio: float = 0.0
    maintenance_margin: float = 0.0
    excess_liquidity: float = 0.0
    margin_call_level: float = 0.0
    liquidation_level: float = 0.0
    status: str = "OK"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "margin_used": self.margin_used,
            "margin_available": self.margin_available,
            "margin_limit": self.margin_limit,
            "margin_ratio": self.margin_ratio,
            "maintenance_margin": self.maintenance_margin,
            "excess_liquidity": self.excess_liquidity,
            "margin_call_level": self.margin_call_level,
            "liquidation_level": self.liquidation_level,
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
        }


class RealtimeMarginMonitor:
    """
    Real-time margin usage monitoring engine.

    Tracks margin utilization, detects approaching margin calls,
    and monitors maintenance margin requirements with configurable
    alert thresholds.

    Usage::

        monitor = RealtimeMarginMonitor()
        await monitor.initialize()

        await monitor.update_margin("ACC-01", used=50000, available=150000, limit=200000)
        status = await monitor.get_margin_status("ACC-01")
    """

    def __init__(
        self,
        warning_threshold: float = 0.70,
        critical_threshold: float = 0.85,
        liquidation_threshold: float = 0.95,
    ) -> None:
        self._warning_threshold = warning_threshold
        self._critical_threshold = critical_threshold
        self._liquidation_threshold = liquidation_threshold
        self._margin_data: dict[str, MarginStatus] = {}
        self._history: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()
        self._initialized = False

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize the margin monitor."""
        self._initialized = True
        logger.info("RealtimeMarginMonitor initialized.")

    async def stop(self) -> None:
        """Stop the margin monitor."""
        self._initialized = False
        logger.info("RealtimeMarginMonitor stopped.")

    # ---- Core API ----

    async def update_margin(
        self,
        account_id: str,
        used: float,
        available: float,
        limit: float = 0.0,
        maintenance: float = 0.0,
    ) -> MarginStatus:
        """
        Update margin data for an account.

        Returns the current MarginStatus with alerts if thresholds
        are breached.
        """
        async with self._lock:
            if limit <= 0:
                limit = used + available

            ratio = used / limit if limit > 0 else 0.0

            # Determine status
            if ratio >= self._liquidation_threshold:
                status = "LIQUIDATION"
            elif ratio >= self._critical_threshold:
                status = "CRITICAL"
            elif ratio >= self._warning_threshold:
                status = "WARNING"
            else:
                status = "OK"

            margin_status = MarginStatus(
                account_id=account_id,
                margin_used=used,
                margin_available=available,
                margin_limit=limit,
                margin_ratio=ratio,
                maintenance_margin=maintenance,
                excess_liquidity=available - maintenance,
                margin_call_level=self._critical_threshold * limit,
                liquidation_level=self._liquidation_threshold * limit,
                status=status,
            )
            self._margin_data[account_id] = margin_status

            # Track history
            if account_id not in self._history:
                self._history[account_id] = deque(maxlen=1000)
            self._history[account_id].append(ratio)

            if status in ("CRITICAL", "LIQUIDATION"):
                logger.warning(
                    f"Margin {status}: {account_id} ratio={ratio:.2%} "
                    f"used={used:,.0f} limit={limit:,.0f}"
                )

            return margin_status

    async def get_margin_status(self, account_id: str) -> Optional[MarginStatus]:
        """Get current margin status for an account."""
        return self._margin_data.get(account_id)

    async def get_all_statuses(self) -> list[MarginStatus]:
        """Get margin statuses for all tracked accounts."""
        return list(self._margin_data.values())

    async def get_history(self, account_id: str) -> list[float]:
        """Get margin ratio history for an account."""
        hist = self._history.get(account_id)
        return list(hist) if hist else []

    async def get_trend(self, account_id: str, window: int = 20) -> dict[str, Any]:
        """
        Analyze margin ratio trend over recent history.

        Returns direction (increasing/decreasing/stable) and rate of change.
        """
        hist = await self.get_history(account_id)
        if len(hist) < 2:
            return {"direction": "stable", "rate": 0.0}

        recent = list(hist)[-window:]
        if len(recent) < 2:
            return {"direction": "stable", "rate": 0.0}

        # Simple linear trend
        first = recent[0]
        last = recent[-1]
        delta = last - first

        direction = "increasing" if delta > 0.01 else ("decreasing" if delta < -0.01 else "stable")
        return {
            "direction": direction,
            "rate": delta / len(recent),
            "current": last,
            "window_start": first,
        }

    async def check_margin_call(self, account_id: str) -> dict[str, Any]:
        """
        Check if an account is approaching or at margin call level.

        Returns detailed assessment with recommended actions.
        """
        status = self._margin_data.get(account_id)
        if not status:
            return {"status": "unknown", "message": "Account not tracked"}

        if status.status == "LIQUIDATION":
            return {
                "status": "liquidation",
                "severity": "critical",
                "margin_ratio": status.margin_ratio,
                "deficit": max(0, status.margin_used - status.liquidation_level),
                "action": "IMMEDIATE: Reduce positions or add capital to avoid liquidation",
            }
        elif status.status == "CRITICAL":
            return {
                "status": "margin_call",
                "severity": "high",
                "margin_ratio": status.margin_ratio,
                "deficit": max(0, status.margin_used - status.margin_call_level),
                "action": "URGENT: Deposit funds or reduce margin positions",
            }
        elif status.status == "WARNING":
            return {
                "status": "warning",
                "severity": "medium",
                "margin_ratio": status.margin_ratio,
                "action": "Monitor closely; consider reducing exposure",
            }
        return {"status": "ok", "severity": "normal", "margin_ratio": status.margin_ratio}

    # ---- Stats ----

    async def get_stats(self) -> dict[str, Any]:
        """Get monitor statistics."""
        async with self._lock:
            return {
                "tracked_accounts": len(self._margin_data),
                "accounts": {
                    aid: {"ratio": ms.margin_ratio, "status": ms.status}
                    for aid, ms in self._margin_data.items()
                },
            }

    async def health_check(self) -> dict[str, Any]:
        """Check monitor health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "tracked_accounts": len(self._margin_data),
        }
