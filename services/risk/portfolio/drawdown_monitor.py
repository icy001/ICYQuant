"""
Drawdown Monitor — Continuous drawdown detection and tracking.

Monitors equity curves for drawdown events across daily, weekly,
monthly, and historical maximum timeframes. Generates alerts when
drawdown exceeds configured thresholds.

Architecture::

    Equity Curve → Peak Value → Current Equity → Drawdown → Risk Level
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DrawdownPeriod(str, Enum):
    """Drawdown monitoring period."""
    INTRADAY = "INTRADAY"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    HISTORICAL = "HISTORICAL"


class DrawdownSeverity(str, Enum):
    """Drawdown severity levels."""
    NONE = "NONE"
    MILD = "MILD"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"
    CRITICAL = "CRITICAL"


@dataclass
class DrawdownEvent:
    """A drawdown event detected by the monitor."""
    event_id: str
    account_id: str
    period: DrawdownPeriod
    peak_equity: float
    current_equity: float
    drawdown_pct: float
    drawdown_amount: float
    severity: DrawdownSeverity = DrawdownSeverity.NONE
    started_at: Optional[datetime] = None
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    recovered_at: Optional[datetime] = None
    is_active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "account_id": self.account_id,
            "period": self.period.value,
            "peak_equity": self.peak_equity,
            "current_equity": self.current_equity,
            "drawdown_pct": self.drawdown_pct,
            "drawdown_amount": self.drawdown_amount,
            "severity": self.severity.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "detected_at": self.detected_at.isoformat(),
            "is_active": self.is_active,
        }


class DrawdownMonitor:
    """
    Continuous drawdown detection and monitoring.

    Tracks equity curves across multiple timeframes (intraday, daily,
    weekly, monthly, historical) and generates alerts when drawdown
    exceeds configured thresholds.

    Usage::

        monitor = DrawdownMonitor()
        await monitor.initialize()

        event = await monitor.check("ACC-01", current_equity=1_000_000)
    """

    def __init__(
        self,
        mild_threshold_pct: float = 3.0,
        moderate_threshold_pct: float = 7.0,
        severe_threshold_pct: float = 15.0,
        critical_threshold_pct: float = 25.0,
        max_history: int = 5000,
    ) -> None:
        self._mild_threshold = mild_threshold_pct
        self._moderate_threshold = moderate_threshold_pct
        self._severe_threshold = severe_threshold_pct
        self._critical_threshold = critical_threshold_pct

        # Equity tracking
        self._equity_history: dict[str, deque[float]] = {}
        self._peak_equity: dict[str, dict[str, float]] = {}
        self._active_drawdowns: dict[str, dict[str, DrawdownEvent]] = {}
        self._events: list[DrawdownEvent] = []

        self._max_history = max_history
        self._lock = asyncio.Lock()
        self._event_counter: int = 0
        self._initialized = False

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize the drawdown monitor."""
        self._initialized = True
        logger.info("DrawdownMonitor initialized.")

    async def stop(self) -> None:
        """Stop the drawdown monitor."""
        self._initialized = False
        logger.info("DrawdownMonitor stopped.")

    # ---- Core API ----

    async def check(
        self,
        account_id: str,
        current_equity: float,
        timestamp: Optional[datetime] = None,
    ) -> list[DrawdownEvent]:
        """
        Check drawdown status for an account.

        Updates the equity history, recalculates peaks, and detects
        new or resolved drawdown events. Returns a list of active
        drawdown events.
        """
        ts = timestamp or datetime.now(timezone.utc)

        async with self._lock:
            # Initialize tracking if needed
            if account_id not in self._equity_history:
                self._equity_history[account_id] = deque(maxlen=self._max_history)
            if account_id not in self._peak_equity:
                self._peak_equity[account_id] = {
                    "intraday": current_equity,
                    "daily": current_equity,
                    "weekly": current_equity,
                    "monthly": current_equity,
                    "historical": current_equity,
                }
            if account_id not in self._active_drawdowns:
                self._active_drawdowns[account_id] = {}

            self._equity_history[account_id].append(current_equity)

            # Update peaks
            peaks = self._peak_equity[account_id]
            for period in peaks:
                if current_equity > peaks[period]:
                    peaks[period] = current_equity

            # Check each period
            new_events = []
            for period_str, peak in peaks.items():
                period = DrawdownPeriod(period_str.upper())

                if peak > 0:
                    dd_pct = ((peak - current_equity) / peak) * 100
                else:
                    dd_pct = 0.0

                dd_amount = peak - current_equity
                severity = self._classify_severity(dd_pct)

                active_key = period_str
                existing = self._active_drawdowns[account_id].get(active_key)

                if severity != DrawdownSeverity.NONE:
                    if existing and existing.is_active:
                        # Update existing event
                        existing.current_equity = current_equity
                        existing.drawdown_pct = dd_pct
                        existing.drawdown_amount = dd_amount
                        existing.severity = severity
                    else:
                        # New drawdown event
                        self._event_counter += 1
                        event = DrawdownEvent(
                            event_id=f"DD-{self._event_counter:06d}",
                            account_id=account_id,
                            period=period,
                            peak_equity=peak,
                            current_equity=current_equity,
                            drawdown_pct=dd_pct,
                            drawdown_amount=dd_amount,
                            severity=severity,
                            started_at=ts,
                            is_active=True,
                        )
                        self._active_drawdowns[account_id][active_key] = event
                        self._events.append(event)
                        new_events.append(event)

                        logger.warning(
                            f"Drawdown detected: {account_id} {period.value} "
                            f"{dd_pct:.2f}% ({severity.value})"
                        )
                else:
                    # Drawdown recovered
                    if existing and existing.is_active:
                        existing.is_active = False
                        existing.recovered_at = ts
                        logger.info(
                            f"Drawdown recovered: {account_id} {period.value}"
                        )

            return new_events

    async def get_active_drawdowns(self, account_id: str = "") -> list[DrawdownEvent]:
        """Get all active drawdown events, optionally filtered by account."""
        active = []
        if account_id:
            dd_dict = self._active_drawdowns.get(account_id, {})
            active = [e for e in dd_dict.values() if e.is_active]
        else:
            for dd_dict in self._active_drawdowns.values():
                active.extend(e for e in dd_dict.values() if e.is_active)
        return active

    async def get_drawdown_history(self, account_id: str) -> dict[str, Any]:
        """Get drawdown history and metrics for an account."""
        peaks = self._peak_equity.get(account_id, {})
        active = self._active_drawdowns.get(account_id, {})

        return {
            "peaks": dict(peaks),
            "active_drawdowns": {
                p: e.to_dict() for p, e in active.items() if e.is_active
            },
            "all_events": len([
                e for e in self._events if e.account_id == account_id
            ]),
        }

    async def get_max_historical_drawdown(self, account_id: str) -> dict[str, Any]:
        """Get the maximum historical drawdown for an account."""
        peaks = self._peak_equity.get(account_id, {})
        hist_peak = peaks.get("historical", 0)
        history = list(self._equity_history.get(account_id, deque()))

        max_dd_pct = 0.0
        max_dd_amount = 0.0
        max_peak = hist_peak

        if history:
            peak_so_far = history[0]
            for equity in history:
                if equity > peak_so_far:
                    peak_so_far = equity
                if peak_so_far > 0:
                    dd_pct = ((peak_so_far - equity) / peak_so_far) * 100
                    if dd_pct > max_dd_pct:
                        max_dd_pct = dd_pct
                        max_dd_amount = peak_so_far - equity
                        max_peak = peak_so_far

        return {
            "max_drawdown_pct": max_dd_pct,
            "max_drawdown_amount": max_dd_amount,
            "peak_equity": max_peak,
        }

    # ---- Internal ----

    def _classify_severity(self, drawdown_pct: float) -> DrawdownSeverity:
        """Classify drawdown percentage into severity level."""
        if drawdown_pct <= 0:
            return DrawdownSeverity.NONE
        if drawdown_pct < self._mild_threshold:
            return DrawdownSeverity.NONE
        if drawdown_pct < self._moderate_threshold:
            return DrawdownSeverity.MILD
        if drawdown_pct < self._severe_threshold:
            return DrawdownSeverity.MODERATE
        if drawdown_pct < self._critical_threshold:
            return DrawdownSeverity.SEVERE
        return DrawdownSeverity.CRITICAL

    # ---- Stats ----

    async def get_stats(self) -> dict[str, Any]:
        """Get monitor statistics."""
        async with self._lock:
            return {
                "tracked_accounts": len(self._equity_history),
                "total_events": len(self._events),
                "active_drawdowns": sum(
                    sum(1 for e in dd.values() if e.is_active)
                    for dd in self._active_drawdowns.values()
                ),
            }

    async def health_check(self) -> dict[str, Any]:
        """Check monitor health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "tracked_accounts": len(self._equity_history),
        }
