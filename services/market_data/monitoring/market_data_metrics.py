"""Market data Prometheus metrics (Commit 013, §23).

ICYQuant already runs Prometheus, so Monitoring does **not** build a
second metrics system — it reuses the default registry by importing
this module (§3).  The metric names follow §23::

    icyquant_market_data_quotes_received_total
    icyquant_market_data_bars_received_total
    icyquant_market_data_quote_age_seconds        (gauge, per symbol)
    icyquant_market_data_latency_seconds          (histogram)
    icyquant_market_data_latency_p95_seconds      (gauge)
    icyquant_market_data_stale_total
    icyquant_market_data_invalid_total
    icyquant_market_data_duplicate_total
    icyquant_market_data_gap_total
    icyquant_market_data_quarantine_total
    icyquant_market_data_reconnect_total
    icyquant_market_data_errors_total
    icyquant_market_data_cache_hit_total
    icyquant_market_data_cache_miss_total

Label discipline (§23): only ``symbol`` is used, and only on the quote
age gauge.  ``timestamp`` / ``order_id`` / ``request_id`` are explicitly
rejected — they are unbounded and would blow up cardinality.

Counter values originate from cumulative service statistics, so they are
synced by *delta*: the first sync raises the counter from 0 to the
observed total, later syncs add only the increase.  This keeps a genuine
monotonic Prometheus counter even though the source is a snapshot.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised only when prometheus_client is absent
    from prometheus_client import Counter, Gauge, Histogram

    PROMETHEUS_AVAILABLE = True
except Exception:  # noqa: BLE001 — metrics are optional infrastructure
    Counter = Gauge = Histogram = None  # type: ignore[assignment]
    PROMETHEUS_AVAILABLE = False


class _NullMetric:
    """No-op stand-in so callers never guard against a missing client."""

    def inc(self, *_args, **_kwargs) -> None:
        return None

    def set(self, *_args, **_kwargs) -> None:
        return None

    def observe(self, *_args, **_kwargs) -> None:
        return None

    def labels(self, *_args, **_kwargs) -> "_NullMetric":
        return self


def _counter(name: str, doc: str):
    if not PROMETHEUS_AVAILABLE:
        return _NullMetric()
    try:
        return Counter(name, doc)
    except ValueError:  # already registered (module re-import)
        return _NullMetric()


def _gauge(name: str, doc: str, labels: Optional[tuple] = None):
    if not PROMETHEUS_AVAILABLE:
        return _NullMetric()
    try:
        return Gauge(name, doc, list(labels or []))
    except ValueError:
        return _NullMetric()


def _histogram(name: str, doc: str):
    if not PROMETHEUS_AVAILABLE:
        return _NullMetric()
    try:
        return Histogram(name, doc)
    except ValueError:
        return _NullMetric()


QUOTES_RECEIVED = _counter(
    "icyquant_market_data_quotes_received_total",
    "Total quotes received from the adapter.",
)
BARS_RECEIVED = _counter(
    "icyquant_market_data_bars_received_total",
    "Total 1m bars produced.",
)
STALE_TOTAL = _counter(
    "icyquant_market_data_stale_total",
    "Total stale-quote observations.",
)
INVALID_TOTAL = _counter(
    "icyquant_market_data_invalid_total",
    "Total invalid quote/bar observations.",
)
DUPLICATE_TOTAL = _counter(
    "icyquant_market_data_duplicate_total",
    "Total duplicate quote/bar observations.",
)
GAP_TOTAL = _counter(
    "icyquant_market_data_gap_total",
    "Total detected bar gaps.",
)
QUARANTINE_TOTAL = _counter(
    "icyquant_market_data_quarantine_total",
    "Total quarantined payloads (Commit 006).",
)
RECONNECT_TOTAL = _counter(
    "icyquant_market_data_reconnect_total",
    "Total adapter reconnects.",
)
ERRORS_TOTAL = _counter(
    "icyquant_market_data_errors_total",
    "Total adapter / pipeline errors.",
)
CACHE_HIT_TOTAL = _counter(
    "icyquant_market_data_cache_hit_total",
    "Total market cache hits.",
)
CACHE_MISS_TOTAL = _counter(
    "icyquant_market_data_cache_miss_total",
    "Total market cache misses.",
)

QUOTE_AGE = _gauge(
    "icyquant_market_data_quote_age_seconds",
    "Latest quote age in seconds, per symbol.",
    ("symbol",),
)
LATENCY_P95 = _gauge(
    "icyquant_market_data_latency_p95_seconds",
    "P95 market data latency in seconds.",
)
LATENCY_AVG = _gauge(
    "icyquant_market_data_latency_avg_seconds",
    "Average market data latency in seconds.",
)
LATENCY = _histogram(
    "icyquant_market_data_latency_seconds",
    "Market data latency (exchange → received) in seconds.",
)

#: Last value synced into each cumulative counter (name → total).
_LAST: dict[str, float] = {}

#: Cumulative-counter sources: snapshot key → Prometheus counter.
_COUNTER_SOURCES = {
    "quotes_received_total": QUOTES_RECEIVED,
    "bars_received_total": BARS_RECEIVED,
    "stale_events_total": STALE_TOTAL,
    "invalid_quote_total": INVALID_TOTAL,
    "duplicate_quote_total": DUPLICATE_TOTAL,
    "bar_gap_total": GAP_TOTAL,
    "quarantined_events_total": QUARANTINE_TOTAL,
    "reconnect_total": RECONNECT_TOTAL,
    "error_total": ERRORS_TOTAL,
    "cache_hit_total": CACHE_HIT_TOTAL,
    "cache_miss_total": CACHE_MISS_TOTAL,
}


def available() -> bool:
    """Whether the Prometheus client is importable."""
    return PROMETHEUS_AVAILABLE


def _sync_counter(key: str, raw: Any) -> None:
    """Delta-sync one cumulative counter from a snapshot total."""
    if raw is None:
        return
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return
    prev = _LAST.get(key, 0.0)
    delta = value - prev
    counter = _COUNTER_SOURCES.get(key)
    if counter is not None and delta > 0:
        try:
            counter.inc(delta)
        except Exception:  # noqa: BLE001 — metrics must never break reads
            logger.debug("metric %s update failed", key, exc_info=True)
    _LAST[key] = value


def observe_latency(seconds: Optional[float]) -> None:
    """Record one latency observation (called once per fresh quote)."""
    if seconds is None:
        return
    try:
        LATENCY.observe(max(0.0, float(seconds)))
    except Exception:  # noqa: BLE001
        logger.debug("latency observation failed", exc_info=True)


def update_from_snapshot(snapshot: dict) -> None:
    """Push a monitoring snapshot into the Prometheus registry (§23).

    Never raises: a metrics failure must not take down the read path.
    """
    if not isinstance(snapshot, dict):
        return
    for key in _COUNTER_SOURCES:
        _sync_counter(key, snapshot.get(key))

    metrics = snapshot.get("metrics") or {}
    latency = (metrics.get("latency") if isinstance(metrics, dict) else {}) or {}
    _safe_set(LATENCY_AVG, _seconds(latency.get("avg_ms")))
    _safe_set(LATENCY_P95, _seconds(latency.get("p95_ms")))

    for row in snapshot.get("symbols", {}).get("items", []) or []:
        sym = row.get("symbol")
        age = _seconds(row.get("quote_age_ms"))
        if sym is None or age is None:
            continue
        try:
            QUOTE_AGE.labels(symbol=str(sym)).set(age)
        except Exception:  # noqa: BLE001
            logger.debug("quote age gauge failed for %s", sym, exc_info=True)


def _seconds(ms: Any) -> Optional[float]:
    if ms is None:
        return None
    try:
        return max(0.0, float(ms) / 1000.0)
    except (TypeError, ValueError):
        return None


def _safe_set(gauge, value: Optional[float]) -> None:
    if value is None:
        return
    try:
        gauge.set(value)
    except Exception:  # noqa: BLE001
        logger.debug("gauge update failed", exc_info=True)


def export_metrics() -> tuple[bytes, str]:
    """Render the registry (delegates to the shared observability module)."""
    from ...observability.prometheus import export_metrics as _export

    return _export()


def reset_for_tests() -> None:
    """Forget the delta bookkeeping (counters themselves stay monotonic)."""
    _LAST.clear()


__all__ = [
    "PROMETHEUS_AVAILABLE",
    "available",
    "observe_latency",
    "update_from_snapshot",
    "export_metrics",
    "reset_for_tests",
    "QUOTES_RECEIVED",
    "BARS_RECEIVED",
    "STALE_TOTAL",
    "INVALID_TOTAL",
    "DUPLICATE_TOTAL",
    "GAP_TOTAL",
    "QUARANTINE_TOTAL",
    "RECONNECT_TOTAL",
    "ERRORS_TOTAL",
    "CACHE_HIT_TOTAL",
    "CACHE_MISS_TOTAL",
    "QUOTE_AGE",
    "LATENCY",
    "LATENCY_P95",
    "LATENCY_AVG",
]
