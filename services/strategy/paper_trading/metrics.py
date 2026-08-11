"""
Paper Trading Metrics
=====================
Prometheus-compatible metrics for the paper trading platform.

Metrics:
    icyquant_paper_orders_total         — Total paper orders submitted
    icyquant_virtual_trades_total       — Total virtual trades executed
    icyquant_strategy_score             — Strategy scorecard score (gauge)
    icyquant_strategy_promotions_total  — Total promotions initiated
    icyquant_kill_switch_triggered      — Kill switch activations (counter)
    icyquant_slippage_average           — Average slippage per trade (gauge)
    icyquant_execution_latency_simulated — Simulated execution latency (histogram)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MetricValue:
    """A single metric data point."""
    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class PaperTradingMetrics:
    """Metrics collector for paper trading platform.

    Tracks 7 key indicators for monitoring paper trading health and quality.
    """

    def __init__(self):
        # Counters
        self._paper_orders_total: int = 0
        self._virtual_trades_total: int = 0
        self._strategy_promotions_total: int = 0
        self._kill_switch_triggered: int = 0

        # Gauges
        self._strategy_scores: Dict[str, float] = {}       # strategy_id → score
        self._slippage_samples: List[float] = []            # Recent slippage values
        self._latency_samples: List[float] = []             # Recent latency values

        # Histogram buckets for execution latency (ms)
        self._latency_buckets: List[float] = [1, 5, 10, 25, 50, 100, 250, 500, 1000]
        self._latency_bucket_counts: Dict[float, int] = {b: 0 for b in self._latency_buckets}

    # ------------------------------------------------------------------
    # Counter Operations
    # ------------------------------------------------------------------

    def increment_paper_orders(self, count: int = 1) -> None:
        self._paper_orders_total += count

    def increment_virtual_trades(self, count: int = 1) -> None:
        self._virtual_trades_total += count

    def increment_promotions(self, count: int = 1) -> None:
        self._strategy_promotions_total += count

    def increment_kill_switch(self, count: int = 1) -> None:
        self._kill_switch_triggered += count

    # ------------------------------------------------------------------
    # Gauge Operations
    # ------------------------------------------------------------------

    def set_strategy_score(self, strategy_id: str, score: float) -> None:
        self._strategy_scores[strategy_id] = score

    def record_slippage(self, slippage_bps: float) -> None:
        self._slippage_samples.append(abs(slippage_bps))
        # Keep last 1000 samples
        if len(self._slippage_samples) > 1000:
            self._slippage_samples = self._slippage_samples[-1000:]

    def record_latency(self, latency_ms: float) -> None:
        self._latency_samples.append(latency_ms)
        if len(self._latency_samples) > 1000:
            self._latency_samples = self._latency_samples[-1000:]

        # Histogram
        for bucket in self._latency_buckets:
            if latency_ms <= bucket:
                self._latency_bucket_counts[bucket] += 1

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    @property
    def avg_slippage_bps(self) -> float:
        if not self._slippage_samples:
            return 0.0
        return sum(self._slippage_samples) / len(self._slippage_samples)

    @property
    def avg_latency_ms(self) -> float:
        if not self._latency_samples:
            return 0.0
        return sum(self._latency_samples) / len(self._latency_samples)

    @property
    def avg_strategy_score(self) -> float:
        if not self._strategy_scores:
            return 0.0
        return sum(self._strategy_scores.values()) / len(self._strategy_scores)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def collect(self) -> List[MetricValue]:
        """Collect all metrics for export."""
        return [
            MetricValue("icyquant_paper_orders_total", float(self._paper_orders_total)),
            MetricValue("icyquant_virtual_trades_total", float(self._virtual_trades_total)),
            MetricValue("icyquant_strategy_promotions_total", float(self._strategy_promotions_total)),
            MetricValue("icyquant_kill_switch_triggered", float(self._kill_switch_triggered)),
            MetricValue("icyquant_slippage_average", self.avg_slippage_bps),
            MetricValue("icyquant_execution_latency_simulated", self.avg_latency_ms),
        ]

    def snapshot(self) -> Dict[str, Any]:
        """Get a snapshot of all metrics."""
        return {
            "counters": {
                "paper_orders_total": self._paper_orders_total,
                "virtual_trades_total": self._virtual_trades_total,
                "strategy_promotions_total": self._strategy_promotions_total,
                "kill_switch_triggered": self._kill_switch_triggered,
            },
            "gauges": {
                "avg_slippage_bps": round(self.avg_slippage_bps, 4),
                "avg_latency_ms": round(self.avg_latency_ms, 2),
                "avg_strategy_score": round(self.avg_strategy_score, 1),
                "strategies_scored": len(self._strategy_scores),
            },
            "histograms": {
                "latency_buckets": {
                    str(b): c for b, c in self._latency_bucket_counts.items()
                },
            },
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._paper_orders_total = 0
        self._virtual_trades_total = 0
        self._strategy_promotions_total = 0
        self._kill_switch_triggered = 0
        self._strategy_scores.clear()
        self._slippage_samples.clear()
        self._latency_samples.clear()
        self._latency_bucket_counts = {b: 0 for b in self._latency_buckets}
