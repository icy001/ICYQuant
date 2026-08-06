"""Factor Metrics — Prometheus-compatible metrics for the factor research engine.

Metrics::

    icyquant_factor_total, icyquant_factor_ic, icyquant_factor_rankic,
    icyquant_factor_icir, icyquant_factor_decay, icyquant_factor_turnover,
    icyquant_factor_alpha_pool
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

    def get(self) -> float:
        with self._lock:
            return self._value


@dataclass
class MetricHistogram:
    """Simple histogram metric."""

    name: str
    help: str
    _values: List[float] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    labels: Dict[str, str] = field(default_factory=dict)

    def observe(self, value: float) -> None:
        with self._lock:
            self._values.append(value)

    def stats(self) -> Dict[str, float]:
        with self._lock:
            if not self._values:
                return {"count": 0, "sum": 0.0, "avg": 0.0}
            return {
                "count": len(self._values),
                "sum": sum(self._values),
                "avg": sum(self._values) / len(self._values),
                "min": min(self._values),
                "max": max(self._values),
            }


class FactorMetrics:
    """Factor research engine metrics registry.

    Tracks:
    * Factor computation counts
    * IC / RankIC values
    * ICIR values
    * Decay analysis metrics
    * Turnover analysis metrics
    * Alpha pool state
    """

    def __init__(self) -> None:
        # Counters
        self.factor_total = MetricCounter(
            name="icyquant_factor_total",
            help="Total number of factors computed",
        )
        self.factor_evaluated_total = MetricCounter(
            name="icyquant_factor_evaluated_total",
            help="Total number of factors evaluated",
        )
        self.factor_published_total = MetricCounter(
            name="icyquant_factor_published_total",
            help="Total number of factors published to alpha pool",
        )
        self.factor_error_total = MetricCounter(
            name="icyquant_factor_error_total",
            help="Total number of factor computation errors",
        )

        # Gauges
        self.factor_ic = MetricGauge(
            name="icyquant_factor_ic",
            help="Latest Information Coefficient",
        )
        self.factor_rankic = MetricGauge(
            name="icyquant_factor_rankic",
            help="Latest Rank Information Coefficient",
        )
        self.factor_icir = MetricGauge(
            name="icyquant_factor_icir",
            help="Latest ICIR value",
        )
        self.factor_decay = MetricGauge(
            name="icyquant_factor_decay",
            help="Latest decay half-life (days)",
        )
        self.factor_turnover = MetricGauge(
            name="icyquant_factor_turnover",
            help="Latest average turnover rate",
        )
        self.factor_alpha_pool_size = MetricGauge(
            name="icyquant_factor_alpha_pool",
            help="Current alpha pool size",
        )

        # Histograms
        self.ic_distribution = MetricHistogram(
            name="icyquant_factor_ic_distribution",
            help="Distribution of IC values",
        )
        self.pipeline_duration = MetricHistogram(
            name="icyquant_factor_pipeline_duration_seconds",
            help="Factor pipeline execution duration",
        )

        # Feature metrics
        self.feature_generated_total = MetricCounter(
            name="icyquant_feature_generated_total",
            help="Total features generated",
        )
        self.feature_cache_hits = MetricCounter(
            name="icyquant_feature_cache_hits",
            help="Feature cache hits",
        )
        self.feature_cache_misses = MetricCounter(
            name="icyquant_feature_cache_misses",
            help="Feature cache misses",
        )

    def record_factor_computed(self, ic: float = 0.0) -> None:
        self.factor_total.inc()
        if ic != 0.0:
            self.ic_distribution.observe(ic)

    def record_factor_evaluated(self) -> None:
        self.factor_evaluated_total.inc()

    def record_factor_published(self) -> None:
        self.factor_published_total.inc()

    def record_factor_error(self) -> None:
        self.factor_error_total.inc()

    def record_ic(self, value: float) -> None:
        self.factor_ic.set(value)

    def record_rankic(self, value: float) -> None:
        self.factor_rankic.set(value)

    def record_icir(self, value: float) -> None:
        self.factor_icir.set(value)

    def record_decay(self, half_life: float) -> None:
        self.factor_decay.set(half_life)

    def record_turnover(self, value: float) -> None:
        self.factor_turnover.set(value)

    def record_alpha_pool_size(self, size: int) -> None:
        self.factor_alpha_pool_size.set(float(size))

    def record_pipeline_duration(self, seconds: float) -> None:
        self.pipeline_duration.observe(seconds)

    def record_feature_cache_hit(self) -> None:
        self.feature_cache_hits.inc()

    def record_feature_cache_miss(self) -> None:
        self.feature_cache_misses.inc()

    def cache_hit_rate(self) -> float:
        hits = self.feature_cache_hits.get()
        misses = self.feature_cache_misses.get()
        total = hits + misses
        return hits / total if total > 0 else 0.0

    def snapshot(self) -> Dict[str, Any]:
        """Take a snapshot of all metrics."""
        return {
            "counters": {
                "factor_total": self.factor_total.get(),
                "factor_evaluated_total": self.factor_evaluated_total.get(),
                "factor_published_total": self.factor_published_total.get(),
                "factor_error_total": self.factor_error_total.get(),
                "feature_generated_total": self.feature_generated_total.get(),
                "feature_cache_hits": self.feature_cache_hits.get(),
                "feature_cache_misses": self.feature_cache_misses.get(),
            },
            "gauges": {
                "factor_ic": self.factor_ic.get(),
                "factor_rankic": self.factor_rankic.get(),
                "factor_icir": self.factor_icir.get(),
                "factor_decay": self.factor_decay.get(),
                "factor_turnover": self.factor_turnover.get(),
                "factor_alpha_pool_size": self.factor_alpha_pool_size.get(),
            },
            "histograms": {
                "ic_distribution": self.ic_distribution.stats(),
                "pipeline_duration": self.pipeline_duration.stats(),
            },
            "cache_hit_rate": self.cache_hit_rate(),
        }
