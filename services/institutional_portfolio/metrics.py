"""
Portfolio Metrics — Multi-Strategy Portfolio Observability

Prometheus-compatible metrics for all portfolio subsystems.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class PortfolioMetrics:
    """Prometheus-compatible metric interface for portfolio operations."""

    def __init__(
        self,
        metrics_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.metrics_id = metrics_id or f"pmet-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}

    # Counter operations
    def inc(self, name: str, value: float = 1.0) -> None:
        self._counters[name] = self._counters.get(name, 0) + value

    # Gauge operations
    def set(self, name: str, value: float) -> None:
        self._gauges[name] = value

    def record_snapshot(self, portfolio_snapshot: Dict[str, Any]) -> None:
        """Record all portfolio metrics from a snapshot."""
        self.set("icyquant_strategy_pool_size", portfolio_snapshot.get("strategy_count", 0))
        self.set("icyquant_gross_exposure", portfolio_snapshot.get("gross_exposure", 0))
        self.set("icyquant_net_exposure", portfolio_snapshot.get("net_exposure", 0))
        self.set("icyquant_long_exposure", portfolio_snapshot.get("long_exposure", 0))
        self.set("icyquant_short_exposure", portfolio_snapshot.get("short_exposure", 0))
        self.set("icyquant_portfolio_resilience_score", portfolio_snapshot.get("resilience_score", 1.0))

    def record_rebalance(self, plan: Dict[str, Any]) -> None:
        self.inc("icyquant_portfolio_rebalance_total")
        if plan.get("action") == "SKIP":
            self.inc("icyquant_rebalance_skipped_total")
        self.set("icyquant_portfolio_turnover", plan.get("total_turnover", 0))
        self.set("icyquant_portfolio_drift", plan.get("drift", 0))

    def get_all_counters(self) -> Dict[str, float]:
        return dict(self._counters)

    def get_all_gauges(self) -> Dict[str, float]:
        return dict(self._gauges)
