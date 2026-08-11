"""
Execution Learning — learns from past executions to improve future ones.

Learning dimensions:
    - Strategy effectiveness by market condition
    - Venue performance by asset and size
    - Slippage patterns by time of day
    - Optimal participation rates
    - Cost model calibration
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class StrategyPerformance:
    """Historical performance of an execution strategy."""
    strategy: str
    avg_slippage_bps: float = 0.0
    avg_cost_bps: float = 0.0
    avg_fill_rate: float = 0.0
    sample_count: int = 0
    success_rate: float = 0.0


@dataclass
class VenuePerformance:
    """Historical performance of a venue."""
    venue: str
    avg_fill_rate: float = 0.0
    avg_slippage_bps: float = 0.0
    avg_latency_ms: float = 0.0
    sample_count: int = 0


@dataclass
class LearningInsight:
    """A single learning insight."""
    id: str = field(default_factory=lambda: str(uuid4()))
    category: str = ""  # strategy, venue, cost, slippage, timing
    insight: str = ""
    confidence: float = 0.5
    sample_count: int = 0
    recommendation: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class ExecutionLearning:
    """
    Learns from execution feedback to optimize future execution.

    Learning cycles:
        1. Collect execution results
        2. Analyze strategy performance by condition
        3. Analyze venue performance
        4. Generate insights
        5. Update execution policy parameters
        6. Feed back into strategy selector
    """

    def __init__(self) -> None:
        self._strategy_performance: dict[str, list[dict]] = defaultdict(list)
        self._venue_performance: dict[str, list[dict]] = defaultdict(list)
        self._insights: list[LearningInsight] = []
        self._total_learned: int = 0

    async def record_execution(
        self,
        strategy: str,
        venue: str,
        slippage_bps: float,
        cost_bps: float,
        fill_rate: float,
        latency_ms: float = 0,
        asset: str = "",
        quantity: int = 0,
        adv: float = 0,
        volatility: float = 0.15,
        time_of_day: Optional[str] = None,
    ) -> None:
        """Record execution result for learning."""
        self._strategy_performance[strategy].append({
            "slippage_bps": slippage_bps,
            "cost_bps": cost_bps,
            "fill_rate": fill_rate,
            "asset": asset,
            "pct_adv": abs(quantity) / max(adv, 1) if adv > 0 else 0,
            "volatility": volatility,
        })

        self._venue_performance[venue].append({
            "fill_rate": fill_rate,
            "slippage_bps": slippage_bps,
            "latency_ms": latency_ms,
        })

        self._total_learned += 1

        # Trim old data
        for s in self._strategy_performance:
            if len(self._strategy_performance[s]) > 500:
                self._strategy_performance[s] = self._strategy_performance[s][-250:]

    async def get_best_strategy(
        self, pct_adv: float = 0.05, volatility: float = 0.15,
    ) -> str:
        """Get best performing strategy for given conditions."""
        best = ""
        best_cost = float("inf")

        for strategy, records in self._strategy_performance.items():
            if len(records) < 5:
                continue
            avg_cost = sum(r["cost_bps"] for r in records) / len(records)
            if avg_cost < best_cost:
                best_cost = avg_cost
                best = strategy

        return best or "VWAP"

    async def get_strategy_stats(self) -> dict[str, StrategyPerformance]:
        """Get strategy performance statistics."""
        stats = {}
        for strategy, records in self._strategy_performance.items():
            if not records:
                continue
            n = len(records)
            stats[strategy] = StrategyPerformance(
                strategy=strategy,
                avg_slippage_bps=sum(r["slippage_bps"] for r in records) / n,
                avg_cost_bps=sum(r["cost_bps"] for r in records) / n,
                avg_fill_rate=sum(r["fill_rate"] for r in records) / n,
                sample_count=n,
            )
        return stats

    async def get_venue_stats(self) -> dict[str, VenuePerformance]:
        """Get venue performance statistics."""
        stats = {}
        for venue, records in self._venue_performance.items():
            if not records:
                continue
            n = len(records)
            stats[venue] = VenuePerformance(
                venue=venue,
                avg_fill_rate=sum(r["fill_rate"] for r in records) / n,
                avg_slippage_bps=sum(r["slippage_bps"] for r in records) / n,
                avg_latency_ms=sum(r.get("latency_ms", 0) for r in records) / n,
                sample_count=n,
            )
        return stats

    async def generate_insights(self) -> list[LearningInsight]:
        """Generate learning insights from accumulated data."""
        insights = []

        # Strategy insights
        strategy_stats = await self.get_strategy_stats()
        if len(strategy_stats) >= 2:
            best = min(strategy_stats.values(), key=lambda s: s.avg_cost_bps)
            worst = max(strategy_stats.values(), key=lambda s: s.avg_cost_bps)
            if best.avg_cost_bps < worst.avg_cost_bps * 0.7:
                insights.append(LearningInsight(
                    category="strategy",
                    insight=f"{best.strategy} has {((worst.avg_cost_bps - best.avg_cost_bps)/worst.avg_cost_bps)*100:.0f}% lower cost than {worst.strategy}",
                    confidence=0.8,
                    recommendation=f"Prefer {best.strategy} for similar conditions",
                ))

        self._insights = insights
        return insights

    @property
    def total_learned(self) -> int:
        return self._total_learned
