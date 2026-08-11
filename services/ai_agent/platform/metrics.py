"""Platform Metrics — Prometheus-compatible metrics for the unified AI Platform.

Metrics exposed:
    icyquant_ai_requests_total       — Counter: total AI platform requests
    icyquant_ai_model_calls_total    — Counter: total model calls
    icyquant_ai_provider_latency     — Histogram: provider response latency
    icyquant_ai_budget_usage         — Gauge: current budget utilization %
    icyquant_ai_guardrail_blocks     — Counter: guardrail block events
    icyquant_ai_reasoning_duration   — Histogram: reasoning phase duration
    icyquant_ai_cost_total           — Counter: cumulative cost in USD
    icyquant_ai_audit_records        — Counter: total audit records created
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class _MetricSnapshot:
    name: str
    type: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.monotonic)


class PlatformMetrics:
    """Collector for AI Platform metrics.

    Thread-safe in-process metrics store exposing 8 built-in Prometheus-
    compatible metrics for platform observability.

    Usage:
        metrics = PlatformMetrics()
        await metrics.initialize()
        metrics.ai_requests_total.inc()
        metrics.ai_budget_usage.set(75.0)
        print(metrics.to_dict())
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._initialized: bool = False
        logger.info("PlatformMetrics created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("PlatformMetrics initialized")

    async def shutdown(self) -> None:
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
        self._initialized = False
        logger.info("PlatformMetrics shutdown complete")

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
    def ai_requests_total(self) -> "_CounterHandle":
        return self.counter("icyquant_ai_requests_total")

    @property
    def ai_model_calls_total(self) -> "_CounterHandle":
        return self.counter("icyquant_ai_model_calls_total")

    @property
    def ai_provider_latency(self) -> "_HistogramHandle":
        return self.histogram("icyquant_ai_provider_latency")

    @property
    def ai_budget_usage(self) -> "_GaugeHandle":
        return self.gauge("icyquant_ai_budget_usage")

    @property
    def ai_guardrail_blocks(self) -> "_CounterHandle":
        return self.counter("icyquant_ai_guardrail_blocks")

    @property
    def ai_reasoning_duration(self) -> "_HistogramHandle":
        return self.histogram("icyquant_ai_reasoning_duration")

    @property
    def ai_cost_total(self) -> "_CounterHandle":
        return self.counter("icyquant_ai_cost_total")

    @property
    def ai_audit_records(self) -> "_CounterHandle":
        return self.counter("icyquant_ai_audit_records")

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
    def __init__(self, name: str, parent: PlatformMetrics) -> None:
        self._name = name
        self._parent = parent

    def inc(self, amount: float = 1.0) -> None:
        self._parent._inc_counter(self._name, amount)

    def get(self) -> float:
        with self._parent._lock:
            return self._parent._counters.get(self._name, 0.0)


class _GaugeHandle:
    def __init__(self, name: str, parent: PlatformMetrics) -> None:
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
    def __init__(self, name: str, parent: PlatformMetrics) -> None:
        self._name = name
        self._parent = parent

    def observe(self, value: float) -> None:
        self._parent._add_histogram(self._name, value)
