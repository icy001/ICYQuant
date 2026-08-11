"""Autonomy Metrics — Prometheus-compatible metrics for the autonomous research subsystem.

Metrics exposed:
    icyquant_autonomy_workflows_total        — Counter: total autonomous workflows
    icyquant_opportunities_detected_total    — Counter: opportunities detected
    icyquant_factor_discovery_total          — Counter: factors discovered
    icyquant_backtest_auto_total             — Counter: autonomous backtests run
    icyquant_portfolio_recommendation_total  — Counter: portfolio recommendations
    icyquant_hitl_requests_total             — Counter: HITL approval requests
    icyquant_learning_iterations_total       — Counter: learning iterations
    icyquant_confidence_score                — Gauge: current confidence score
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class _MetricSnapshot:
    name: str
    type: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.monotonic)


class AutonomyMetrics:
    """Collector for autonomous research subsystem metrics.

    Thread-safe in-process metrics store.

    Usage:
        metrics = AutonomyMetrics()
        await metrics.initialize()
        metrics.workflows_total.inc()
        metrics.confidence_score.set(0.85)
        print(metrics.to_dict())
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._initialized: bool = False
        logger.info("AutonomyMetrics created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("AutonomyMetrics initialized")

    async def shutdown(self) -> None:
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        self._initialized = False
        logger.info("AutonomyMetrics shutdown complete")

    def _inc_counter(self, name: str, amount: float = 1.0) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0.0) + amount

    def _set_gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = value

    def _add_histogram(self, name: str, value: float) -> None:
        with self._lock:
            self._histograms.setdefault(name, []).append(value)

    def counter(self, name: str) -> "_CounterHandle":
        return _CounterHandle(name, self)

    def gauge(self, name: str) -> "_GaugeHandle":
        return _GaugeHandle(name, self)

    def histogram(self, name: str) -> "_HistogramHandle":
        return _HistogramHandle(name, self)

    # ── Built-in Metrics ──

    @property
    def workflows_total(self) -> "_CounterHandle":
        return self.counter("icyquant_autonomy_workflows_total")

    @property
    def opportunities_detected_total(self) -> "_CounterHandle":
        return self.counter("icyquant_opportunities_detected_total")

    @property
    def factor_discovery_total(self) -> "_CounterHandle":
        return self.counter("icyquant_factor_discovery_total")

    @property
    def backtest_auto_total(self) -> "_CounterHandle":
        return self.counter("icyquant_backtest_auto_total")

    @property
    def portfolio_recommendation_total(self) -> "_CounterHandle":
        return self.counter("icyquant_portfolio_recommendation_total")

    @property
    def hitl_requests_total(self) -> "_CounterHandle":
        return self.counter("icyquant_hitl_requests_total")

    @property
    def learning_iterations_total(self) -> "_CounterHandle":
        return self.counter("icyquant_learning_iterations_total")

    @property
    def confidence_score(self) -> "_GaugeHandle":
        return self.gauge("icyquant_confidence_score")

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
            }

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            **self.to_dict(),
        }


class _CounterHandle:
    def __init__(self, name: str, parent: AutonomyMetrics) -> None:
        self._name = name
        self._parent = parent

    def inc(self, amount: float = 1.0) -> None:
        self._parent._inc_counter(self._name, amount)

    def get(self) -> float:
        with self._parent._lock:
            return self._parent._counters.get(self._name, 0.0)


class _GaugeHandle:
    def __init__(self, name: str, parent: AutonomyMetrics) -> None:
        self._name = name
        self._parent = parent

    def set(self, value: float) -> None:
        self._parent._set_gauge(self._name, value)

    def inc(self, amount: float = 1.0) -> None:
        with self._parent._lock:
            current = self._parent._gauges.get(self._name, 0.0)
            self._parent._gauges[self._name] = current + amount

    def dec(self, amount: float = 1.0) -> None:
        self.inc(-amount)

    def get(self) -> float:
        with self._parent._lock:
            return self._parent._gauges.get(self._name, 0.0)


class _HistogramHandle:
    def __init__(self, name: str, parent: AutonomyMetrics) -> None:
        self._name = name
        self._parent = parent

    def observe(self, value: float) -> None:
        self._parent._add_histogram(self._name, value)
