"""Portfolio Metrics — Prometheus-compatible metrics for portfolio research.

Metrics::

    icyquant_portfolio_total
    icyquant_portfolio_optimizer_runtime
    icyquant_portfolio_turnover
    icyquant_portfolio_tracking_error
    icyquant_portfolio_var
    icyquant_portfolio_cvar
    icyquant_portfolio_stress_tests
"""

from __future__ import annotations

import logging
import threading
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
    """Thread-safe histogram metric."""

    name: str
    help: str
    buckets: List[float] = field(default_factory=lambda: [
        0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0,
    ])
    _counts: List[int] = field(default_factory=list)
    _sum: float = 0.0
    _count: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        self._counts = [0] * (len(self.buckets) + 1)

    def observe(self, value: float) -> None:
        with self._lock:
            self._sum += value
            self._count += 1
            for i, bound in enumerate(self.buckets):
                if value <= bound:
                    self._counts[i] += 1
                    return
            self._counts[-1] += 1


class PortfolioMetrics:
    """Metrics collector for portfolio research.

    Tracks portfolio construction, optimization, risk, and
    stress testing operations with Prometheus-compatible metrics.
    """

    def __init__(self) -> None:
        # Counters
        self.total_portfolios = MetricCounter(
            name="icyquant_portfolio_total",
            help="Total number of portfolios created",
        )
        self.total_optimizations = MetricCounter(
            name="icyquant_portfolio_optimizations_total",
            help="Total number of optimization runs",
        )
        self.total_stress_tests = MetricCounter(
            name="icyquant_portfolio_stress_tests",
            help="Total number of stress test runs",
        )
        self.total_reports = MetricCounter(
            name="icyquant_portfolio_reports_total",
            help="Total number of portfolio reports generated",
        )

        # Gauges
        self.active_turnover = MetricGauge(
            name="icyquant_portfolio_turnover",
            help="Latest portfolio turnover ratio",
        )
        self.active_tracking_error = MetricGauge(
            name="icyquant_portfolio_tracking_error",
            help="Latest tracking error (annualized)",
        )
        self.active_var = MetricGauge(
            name="icyquant_portfolio_var",
            help="Latest VaR estimate (95% confidence)",
        )
        self.active_cvar = MetricGauge(
            name="icyquant_portfolio_cvar",
            help="Latest CVaR estimate (95% confidence)",
        )
        self.active_sharpe = MetricGauge(
            name="icyquant_portfolio_sharpe",
            help="Latest portfolio Sharpe ratio",
        )

        # Histograms
        self.optimizer_runtime = MetricHistogram(
            name="icyquant_portfolio_optimizer_runtime",
            help="Optimizer runtime distribution (seconds)",
        )

    def record_portfolio_created(self) -> None:
        self.total_portfolios.inc()

    def record_optimization(
        self, sharpe: float, turnover: float, runtime_seconds: float
    ) -> None:
        self.total_optimizations.inc()
        self.active_sharpe.set(sharpe)
        self.active_turnover.set(turnover)
        self.optimizer_runtime.observe(runtime_seconds)

    def record_risk(
        self, var: float, cvar: float, tracking_error: float
    ) -> None:
        self.active_var.set(var)
        self.active_cvar.set(cvar)
        self.active_tracking_error.set(tracking_error)

    def record_stress_test(self, max_loss: float) -> None:
        self.total_stress_tests.inc()

    def record_report(self) -> None:
        self.total_reports.inc()

    def collect(self) -> Dict[str, Any]:
        """Collect all metrics for export."""
        return {
            "icyquant_portfolio_total": self.total_portfolios.get(),
            "icyquant_portfolio_optimizations_total": self.total_optimizations.get(),
            "icyquant_portfolio_stress_tests": self.total_stress_tests.get(),
            "icyquant_portfolio_reports_total": self.total_reports.get(),
            "icyquant_portfolio_turnover": self.active_turnover.get(),
            "icyquant_portfolio_tracking_error": self.active_tracking_error.get(),
            "icyquant_portfolio_var": self.active_var.get(),
            "icyquant_portfolio_cvar": self.active_cvar.get(),
            "icyquant_portfolio_sharpe": self.active_sharpe.get(),
        }
