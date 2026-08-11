"""SurvivalMemory — survival score history and trend analysis.

Tracks survival score evolution over time, enabling
detection of survival degradation patterns.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SurvivalSnapshot:
    """A survival score snapshot."""

    timestamp: float
    score: float
    components: Dict[str, float] = field(default_factory=dict)
    mode: str = "NORMAL"
    capital: float = 0.0
    var_99: float = 0.0
    drawdown_pct: float = 0.0


class SurvivalMemory:
    """Tracks survival score history.

    Usage::

        memory = SurvivalMemory()
        memory.record(score=78.5, mode="CAUTION", capital=100_000_000)
        trend = memory.get_trend(last_n=50)
        if trend["trend"] == "declining":
            print("WARNING: Survival score trending down")
    """

    def __init__(self, max_snapshots: int = 5000):
        self._snapshots: List[SurvivalSnapshot] = []
        self._max_snapshots = max_snapshots

    def record(
        self,
        score: float,
        mode: str = "NORMAL",
        capital: float = 0.0,
        var_99: float = 0.0,
        drawdown_pct: float = 0.0,
        components: Optional[Dict[str, float]] = None,
    ) -> SurvivalSnapshot:
        """Record a survival score snapshot."""
        snapshot = SurvivalSnapshot(
            timestamp=time.time(),
            score=score,
            components=components or {},
            mode=mode,
            capital=capital,
            var_99=var_99,
            drawdown_pct=drawdown_pct,
        )
        self._snapshots.append(snapshot)

        if len(self._snapshots) > self._max_snapshots:
            self._snapshots = self._snapshots[-self._max_snapshots:]

        return snapshot

    def get_trend(
        self,
        last_n: int = 50,
    ) -> Dict[str, Any]:
        """Analyze survival score trend.

        Returns trend direction, volatility, and recent extremes.
        """
        if len(self._snapshots) < 2:
            return {"trend": "insufficient_data"}

        recent = self._snapshots[-last_n:]
        scores = [s.score for s in recent]

        avg = sum(scores) / len(scores)
        first_avg = sum(scores[:max(len(scores)//3, 1)]) / max(len(scores)//3, 1)
        last_avg = sum(scores[-max(len(scores)//3, 1):]) / max(len(scores)//3, 1)

        change = last_avg - first_avg

        if change > 5:
            trend = "improving"
        elif change < -5:
            trend = "declining"
        else:
            trend = "stable"

        # volatility
        variance = sum((s - avg) ** 2 for s in scores) / len(scores)
        vol = variance ** 0.5

        return {
            "trend": trend,
            "change": change,
            "current_score": recent[-1].score,
            "average": avg,
            "min": min(scores),
            "max": max(scores),
            "volatility": vol,
            "snapshot_count": len(recent),
        }

    def get_latest(self) -> Optional[SurvivalSnapshot]:
        """Get the latest snapshot."""
        return self._snapshots[-1] if self._snapshots else None

    def clear(self) -> None:
        """Clear all snapshots."""
        self._snapshots.clear()
