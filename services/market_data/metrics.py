"""
Market Data Metrics — Prometheus-style metrics for the normalization
pipeline and data quality framework.

Commit 16 Part 1.2
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MetricCounter:
    """A monotonically increasing counter."""
    name: str = ""
    help: str = ""
    value: int = 0
    labels: dict[str, str] = field(default_factory=dict)

    def inc(self, amount: int = 1) -> None:
        self.value += amount


@dataclass
class MetricGauge:
    """A value that can go up and down."""
    name: str = ""
    help: str = ""
    value: float = 0.0
    labels: dict[str, str] = field(default_factory=dict)

    def set(self, value: float) -> None:
        self.value = value

    def inc(self, amount: float = 1.0) -> None:
        self.value += amount

    def dec(self, amount: float = 1.0) -> None:
        self.value -= amount


@dataclass
class MetricHistogram:
    """A histogram of observed values."""
    name: str = ""
    help: str = ""
    values: list[float] = field(default_factory=list)
    sum: float = 0.0
    count: int = 0
    labels: dict[str, str] = field(default_factory=dict)

    def observe(self, value: float) -> None:
        self.values.append(value)
        self.sum += value
        self.count += 1

    @property
    def avg(self) -> float:
        return self.sum / max(self.count, 1)


class MarketDataMetrics:
    """
    Market data normalization pipeline metrics.

    Metrics:
    - icyquant_market_ticks_total: Total ticks received
    - icyquant_market_quotes_total: Total quotes received
    - icyquant_market_trades_total: Total trades received
    - icyquant_market_normalization_latency: Normalization latency (us)
    - icyquant_market_validation_errors_total: Total validation errors
    - icyquant_market_duplicate_total: Total duplicate records
    - icyquant_market_gap_total: Total gap events
    - icyquant_market_outlier_total: Total outlier events
    - icyquant_market_quality_score: Overall data quality score
    """

    def __init__(self) -> None:
        # Counters
        self.ticks_total = MetricCounter(
            name="icyquant_market_ticks_total",
            help="Total market tick events received",
        )
        self.quotes_total = MetricCounter(
            name="icyquant_market_quotes_total",
            help="Total market quote events received",
        )
        self.trades_total = MetricCounter(
            name="icyquant_market_trades_total",
            help="Total market trade events received",
        )
        self.orderbooks_total = MetricCounter(
            name="icyquant_market_orderbooks_total",
            help="Total order book events received",
        )
        self.klines_total = MetricCounter(
            name="icyquant_market_klines_total",
            help="Total kline events received",
        )

        # Pipeline counters
        self.normalized_total = MetricCounter(
            name="icyquant_market_normalized_total",
            help="Total events successfully normalized",
        )
        self.validation_errors_total = MetricCounter(
            name="icyquant_market_validation_errors_total",
            help="Total validation errors",
        )
        self.duplicate_total = MetricCounter(
            name="icyquant_market_duplicate_total",
            help="Total duplicate events detected",
        )
        self.gap_total = MetricCounter(
            name="icyquant_market_gap_total",
            help="Total gap events detected",
        )
        self.outlier_total = MetricCounter(
            name="icyquant_market_outlier_total",
            help="Total outlier events detected",
        )
        self.rejected_total = MetricCounter(
            name="icyquant_market_rejected_total",
            help="Total events rejected",
        )

        # Histograms
        self.normalization_latency = MetricHistogram(
            name="icyquant_market_normalization_latency",
            help="Normalization processing latency in microseconds",
        )
        self.validation_latency = MetricHistogram(
            name="icyquant_market_validation_latency",
            help="Validation processing latency in microseconds",
        )
        self.pipeline_latency = MetricHistogram(
            name="icyquant_market_pipeline_latency",
            help="Full pipeline processing latency in microseconds",
        )

        # Gauges
        self.quality_score = MetricGauge(
            name="icyquant_market_quality_score",
            help="Overall data quality score (0-100)",
        )
        self.active_instruments = MetricGauge(
            name="icyquant_market_active_instruments",
            help="Number of active instruments being tracked",
        )
        self.cache_hit_rate = MetricGauge(
            name="icyquant_market_cache_hit_rate",
            help="Cache hit rate percentage",
        )

    def record_tick(self) -> None:
        self.ticks_total.inc()

    def record_quote(self) -> None:
        self.quotes_total.inc()

    def record_trade(self) -> None:
        self.trades_total.inc()

    def record_orderbook(self) -> None:
        self.orderbooks_total.inc()

    def record_kline(self) -> None:
        self.klines_total.inc()

    def record_normalized(self, count: int = 1) -> None:
        self.normalized_total.inc(count)

    def record_validation_error(self, count: int = 1) -> None:
        self.validation_errors_total.inc(count)

    def record_duplicate(self, count: int = 1) -> None:
        self.duplicate_total.inc(count)

    def record_gap(self, count: int = 1) -> None:
        self.gap_total.inc(count)

    def record_outlier(self, count: int = 1) -> None:
        self.outlier_total.inc(count)

    def record_rejected(self, count: int = 1) -> None:
        self.rejected_total.inc(count)

    def record_normalization_latency_us(self, us: float) -> None:
        self.normalization_latency.observe(us)

    def record_validation_latency_us(self, us: float) -> None:
        self.validation_latency.observe(us)

    def record_pipeline_latency_us(self, us: float) -> None:
        self.pipeline_latency.observe(us)

    def set_quality_score(self, score: float) -> None:
        self.quality_score.set(score)

    def set_active_instruments(self, count: int) -> None:
        self.active_instruments.set(float(count))

    def set_cache_hit_rate(self, rate: float) -> None:
        self.cache_hit_rate.set(rate)

    def snapshot(self) -> dict[str, Any]:
        """Return a snapshot of all current metric values."""
        return {
            "ticks_total": self.ticks_total.value,
            "quotes_total": self.quotes_total.value,
            "trades_total": self.trades_total.value,
            "orderbooks_total": self.orderbooks_total.value,
            "klines_total": self.klines_total.value,
            "normalized_total": self.normalized_total.value,
            "validation_errors_total": self.validation_errors_total.value,
            "duplicate_total": self.duplicate_total.value,
            "gap_total": self.gap_total.value,
            "outlier_total": self.outlier_total.value,
            "rejected_total": self.rejected_total.value,
            "normalization_latency_avg_us": self.normalization_latency.avg,
            "validation_latency_avg_us": self.validation_latency.avg,
            "pipeline_latency_avg_us": self.pipeline_latency.avg,
            "quality_score": self.quality_score.value,
            "active_instruments": self.active_instruments.value,
            "cache_hit_rate": self.cache_hit_rate.value,
        }
