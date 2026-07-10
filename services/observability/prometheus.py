"""
Prometheus metrics exporter.

Provides standard metrics
for production monitoring.
"""

from __future__ import annotations

try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        generate_latest,
    )

    ORDER_COUNTER = Counter(
        "icyquant_orders_total",
        "Total submitted orders"
    )

    ORDER_FAILED_COUNTER = Counter(
        "icyquant_order_failed_total",
        "Total failed orders"
    )

    LEDGER_EVENT_COUNTER = Counter(
        "icyquant_ledger_events_total",
        "Total ledger events"
    )

    ACTIVE_REQUESTS = Gauge(
        "icyquant_active_requests",
        "Active HTTP requests"
    )

    REQUEST_LATENCY = Histogram(
        "icyquant_request_latency_seconds",
        "HTTP request latency"
    )

    def record_order():
        ORDER_COUNTER.inc()

    def record_order_failure():
        ORDER_FAILED_COUNTER.inc()

    def record_ledger_event():
        LEDGER_EVENT_COUNTER.inc()

    def set_active_requests(
        value: int,
    ):
        ACTIVE_REQUESTS.set(
            value
        )

    def observe_latency(
        seconds: float,
    ):
        REQUEST_LATENCY.observe(
            seconds
        )

    def export_metrics() -> bytes:
        return generate_latest()

except ImportError:
    def record_order():
        pass

    def record_order_failure():
        pass

    def record_ledger_event():
        pass

    def set_active_requests(
        value: int,
    ):
        pass

    def observe_latency(
        seconds: float,
    ):
        pass

    def export_metrics() -> bytes:
        return b""