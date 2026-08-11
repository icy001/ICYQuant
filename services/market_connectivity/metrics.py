"""
Market Connectivity Metrics — Prometheus-compatible metrics for the
Market Connectivity Platform.

Tracks exchange connections, retries, failures, active sessions,
protocol latency, heartbeat timeouts, and endpoint switches.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MarketConnectivityMetrics:
    """
    Prometheus-style metrics for the Market Connectivity Platform.

    Metrics:
        icyquant_exchange_connections_total
        icyquant_connection_retries_total
        icyquant_connection_failures_total
        icyquant_session_active_total
        icyquant_protocol_latency
        icyquant_heartbeat_timeout_total
        icyquant_endpoint_switch_total
    """

    EXCHANGE_CONNECTIONS_TOTAL = "icyquant_exchange_connections_total"
    CONNECTION_RETRIES_TOTAL = "icyquant_connection_retries_total"
    CONNECTION_FAILURES_TOTAL = "icyquant_connection_failures_total"
    SESSION_ACTIVE_TOTAL = "icyquant_session_active_total"
    PROTOCOL_LATENCY = "icyquant_protocol_latency"
    HEARTBEAT_TIMEOUT_TOTAL = "icyquant_heartbeat_timeout_total"
    ENDPOINT_SWITCH_TOTAL = "icyquant_endpoint_switch_total"
    DISCONNECTION_TOTAL = "icyquant_disconnection_total"
    MESSAGES_SENT_TOTAL = "icyquant_messages_sent_total"
    MESSAGES_RECEIVED_TOTAL = "icyquant_messages_received_total"

    def __init__(self) -> None:
        self._counters: dict[str, float] = {
            self.EXCHANGE_CONNECTIONS_TOTAL: 0,
            self.CONNECTION_RETRIES_TOTAL: 0,
            self.CONNECTION_FAILURES_TOTAL: 0,
            self.SESSION_ACTIVE_TOTAL: 0,
            self.HEARTBEAT_TIMEOUT_TOTAL: 0,
            self.ENDPOINT_SWITCH_TOTAL: 0,
            self.DISCONNECTION_TOTAL: 0,
            self.MESSAGES_SENT_TOTAL: 0,
            self.MESSAGES_RECEIVED_TOTAL: 0,
        }
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._start_time: float = time.monotonic()

    # ---- Counters ----

    def increment(self, name: str, amount: float = 1.0) -> None:
        if name in self._counters:
            self._counters[name] += amount

    def record_connection_established(self) -> None:
        self.increment(self.EXCHANGE_CONNECTIONS_TOTAL)

    def record_connection_retry(self) -> None:
        self.increment(self.CONNECTION_RETRIES_TOTAL)

    def record_connection_failure(self) -> None:
        self.increment(self.CONNECTION_FAILURES_TOTAL)

    def record_disconnection(self) -> None:
        self.increment(self.DISCONNECTION_TOTAL)

    def record_heartbeat_timeout(self) -> None:
        self.increment(self.HEARTBEAT_TIMEOUT_TOTAL)

    def record_endpoint_switch(self) -> None:
        self.increment(self.ENDPOINT_SWITCH_TOTAL)

    def record_message_sent(self) -> None:
        self.increment(self.MESSAGES_SENT_TOTAL)

    def record_message_received(self) -> None:
        self.increment(self.MESSAGES_RECEIVED_TOTAL)

    # ---- Gauges ----

    def set_gauge(self, name: str, value: float) -> None:
        self._gauges[name] = value

    def set_active_sessions(self, count: int) -> None:
        self.set_gauge("active_sessions", float(count))
        self._counters[self.SESSION_ACTIVE_TOTAL] = float(count)

    def set_active_connections(self, count: int) -> None:
        self.set_gauge("active_connections", float(count))

    # ---- Histograms ----

    def record_histogram(self, name: str, value: float) -> None:
        if name not in self._histograms:
            self._histograms[name] = []
        self._histograms[name].append(value)
        if len(self._histograms[name]) > 1000:
            self._histograms[name] = self._histograms[name][-1000:]

    def record_protocol_latency(self, protocol: str, latency_ms: float) -> None:
        self.record_histogram(f"protocol_latency_{protocol}", latency_ms)

    def record_connection_duration(self, duration_ms: float) -> None:
        self.record_histogram("connection_duration", duration_ms)

    # ---- Snapshots ----

    def get_counters(self) -> dict[str, float]:
        return dict(self._counters)

    def get_gauges(self) -> dict[str, float]:
        return dict(self._gauges)

    def get_histogram_stats(self, name: str) -> dict[str, float]:
        values = self._histograms.get(name, [])
        if not values:
            return {"count": 0, "min": 0, "max": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0}

        sorted_values = sorted(values)
        n = len(sorted_values)
        return {
            "count": n,
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "avg": sum(sorted_values) / n,
            "p50": sorted_values[int(n * 0.5)],
            "p95": sorted_values[int(n * 0.95)],
            "p99": sorted_values[int(n * 0.99)],
        }

    def get_summary(self) -> dict[str, Any]:
        """Get comprehensive metrics summary."""
        counters = self.get_counters()
        uptime = time.monotonic() - self._start_time

        summary: dict[str, Any] = {
            "uptime_seconds": uptime,
            "counters": counters,
            "gauges": self.get_gauges(),
            "rates": {},
        }

        # Calculate rates
        if uptime > 0:
            summary["rates"] = {
                "connections_per_minute": counters[self.EXCHANGE_CONNECTIONS_TOTAL] / (uptime / 60.0),
                "failures_per_minute": counters[self.CONNECTION_FAILURES_TOTAL] / (uptime / 60.0),
                "retries_per_minute": counters[self.CONNECTION_RETRIES_TOTAL] / (uptime / 60.0),
                "messages_per_second": (
                    counters[self.MESSAGES_SENT_TOTAL] + counters[self.MESSAGES_RECEIVED_TOTAL]
                ) / uptime if uptime > 0 else 0,
            }

        # Per-protocol latency
        protocol_latencies = {}
        for key, values in self._histograms.items():
            if key.startswith("protocol_latency_"):
                protocol = key.replace("protocol_latency_", "")
                protocol_latencies[protocol] = self.get_histogram_stats(key)

        summary["protocol_latencies"] = protocol_latencies

        return summary

    def reset(self) -> None:
        """Reset all metrics."""
        for key in self._counters:
            self._counters[key] = 0
        self._gauges.clear()
        self._histograms.clear()
        self._start_time = time.monotonic()
