"""Backtest Metrics — Prometheus-compatible metrics for the backtesting engine.

Metrics::

    icyquant_backtest_total, icyquant_backtest_runtime_seconds,
    icyquant_backtest_orders_total, icyquant_backtest_trades_total,
    icyquant_backtest_slippage, icyquant_backtest_cost_total,
    icyquant_backtest_report_total
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MetricCounter:
    """Thread-safe counter metric."""

    name: str
    help: str
    _value: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)
    labels: Dict[str, str] = field(default_factory=dict)

    def inc(self, amount: int = 1) -> None:
        with self._lock:
            self._value += amount

    def get(self) -> int:
        with self._lock:
            return self._value


@dataclass
class MetricGauge:
    """Thread-safe gauge metric."""

    name: str
    help: str
    _value: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)
    labels: Dict[str, str] = field(default_factory=dict)

    def set(self, value: float) -> None:
        with self._lock:
            self._value = value

    def inc(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value += amount

    def dec(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value -= amount

    def get(self) -> float:
        with self._lock:
            return self._value


@dataclass
class MetricHistogram:
    """Simple histogram with explicit samples."""

    name: str
    help: str
    samples: List[float] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    labels: Dict[str, str] = field(default_factory=dict)

    def observe(self, value: float) -> None:
        with self._lock:
            self.samples.append(value)

    def get_summary(self) -> Dict[str, float]:
        with self._lock:
            if not self.samples:
                return {"count": 0, "sum": 0.0, "avg": 0.0, "min": 0.0, "max": 0.0}
            return {
                "count": len(self.samples),
                "sum": sum(self.samples),
                "avg": sum(self.samples) / len(self.samples),
                "min": min(self.samples),
                "max": max(self.samples),
            }


class BacktestMetrics:
    """Prometheus-compatible metrics collection for backtesting.

    Exposes 7 key metrics:
    * icyquant_backtest_total — total backtests run
    * icyquant_backtest_runtime_seconds — runtime histogram
    * icyquant_backtest_orders_total — total orders submitted
    * icyquant_backtest_trades_total — total trades executed
    * icyquant_backtest_slippage — average slippage
    * icyquant_backtest_cost_total — total transaction cost
    * icyquant_backtest_report_total — total reports generated
    """

    def __init__(self) -> None:
        # Counters
        self.backtest_total = MetricCounter(
            "icyquant_backtest_total", "Total number of backtests executed",
        )
        self.orders_total = MetricCounter(
            "icyquant_backtest_orders_total", "Total orders submitted",
        )
        self.trades_total = MetricCounter(
            "icyquant_backtest_trades_total", "Total trades executed",
        )
        self.report_total = MetricCounter(
            "icyquant_backtest_report_total", "Total reports generated",
        )

        # Gauges
        self.active_backtests = MetricGauge(
            "icyquant_backtest_active", "Currently active backtests",
        )
        self.current_cost = MetricGauge(
            "icyquant_backtest_cost_total", "Cumulative transaction cost",
        )
        self.avg_slippage = MetricGauge(
            "icyquant_backtest_slippage", "Average execution slippage",
        )

        # Histogram
        self.runtime_seconds = MetricHistogram(
            "icyquant_backtest_runtime_seconds", "Backtest runtime in seconds",
        )

    # ── recording ──────────────────────────────────────────────────────────

    def record_backtest_start(self) -> None:
        self.active_backtests.inc()

    def record_backtest_complete(self, runtime_seconds: float) -> None:
        self.backtest_total.inc()
        self.active_backtests.dec()
        self.runtime_seconds.observe(runtime_seconds)

    def record_backtest_failed(self) -> None:
        self.active_backtests.dec()

    def record_order(self, count: int = 1) -> None:
        self.orders_total.inc(count)

    def record_trade(self, count: int = 1) -> None:
        self.trades_total.inc(count)

    def record_slippage(self, slippage_bps: float) -> None:
        self.avg_slippage.set(slippage_bps)

    def record_cost(self, cost: float) -> None:
        self.current_cost.inc(cost)

    def record_report(self) -> None:
        self.report_total.inc()

    # ── export ─────────────────────────────────────────────────────────────

    def collect(self) -> Dict[str, Any]:
        """Collect all metrics in Prometheus-compatible format."""
        return {
            "backtest_total": self.backtest_total.get(),
            "backtest_active": self.active_backtests.get(),
            "backtest_runtime_seconds": self.runtime_seconds.get_summary(),
            "orders_total": self.orders_total.get(),
            "trades_total": self.trades_total.get(),
            "avg_slippage": self.avg_slippage.get(),
            "cost_total": self.current_cost.get(),
            "report_total": self.report_total.get(),
        }

    def get_stats(self) -> Dict[str, Any]:
        return self.collect()
