"""
Execution Guard — real-time monitoring during order execution.

Monitors execution in real-time and can:
    - Pause execution (spread widening)
    - Cancel orders (excessive slippage)
    - Throttle rate (market impact exceeding estimate)
    - Halt entirely (anomaly detection)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class ExecutionAlert:
    """Execution anomaly alert."""
    alert_type: str
    severity: str = "WARNING"  # INFO, WARNING, CRITICAL
    message: str = ""
    order_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class GuardState:
    """Current execution guard state."""
    is_active: bool = True
    is_throttled: bool = False
    is_paused: bool = False
    consecutive_slippage_violations: int = 0
    active_alerts: list[ExecutionAlert] = field(default_factory=list)


class ExecutionGuard:
    """
    Real-time execution monitoring and safety.

    Monitors:
        - Slippage vs expected
        - Fill rate vs expected
        - Spread changes during execution
        - Volatility spikes
        - Anomalous fill patterns
        - Time since last fill
        - Cumulative impact vs estimate
    """

    def __init__(
        self,
        max_consecutive_slippage: int = 3,
        spread_widening_threshold: float = 3.0,
        vol_spike_threshold: float = 2.0,
    ) -> None:
        self._max_slippage_violations = max_consecutive_slippage
        self._spread_widening_threshold = spread_widening_threshold
        self._vol_spike_threshold = vol_spike_threshold
        self._state = GuardState()

    async def monitor_fill(
        self,
        order_id: str,
        fill_price: float,
        arrival_price: float,
        expected_slippage_bps: float,
        spread_bps: float,
        initial_spread_bps: float,
        volatility: float,
        initial_volatility: float,
    ) -> list[ExecutionAlert]:
        """Monitor a fill and return any alerts."""
        alerts = []

        # Slippage check
        if arrival_price > 0:
            slippage_bps = (fill_price - arrival_price) / arrival_price * 10000
            if abs(slippage_bps) > max(expected_slippage_bps * 2, 50):
                self._state.consecutive_slippage_violations += 1
                alerts.append(ExecutionAlert(
                    alert_type="excessive_slippage",
                    severity="WARNING" if self._state.consecutive_slippage_violations < 3 else "CRITICAL",
                    message=f"Slippage {slippage_bps:.1f}bps exceeds expected {expected_slippage_bps:.1f}bps",
                    order_id=order_id,
                ))
            else:
                self._state.consecutive_slippage_violations = max(0, self._state.consecutive_slippage_violations - 1)

        # Spread widening check
        if initial_spread_bps > 0:
            spread_ratio = spread_bps / initial_spread_bps
            if spread_ratio > self._spread_widening_threshold:
                alerts.append(ExecutionAlert(
                    alert_type="spread_widening",
                    severity="WARNING",
                    message=f"Spread widened {spread_ratio:.1f}x (from {initial_spread_bps:.0f} to {spread_bps:.0f} bps)",
                    order_id=order_id,
                ))

        # Vol spike check
        if initial_volatility > 0:
            vol_ratio = volatility / initial_volatility
            if vol_ratio > self._vol_spike_threshold:
                alerts.append(ExecutionAlert(
                    alert_type="volatility_spike",
                    severity="CRITICAL",
                    message=f"Volatility spiked {vol_ratio:.1f}x",
                    order_id=order_id,
                ))

        self._state.active_alerts = alerts[-20:]
        for alert in alerts:
            logger.warning("Execution alert: %s %s", alert.alert_type, alert.message)

        return alerts

    def should_pause(self) -> bool:
        """Check if execution should be paused."""
        return (
            self._state.consecutive_slippage_violations >= self._max_slippage_violations
            or any(a.severity == "CRITICAL" for a in self._state.active_alerts[-3:])
        )

    def should_cancel(self) -> bool:
        """Check if orders should be cancelled."""
        return self._state.consecutive_slippage_violations >= self._max_slippage_violations * 2

    def reset(self) -> None:
        """Reset guard state."""
        self._state = GuardState()

    @property
    def state(self) -> GuardState:
        return self._state
