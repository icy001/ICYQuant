"""Metrics Exporter.

Exports metrics in various formats:
- Prometheus text format
- JSON
- Dict (for API responses)

Usage::

    exporter = MetricsExporter()
    prom_text = exporter.export_prometheus(collector, aggregator)
    json_data = exporter.export_json(collector)
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Dict, List, Optional

from services.monitoring.metrics.collector import MetricsCollector
from services.monitoring.metrics.aggregator import MetricsAggregator, AggregationWindow
from services.monitoring.metrics.timeseries import TimeSeriesStore


class ExportFormat(str, Enum):
    JSON = "json"
    PROMETHEUS = "prometheus"
    DICT = "dict"


class MetricsExporter:
    """Exports collected metrics to various formats."""

    def export(
        self,
        collector: MetricsCollector,
        aggregator: Optional[MetricsAggregator] = None,
        timeseries: Optional[TimeSeriesStore] = None,
        fmt: ExportFormat = ExportFormat.DICT,
    ) -> Any:
        """Export metrics in the specified format."""
        if fmt == ExportFormat.DICT:
            return self.export_dict(collector, aggregator, timeseries)
        elif fmt == ExportFormat.JSON:
            return self.export_json(collector, aggregator, timeseries)
        elif fmt == ExportFormat.PROMETHEUS:
            return self.export_prometheus(collector, aggregator, timeseries)
        return {}

    def export_dict(
        self,
        collector: MetricsCollector,
        aggregator: Optional[MetricsAggregator] = None,
        timeseries: Optional[TimeSeriesStore] = None,
    ) -> Dict[str, Any]:
        """Export as a Python dict."""
        result: Dict[str, Any] = {
            "business": collector.get_business().to_dict(),
            "system": collector.get_system().to_dict(),
        }

        if aggregator:
            result["aggregations"] = {}
            for name in aggregator.list_metrics():
                result["aggregations"][name] = {
                    w.value: aggregator.get_stats(name, w).to_dict()
                    for w in AggregationWindow
                    if w != AggregationWindow.ALL
                }

        if timeseries:
            result["timeseries"] = {
                name: ts.to_dict()
                for name, ts in timeseries._series.items()
            }

        return result

    def export_json(
        self,
        collector: MetricsCollector,
        aggregator: Optional[MetricsAggregator] = None,
        timeseries: Optional[TimeSeriesStore] = None,
    ) -> str:
        """Export as JSON string."""
        data = self.export_dict(collector, aggregator, timeseries)
        return json.dumps(data, indent=2, default=str)

    def export_prometheus(
        self,
        collector: MetricsCollector,
        aggregator: Optional[MetricsAggregator] = None,
        timeseries: Optional[TimeSeriesStore] = None,
    ) -> str:
        """Export in Prometheus text format.

        https://prometheus.io/docs/instrumenting/exposition_formats/
        """
        lines: List[str] = []

        # Help text and type for each metric
        business = collector.get_business()
        system = collector.get_system()

        # Business metrics
        lines.append("# HELP icyquant_orders_per_sec Orders per second")
        lines.append("# TYPE icyquant_orders_per_sec gauge")
        lines.append(f"icyquant_orders_per_sec {business.orders_per_sec}")

        lines.append("# HELP icyquant_trades_per_sec Trades per second")
        lines.append("# TYPE icyquant_trades_per_sec gauge")
        lines.append(f"icyquant_trades_per_sec {business.trades_per_sec}")

        lines.append("# HELP icyquant_pnl Current PnL")
        lines.append("# TYPE icyquant_pnl gauge")
        lines.append(f"icyquant_pnl {business.pnl}")

        lines.append("# HELP icyquant_nav Current NAV")
        lines.append("# TYPE icyquant_nav gauge")
        lines.append(f"icyquant_nav {business.nav}")

        lines.append("# HELP icyquant_aum Assets Under Management")
        lines.append("# TYPE icyquant_aum gauge")
        lines.append(f"icyquant_aum {business.aum}")

        lines.append("# HELP icyquant_sharpe Sharpe ratio")
        lines.append("# TYPE icyquant_sharpe gauge")
        lines.append(f"icyquant_sharpe {business.sharpe}")

        lines.append("# HELP icyquant_drawdown_pct Current drawdown percentage")
        lines.append("# TYPE icyquant_drawdown_pct gauge")
        lines.append(f"icyquant_drawdown_pct {business.drawdown_pct}")

        lines.append("# HELP icyquant_win_rate Trade win rate")
        lines.append("# TYPE icyquant_win_rate gauge")
        lines.append(f"icyquant_win_rate {business.win_rate}")

        lines.append("# HELP icyquant_profit_factor Profit factor")
        lines.append("# TYPE icyquant_profit_factor gauge")
        lines.append(f"icyquant_profit_factor {business.profit_factor}")

        lines.append("# HELP icyquant_total_orders Total orders")
        lines.append("# TYPE icyquant_total_orders counter")
        lines.append(f"icyquant_total_orders {business.total_orders}")

        lines.append("# HELP icyquant_total_trades Total trades")
        lines.append("# TYPE icyquant_total_trades counter")
        lines.append(f"icyquant_total_trades {business.total_trades}")

        lines.append("# HELP icyquant_fill_rate_pct Fill rate percentage")
        lines.append("# TYPE icyquant_fill_rate_pct gauge")
        lines.append(f"icyquant_fill_rate_pct {business.fill_rate_pct}")

        # System metrics
        lines.append("# HELP icyquant_cpu_pct CPU usage percentage")
        lines.append("# TYPE icyquant_cpu_pct gauge")
        lines.append(f"icyquant_cpu_pct {system.cpu_pct}")

        lines.append("# HELP icyquant_memory_pct Memory usage percentage")
        lines.append("# TYPE icyquant_memory_pct gauge")
        lines.append(f"icyquant_memory_pct {system.memory_pct}")

        lines.append("# HELP icyquant_disk_pct Disk usage percentage")
        lines.append("# TYPE icyquant_disk_pct gauge")
        lines.append(f"icyquant_disk_pct {system.disk_pct}")

        lines.append("# HELP icyquant_redis_latency_ms Redis latency in ms")
        lines.append("# TYPE icyquant_redis_latency_ms gauge")
        lines.append(f"icyquant_redis_latency_ms {system.redis_latency_ms}")

        lines.append("# HELP icyquant_kafka_latency_ms Kafka latency in ms")
        lines.append("# TYPE icyquant_kafka_latency_ms gauge")
        lines.append(f"icyquant_kafka_latency_ms {system.kafka_latency_ms}")

        lines.append("# HELP icyquant_postgres_latency_ms Postgres latency in ms")
        lines.append("# TYPE icyquant_postgres_latency_ms gauge")
        lines.append(f"icyquant_postgres_latency_ms {system.postgres_latency_ms}")

        lines.append("# HELP icyquant_api_latency_p50 API latency p50 in ms")
        lines.append("# TYPE icyquant_api_latency_p50 gauge")
        lines.append(f"icyquant_api_latency_p50 {system.api_latency_p50}")

        lines.append("# HELP icyquant_api_latency_p99 API latency p99 in ms")
        lines.append("# TYPE icyquant_api_latency_p99 gauge")
        lines.append(f"icyquant_api_latency_p99 {system.api_latency_p99}")

        lines.append("# HELP icyquant_api_error_rate API error rate")
        lines.append("# TYPE icyquant_api_error_rate gauge")
        lines.append(f"icyquant_api_error_rate {system.api_error_rate}")

        # Redis/Kafka/Postgres availability
        lines.append("# HELP icyquant_redis_available Redis available (1=yes)")
        lines.append("# TYPE icyquant_redis_available gauge")
        lines.append(f"icyquant_redis_available {1 if system.redis_available else 0}")

        lines.append("# HELP icyquant_kafka_available Kafka available (1=yes)")
        lines.append("# TYPE icyquant_kafka_available gauge")
        lines.append(f"icyquant_kafka_available {1 if system.kafka_available else 0}")

        lines.append("# HELP icyquant_postgres_available Postgres available (1=yes)")
        lines.append("# TYPE icyquant_postgres_available gauge")
        lines.append(f"icyquant_postgres_available {1 if system.postgres_available else 0}")

        lines.append("")  # End with newline
        return "\n".join(lines)
