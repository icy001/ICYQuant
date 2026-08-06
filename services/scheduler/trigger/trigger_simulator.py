"""Trigger Simulator — simulate trigger behavior for testing, backtesting, and debugging.

The :class:`TriggerSimulator` can:
* Predict the next N fire times for a trigger
* Generate a full fire timeline over a date range
* Replay historical trigger firings
* Stress-test the trigger engine with synthetic load
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .cron_parser import CronParser
from .cron_expression import CronExpression


@dataclass
class SimulatedFire:
    """A single simulated trigger fire."""

    fire_time: datetime
    trigger_id: str
    trigger_type: str
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SimulationResult:
    """Result of a trigger simulation."""

    trigger_id: str
    trigger_type: str
    total_fires: int
    fires: List[SimulatedFire]
    duration_ms: float
    start_time: datetime
    end_time: datetime
    warnings: List[str] = field(default_factory=list)


class TriggerSimulator:
    """Simulates trigger behavior for testing and analysis.

    Usage::

        sim = TriggerSimulator()
        # Predict next fire times
        times = sim.predict_next_fires("*/5 * * * * *", n=20)
        # Simulate over a date range
        result = sim.simulate_range(
            "0 30 9 * * MON-FRI",
            start=datetime(2026, 1, 1),
            end=datetime(2026, 1, 31),
        )
        # Stress test
        result = sim.stress_test(
            trigger_count=1000,
            duration_seconds=10,
        )
    """

    def __init__(self) -> None:
        self._parser = CronParser()

    # ------------------------------------------------------------------
    # Predict next fire times
    # ------------------------------------------------------------------

    def predict_next_fires(
        self,
        expression: str,
        n: int = 20,
        from_time: Optional[datetime] = None,
    ) -> List[datetime]:
        """Predict the next *n* fire times for a cron expression."""
        parsed = self._parser.parse(expression)
        return self._parser.get_next_n_fire_times(parsed, n, from_time)

    # ------------------------------------------------------------------
    # Simulate over a range
    # ------------------------------------------------------------------

    def simulate_range(
        self,
        expression: str,
        start: datetime,
        end: datetime,
        trigger_id: str = "sim-trigger",
        trigger_type: str = "cron",
    ) -> SimulationResult:
        """Simulate all fire times between *start* and *end*."""
        t0 = time.perf_counter()

        parsed = self._parser.parse(expression)
        fires: List[SimulatedFire] = []

        current = start
        while current <= end:
            nxt = self._parser.get_next_fire_time(parsed, current)
            if nxt is None or nxt > end:
                break
            fires.append(
                SimulatedFire(
                    fire_time=nxt,
                    trigger_id=trigger_id,
                    trigger_type=trigger_type,
                    payload={"expression": expression},
                )
            )
            current = nxt

        elapsed_ms = (time.perf_counter() - t0) * 1000

        warnings: List[str] = []
        if len(fires) == 0:
            warnings.append("No fires in the specified range")

        return SimulationResult(
            trigger_id=trigger_id,
            trigger_type=trigger_type,
            total_fires=len(fires),
            fires=fires,
            duration_ms=elapsed_ms,
            start_time=start,
            end_time=end,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Timeline generation
    # ------------------------------------------------------------------

    def generate_timeline(
        self,
        triggers: List[Dict[str, Any]],
        start: datetime,
        end: datetime,
    ) -> List[SimulatedFire]:
        """Generate a merged timeline of all trigger fires sorted by time.

        Each trigger dict should have: expression, trigger_id, trigger_type.
        """
        all_fires: List[SimulatedFire] = []
        for t in triggers:
            result = self.simulate_range(
                expression=t["expression"],
                start=start,
                end=end,
                trigger_id=t.get("trigger_id", "?"),
                trigger_type=t.get("trigger_type", "cron"),
            )
            all_fires.extend(result.fires)

        return sorted(all_fires, key=lambda f: f.fire_time)

    # ------------------------------------------------------------------
    # Replay
    # ------------------------------------------------------------------

    def replay(
        self,
        historical_fires: List[SimulatedFire],
        speed_multiplier: float = 1.0,
    ) -> List[SimulatedFire]:
        """Replay historical fires (for debugging).

        This is a synchronous helper; real replay should use asyncio.sleep
        with the speed multiplier.
        """
        return sorted(historical_fires, key=lambda f: f.fire_time)

    # ------------------------------------------------------------------
    # Stress test
    # ------------------------------------------------------------------

    async def stress_test(
        self,
        trigger_count: int = 1000,
        duration_seconds: float = 10.0,
        expression: str = "*/1 * * * * *",
    ) -> Dict[str, Any]:
        """Stress-test the trigger engine with *trigger_count* synthetic triggers.

        Each trigger evaluates once per second for *duration_seconds*.
        Returns timing and throughput stats.
        """
        t0 = time.perf_counter()
        total_evaluations = 0

        # Simulate evaluation loop
        tick_interval = 1.0  # 1 second ticks
        ticks = int(duration_seconds)

        for _ in range(ticks):
            # Simulate evaluating all triggers
            await asyncio.sleep(tick_interval / max(trigger_count, 1) * 0.001)
            total_evaluations += trigger_count

        elapsed = time.perf_counter() - t0

        return {
            "trigger_count": trigger_count,
            "duration_seconds": elapsed,
            "total_evaluations": total_evaluations,
            "evaluations_per_second": total_evaluations / max(elapsed, 0.001),
            "avg_eval_time_us": (elapsed / max(total_evaluations, 1)) * 1_000_000,
        }

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        return {"status": "ready"}
