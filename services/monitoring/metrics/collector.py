"""Metrics Collector.

Unified metrics collection for both business and system metrics.

Business metrics:
- Orders/sec, Trades/sec, PnL, NAV, AUM, Sharpe, Drawdown

System metrics:
- CPU, Memory, Disk, Redis, Kafka, Postgres latency/throughput

Usage::

    collector = MetricsCollector()
    collector.collect_business("pnl", 250000.0)
    collector.collect_system("cpu_pct", 45.2)
    snapshot = collector.snapshot()
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class MetricType(str, Enum):
    GAUGE = "gauge"
    COUNTER = "counter"
    HISTOGRAM = "histogram"


@dataclass
class BusinessMetrics:
    """Snapshot of business-level metrics."""

    orders_per_sec: float = 0.0
    trades_per_sec: float = 0.0
    pnl: float = 0.0
    nav: float = 0.0
    aum: float = 0.0
    sharpe: float = 0.0
    drawdown_pct: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_orders: int = 0
    total_trades: int = 0
    fill_rate_pct: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "orders_per_sec": self.orders_per_sec,
            "trades_per_sec": self.trades_per_sec,
            "pnl": self.pnl,
            "nav": self.nav,
            "aum": self.aum,
            "sharpe": self.sharpe,
            "drawdown_pct": self.drawdown_pct,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "total_orders": self.total_orders,
            "total_trades": self.total_trades,
            "fill_rate_pct": self.fill_rate_pct,
            "timestamp": self.timestamp,
        }


@dataclass
class SystemMetrics:
    """Snapshot of infrastructure/system metrics."""

    cpu_pct: float = 0.0
    memory_pct: float = 0.0
    disk_pct: float = 0.0
    redis_latency_ms: float = 0.0
    kafka_latency_ms: float = 0.0
    postgres_latency_ms: float = 0.0
    redis_available: bool = True
    kafka_available: bool = True
    postgres_available: bool = True
    api_latency_p50: float = 0.0
    api_latency_p99: float = 0.0
    api_error_rate: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cpu_pct": self.cpu_pct,
            "memory_pct": self.memory_pct,
            "disk_pct": self.disk_pct,
            "redis_latency_ms": self.redis_latency_ms,
            "kafka_latency_ms": self.kafka_latency_ms,
            "postgres_latency_ms": self.postgres_latency_ms,
            "redis_available": self.redis_available,
            "kafka_available": self.kafka_available,
            "postgres_available": self.postgres_available,
            "api_latency_p50": self.api_latency_p50,
            "api_latency_p99": self.api_latency_p99,
            "api_error_rate": self.api_error_rate,
            "timestamp": self.timestamp,
        }


class MetricsCollector:
    """Collects and holds the latest metrics snapshot.

    This is the central collection point for all monitoring metrics.
    Both business and system metrics are collected here.
    """

    def __init__(self) -> None:
        self._business = BusinessMetrics()
        self._system = SystemMetrics()
        self._custom_gauges: Dict[str, float] = {}
        self._custom_counters: Dict[str, int] = {}
        self._collection_count: int = 0
        self._last_collection: float = 0.0

    # ------------------------------------------------------------------
    # Business metrics
    # ------------------------------------------------------------------

    def collect_business(self, name: str, value: Any) -> None:
        """Set a business metric value."""
        if hasattr(self._business, name):
            setattr(self._business, name, value)
        else:
            self._custom_gauges[name] = float(value)
        self._mark_collected()

    def set_business_snapshot(self, metrics: BusinessMetrics) -> None:
        """Replace entire business metrics snapshot."""
        self._business = metrics
        self._mark_collected()

    def get_business(self) -> BusinessMetrics:
        """Get current business metrics snapshot."""
        return self._business

    # ------------------------------------------------------------------
    # System metrics
    # ------------------------------------------------------------------

    def collect_system(self, name: str, value: Any) -> None:
        """Set a system metric value."""
        if hasattr(self._system, name):
            setattr(self._system, name, value)
        else:
            self._custom_gauges[f"sys_{name}"] = float(value)
        self._mark_collected()

    def set_system_snapshot(self, metrics: SystemMetrics) -> None:
        """Replace entire system metrics snapshot."""
        self._system = metrics
        self._mark_collected()

    def get_system(self) -> SystemMetrics:
        """Get current system metrics snapshot."""
        return self._system

    # ------------------------------------------------------------------
    # Counters
    # ------------------------------------------------------------------

    def increment_counter(self, name: str, delta: int = 1) -> int:
        """Increment a named counter."""
        current = self._custom_counters.get(name, 0)
        current += delta
        self._custom_counters[name] = current
        return current

    def get_counter(self, name: str) -> int:
        """Get current counter value."""
        return self._custom_counters.get(name, 0)

    def reset_counter(self, name: str) -> None:
        """Reset a counter to 0."""
        self._custom_counters[name] = 0

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        """Get full metrics snapshot as a dict."""
        return {
            "business": self._business.to_dict(),
            "system": self._system.to_dict(),
            "custom_gauges": dict(self._custom_gauges),
            "counters": dict(self._custom_counters),
            "collection_count": self._collection_count,
            "last_collection": self._last_collection,
        }

    def reset(self) -> None:
        """Reset all metrics to defaults."""
        self._business = BusinessMetrics()
        self._system = SystemMetrics()
        self._custom_gauges.clear()
        self._custom_counters.clear()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _mark_collected(self) -> None:
        self._collection_count += 1
        self._last_collection = time.time()
