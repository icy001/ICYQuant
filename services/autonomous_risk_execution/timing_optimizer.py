"""
Timing Optimizer — determines optimal execution timing.

Decides when to execute within the trading day:
    - Avoid market open/close auction periods
    - Target liquidity windows
    - Align with volume profiles (VWAP)
    - Respect urgency constraints
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class TimingWindow:
    """A favorable trading window."""
    start: time
    end: time
    liquidity_score: float = 0.5
    volatility_score: float = 0.5
    description: str = ""


@dataclass
class TimingDecision:
    """Optimal timing decision."""
    id: str = field(default_factory=lambda: str(uuid4()))
    execute_now: bool = True
    wait_seconds: int = 0
    recommended_window: str = ""
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class TimingOptimizer:
    """
    Optimizes execution timing within the trading day.

    Volume profile (typical US market):
        - Open auction: avoid
        - 09:30-10:00: high vol, high spread → AVOID
        - 10:00-11:30: good liquidity, moderate spread → GOOD
        - 11:30-14:00: lunch lull, lower liquidity → OK
        - 14:00-15:30: good liquidity → GOOD
        - 15:30-15:50: high vol, wider spreads → CAUTION
        - 15:50-16:00: closing auction → AVOID
    """

    FAVORABLE_WINDOWS = [
        TimingWindow(time(10, 0), time(11, 30), 0.8, 0.7, "Morning liquidity window"),
        TimingWindow(time(11, 30), time(14, 0), 0.5, 0.6, "Midday"),
        TimingWindow(time(14, 0), time(15, 30), 0.8, 0.7, "Afternoon liquidity window"),
    ]

    def __init__(self) -> None:
        self._decisions: list[TimingDecision] = []

    async def optimize(
        self,
        now: Optional[datetime] = None,
        urgency: str = "MEDIUM",
        volatility: float = 0.15,
    ) -> TimingDecision:
        """Determine optimal execution timing."""
        now = now or datetime.now()
        current_time = now.time()

        # Market open avoidance
        if time(9, 30) <= current_time <= time(10, 0):
            if urgency == "LOW":
                return TimingDecision(
                    execute_now=False, wait_seconds=(
                        timedelta(hours=10) - timedelta(
                            hours=current_time.hour,
                            minutes=current_time.minute,
                        )
                    ).seconds,
                    recommended_window="Morning liquidity",
                    reason="Avoiding market open volatility",
                )

        # Market close avoidance
        if time(15, 45) <= current_time <= time(16, 0):
            if urgency != "CRITICAL":
                return TimingDecision(
                    execute_now=False, wait_seconds=0,
                    recommended_window="Next trading day",
                    reason="Avoiding market close",
                )

        # Find best available window
        best_window = None
        for window in self.FAVORABLE_WINDOWS:
            if window.start <= current_time <= window.end:
                best_window = window
                break

        if best_window:
            return TimingDecision(
                execute_now=True,
                recommended_window=best_window.description,
                reason=f"Good liquidity window (score={best_window.liquidity_score:.1f})",
            )

        # Default: execute now if outside special windows
        wait = 0
        if urgency == "LOW":
            # Wait for next favorable window
            for window in self.FAVORABLE_WINDOWS:
                if current_time < window.start:
                    wait = (
                        timedelta(
                            hours=window.start.hour,
                            minutes=window.start.minute,
                        )
                        - timedelta(
                            hours=current_time.hour,
                            minutes=current_time.minute,
                        )
                    ).seconds
                    break

        return TimingDecision(
            execute_now=(wait == 0),
            wait_seconds=wait,
            reason="Standard execution timing",
        )
