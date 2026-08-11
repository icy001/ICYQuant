"""
Data Lake Metrics — Prometheus-style metrics for the enterprise
historical data lake covering ingestion, storage, query, replay,
and snapshot operations.

Commit 16 Part 1.3
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DataLakeMetrics:
    """
    Prometheus-style metrics registry for the data lake.

    Tracks counters, gauges, and histograms across all data lake
    subsystems: ingestion, storage, query, replay, snapshot, and
    lifecycle management.

    Metrics:
        icyquant_datalake_ingestion_total: Counter of total ingestions
        icyquant_datalake_ingestion_rows: Counter of ingested rows
        icyquant_datalake_ingestion_bytes: Counter of ingested bytes
        icyquant_datalake_ingestion_latency: Histogram of ingestion latency
        icyquant_datalake_ingestion_errors: Counter of ingestion errors
        icyquant_datalake_queries_total: Counter of total queries
        icyquant_datalake_query_rows_scanned: Counter of scanned rows
        icyquant_datalake_query_latency: Histogram of query latency
        icyquant_datalake_storage_bytes: Gauge of total storage bytes
        icyquant_datalake_storage_files: Gauge of total file count
        icyquant_datalake_compaction_total: Counter of compactions
        icyquant_datalake_replay_active: Gauge of active replays
        icyquant_datalake_replay_total: Counter of total replays
        icyquant_datalake_snapshots_total: Counter of snapshots
        icyquant_datalake_partitions_active: Gauge of active partitions

    Usage::

        metrics = DataLakeMetrics()
        metrics.record_ingestion("us_equity_trades", 5000000, 1024 * 1024 * 100)
        metrics.record_query("btc_usdt_orderbook", 100000, 0.5)
    """

    PREFIX = "icyquant_datalake"

    def __init__(self) -> None:
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}

        # ---- Ingestion Counters ----
        self._counters[f"{self.PREFIX}_ingestion_total"] = 0.0
        self._counters[f"{self.PREFIX}_ingestion_rows"] = 0.0
        self._counters[f"{self.PREFIX}_ingestion_bytes"] = 0.0
        self._counters[f"{self.PREFIX}_ingestion_errors"] = 0.0
        self._counters[f"{self.PREFIX}_ingestion_batches"] = 0.0

        # ---- Query Counters ----
        self._counters[f"{self.PREFIX}_queries_total"] = 0.0
        self._counters[f"{self.PREFIX}_query_rows_scanned"] = 0.0
        self._counters[f"{self.PREFIX}_query_errors"] = 0.0
        self._counters[f"{self.PREFIX}_time_travel_queries"] = 0.0

        # ---- Storage Counters ----
        self._counters[f"{self.PREFIX}_compaction_total"] = 0.0
        self._counters[f"{self.PREFIX}_compaction_bytes_saved"] = 0.0
        self._counters[f"{self.PREFIX}_snapshots_total"] = 0.0
        self._counters[f"{self.PREFIX}_retention_enforcements"] = 0.0

        # ---- Replay Counters ----
        self._counters[f"{self.PREFIX}_replay_total"] = 0.0
        self._counters[f"{self.PREFIX}_replay_events_total"] = 0.0

        # ---- Ingestion Histograms ----
        self._histograms[f"{self.PREFIX}_ingestion_latency"] = []
        self._histograms[f"{self.PREFIX}_query_latency"] = []
        self._histograms[f"{self.PREFIX}_compaction_latency"] = []
        self._histograms[f"{self.PREFIX}_replay_latency"] = []
        self._histograms[f"{self.PREFIX}_ingestion_batch_size"] = []

        # ---- Gauges ----
        self._gauges[f"{self.PREFIX}_storage_bytes"] = 0.0
        self._gauges[f"{self.PREFIX}_storage_files"] = 0.0
        self._gauges[f"{self.PREFIX}_replay_active"] = 0.0
        self._gauges[f"{self.PREFIX}_partitions_active"] = 0.0
        self._gauges[f"{self.PREFIX}_datasets_active"] = 0.0
        self._gauges[f"{self.PREFIX}_runtime_workers_busy"] = 0.0

    # ── Ingestion Metrics ─────────────────────────────────────────

    def record_ingestion(
        self,
        dataset: str,
        rows: int,
        bytes_written: int,
        latency_seconds: float = 0.0,
    ) -> None:
        """Record a data ingestion event."""
        self._counters[f"{self.PREFIX}_ingestion_total"] += 1
        self._counters[f"{self.PREFIX}_ingestion_rows"] += rows
        self._counters[f"{self.PREFIX}_ingestion_bytes"] += bytes_written
        self._histograms[f"{self.PREFIX}_ingestion_batch_size"].append(float(rows))
        if latency_seconds > 0:
            self._histograms[f"{self.PREFIX}_ingestion_latency"].append(latency_seconds)
        logger.debug(
            "Ingestion: %s rows=%d bytes=%d latency=%.3fs",
            dataset, rows, bytes_written, latency_seconds,
        )

    def record_ingestion_batch(
        self, dataset: str, batch_count: int = 1
    ) -> None:
        """Record ingestion batches."""
        self._counters[f"{self.PREFIX}_ingestion_batches"] += batch_count

    def record_ingestion_error(self, dataset: str, error: str = "") -> None:
        """Record an ingestion error."""
        self._counters[f"{self.PREFIX}_ingestion_errors"] += 1
        logger.warning("Ingestion error: %s — %s", dataset, error)

    # ── Query Metrics ─────────────────────────────────────────────

    def record_query(
        self,
        dataset: str,
        rows_scanned: int,
        latency_seconds: float = 0.0,
    ) -> None:
        """Record a query execution."""
        self._counters[f"{self.PREFIX}_queries_total"] += 1
        self._counters[f"{self.PREFIX}_query_rows_scanned"] += rows_scanned
        if latency_seconds > 0:
            self._histograms[f"{self.PREFIX}_query_latency"].append(latency_seconds)

    def record_time_travel_query(self, dataset: str) -> None:
        """Record a time-travel query."""
        self._counters[f"{self.PREFIX}_time_travel_queries"] += 1

    def record_query_error(self, dataset: str, error: str = "") -> None:
        """Record a query error."""
        self._counters[f"{self.PREFIX}_query_errors"] += 1
        logger.warning("Query error: %s — %s", dataset, error)

    # ── Storage Metrics ───────────────────────────────────────────

    def record_storage_bytes(self, total_bytes: int) -> None:
        """Set the total storage bytes gauge."""
        self._gauges[f"{self.PREFIX}_storage_bytes"] = float(total_bytes)

    def record_storage_files(self, file_count: int) -> None:
        """Set the total file count gauge."""
        self._gauges[f"{self.PREFIX}_storage_files"] = float(file_count)

    def record_compaction(
        self,
        dataset: str,
        bytes_saved: int = 0,
        latency_seconds: float = 0.0,
    ) -> None:
        """Record a compaction event."""
        self._counters[f"{self.PREFIX}_compaction_total"] += 1
        self._counters[f"{self.PREFIX}_compaction_bytes_saved"] += bytes_saved
        if latency_seconds > 0:
            self._histograms[f"{self.PREFIX}_compaction_latency"].append(latency_seconds)

    # ── Snapshot Metrics ──────────────────────────────────────────

    def record_snapshot(self, dataset: str) -> None:
        """Record a snapshot creation."""
        self._counters[f"{self.PREFIX}_snapshots_total"] += 1

    # ── Retention Metrics ─────────────────────────────────────────

    def record_retention_enforcement(
        self, dataset: str, files_removed: int
    ) -> None:
        """Record retention policy enforcement."""
        self._counters[f"{self.PREFIX}_retention_enforcements"] += 1

    # ── Replay Metrics ────────────────────────────────────────────

    def record_replay_start(self, dataset: str) -> None:
        """Record a replay start."""
        self._gauges[f"{self.PREFIX}_replay_active"] += 1

    def record_replay_end(
        self,
        dataset: str,
        total_events: int,
        latency_seconds: float = 0.0,
    ) -> None:
        """Record a replay completion."""
        self._counters[f"{self.PREFIX}_replay_total"] += 1
        self._counters[f"{self.PREFIX}_replay_events_total"] += total_events
        self._gauges[f"{self.PREFIX}_replay_active"] = max(
            0, self._gauges[f"{self.PREFIX}_replay_active"] - 1,
        )
        if latency_seconds > 0:
            self._histograms[f"{self.PREFIX}_replay_latency"].append(latency_seconds)

    # ── Lifetime Gauges ───────────────────────────────────────────

    def record_partitions_active(self, count: int) -> None:
        """Set active partitions gauge."""
        self._gauges[f"{self.PREFIX}_partitions_active"] = float(count)

    def record_datasets_active(self, count: int) -> None:
        """Set active datasets gauge."""
        self._gauges[f"{self.PREFIX}_datasets_active"] = float(count)

    def record_workers_busy(self, count: int) -> None:
        """Set busy workers gauge."""
        self._gauges[f"{self.PREFIX}_runtime_workers_busy"] = float(count)

    # ── Query API ─────────────────────────────────────────────────

    def get_counter(self, name: str) -> float:
        """Get a counter value."""
        full_name = f"{self.PREFIX}_{name}" if not name.startswith(self.PREFIX) else name
        return self._counters.get(full_name, 0.0)

    def get_gauge(self, name: str) -> float:
        """Get a gauge value."""
        full_name = f"{self.PREFIX}_{name}" if not name.startswith(self.PREFIX) else name
        return self._gauges.get(full_name, 0.0)

    def get_histogram_stats(self, name: str) -> dict[str, float]:
        """Get histogram statistics."""
        full_name = f"{self.PREFIX}_{name}" if not name.startswith(self.PREFIX) else name
        values = self._histograms.get(full_name, [])
        if not values:
            return {"count": 0, "sum": 0.0, "avg": 0.0, "min": 0.0, "max": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}

        sorted_vals = sorted(values)
        n = len(sorted_vals)
        return {
            "count": n,
            "sum": sum(sorted_vals),
            "avg": sum(sorted_vals) / n,
            "min": min(sorted_vals),
            "max": max(sorted_vals),
            "p50": sorted_vals[int(n * 0.50)] if n > 1 else sorted_vals[0],
            "p95": sorted_vals[int(n * 0.95)] if n > 1 else sorted_vals[0],
            "p99": sorted_vals[int(n * 0.99)] if n > 1 else sorted_vals[0],
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize all metrics to dictionary."""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                k: self.get_histogram_stats(k.replace(self.PREFIX + "_", ""))
                for k in self._histograms
            },
        }
