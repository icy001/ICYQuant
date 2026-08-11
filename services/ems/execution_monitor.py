"""Execution Monitor — Real-time execution quality monitoring.

Monitors execution quality metrics in real-time including fill rates,
slippage, latency, and remaining quantities for active executions.

Monitoring Pipeline::

    Child Order → Monitor → Fill Rate / Latency / Slippage → Alert / Pause

Usage::

    monitor = ExecutionMonitor()
    await monitor.monitor_child(child_order)
    await monitor.track_slippage(parent_order_id, fill_price, benchmark)
    stats = await monitor.get_stats(parent_order_id)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from services.ems.child_order import ChildOrder

logger = logging.getLogger(__name__)


@dataclass
class ExecutionSnapshot:
    """A point-in-time execution snapshot for monitoring."""

    parent_order_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    filled_quantity: float = 0.0
    remaining_quantity: float = 0.0
    average_price: float = 0.0
    fill_pct: float = 0.0
    active_children: int = 0
    slippage_bps: float = 0.0


class ExecutionMonitor:
    """Real-time execution quality monitor.

    Tracks fill rates, slippage, latency, and other quality metrics
    during active execution.

    Attributes:
        _snapshots: Per-parent-order execution snapshots
        _fill_events: Per-parent-order fill event history
        _latency_samples: Per-parent-order latency samples
        _alert_thresholds: Configurable alert thresholds
    """

    def __init__(self) -> None:
        self._snapshots: dict[str, list[ExecutionSnapshot]] = {}
        self._fill_events: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._latency_samples: dict[str, list[float]] = defaultdict(list)

        # Alert thresholds
        self._alert_thresholds: dict[str, float] = {
            "min_fill_rate_pct_per_min": 1.0,
            "max_slippage_bps": 50.0,
            "max_latency_ms": 5000.0,
            "min_fill_pct": 10.0,
        }

    # ── Monitoring API ─────────────────────────────────────────────

    async def monitor_child(self, child: ChildOrder) -> None:
        """Monitor a child order through its lifecycle.

        Args:
            child: Child order to monitor
        """
        # Record submission latency if applicable
        if child.submitted_at and child.created_at:
            latency = (child.submitted_at - child.created_at).total_seconds() * 1000
            self._latency_samples[child.parent_order_id].append(latency)

    async def track_fill(
        self,
        parent_order_id: str,
        child_order_id: str,
        fill_qty: float,
        fill_price: float,
        filled_quantity: float,
        remaining_quantity: float,
        average_price: float,
    ) -> None:
        """Track a fill event for monitoring.

        Args:
            parent_order_id: Parent order identifier
            child_order_id: Child order identifier
            fill_qty: Fill quantity
            fill_price: Fill price
            filled_quantity: Cumulative filled quantity
            remaining_quantity: Remaining quantity
            average_price: Current average price
        """
        total_qty = filled_quantity + remaining_quantity
        fill_pct = filled_quantity / total_qty if total_qty > 0 else 0.0

        event = {
            "timestamp": datetime.now(timezone.utc),
            "child_order_id": child_order_id,
            "fill_qty": fill_qty,
            "fill_price": fill_price,
            "filled_quantity": filled_quantity,
            "remaining_quantity": remaining_quantity,
            "fill_pct": fill_pct,
            "average_price": average_price,
        }
        self._fill_events[parent_order_id].append(event)

        # Create snapshot
        snapshot = ExecutionSnapshot(
            parent_order_id=parent_order_id,
            filled_quantity=filled_quantity,
            remaining_quantity=remaining_quantity,
            average_price=average_price,
            fill_pct=fill_pct,
        )
        self._snapshots.setdefault(parent_order_id, []).append(snapshot)

    async def track_slippage(
        self,
        parent_order_id: str,
        fill_price: float,
        benchmark_price: float,
    ) -> float:
        """Track slippage vs benchmark.

        Args:
            parent_order_id: Parent order identifier
            fill_price: Actual fill price
            benchmark_price: Benchmark price

        Returns:
            Slippage in basis points
        """
        if benchmark_price <= 0:
            return 0.0

        slippage = (fill_price - benchmark_price) / benchmark_price * 10000
        logger.debug("Slippage tracked: %s slippage=%.1f bps", parent_order_id, slippage)
        return slippage

    # ── Statistics API ─────────────────────────────────────────────

    async def get_fill_rate(self, parent_order_id: str) -> float:
        """Get fill rate in quantity per minute.

        Args:
            parent_order_id: Parent order identifier

        Returns:
            Fill rate (qty/min)
        """
        events = self._fill_events.get(parent_order_id, [])
        if len(events) < 2:
            return 0.0

        first = events[0]
        last = events[-1]

        first_ts = first["timestamp"]
        last_ts = last["timestamp"]

        if isinstance(first_ts, str):
            first_ts = datetime.fromisoformat(first_ts)
        if isinstance(last_ts, str):
            last_ts = datetime.fromisoformat(last_ts)

        elapsed = (last_ts - first_ts).total_seconds()
        if elapsed <= 0:
            return 0.0

        total_filled = sum(e["fill_qty"] for e in events)
        return (total_filled / elapsed) * 60.0

    async def get_latency_stats(self, parent_order_id: str) -> dict[str, float]:
        """Get latency statistics for a parent order.

        Args:
            parent_order_id: Parent order identifier

        Returns:
            Dict with avg, min, max, p50, p95, p99 latency in ms
        """
        samples = self._latency_samples.get(parent_order_id, [])
        if not samples:
            return {"avg": 0.0, "min": 0.0, "max": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}

        sorted_samples = sorted(samples)
        n = len(sorted_samples)

        return {
            "avg": sum(samples) / n,
            "min": sorted_samples[0],
            "max": sorted_samples[-1],
            "p50": sorted_samples[int(n * 0.50)],
            "p95": sorted_samples[int(n * 0.95)],
            "p99": sorted_samples[int(n * 0.99)],
        }

    async def get_stats(self, parent_order_id: str) -> dict[str, Any]:
        """Get comprehensive execution statistics.

        Args:
            parent_order_id: Parent order identifier

        Returns:
            Statistics dictionary
        """
        events = self._fill_events.get(parent_order_id, [])
        snapshots = self._snapshots.get(parent_order_id, [])

        fill_count = len(events)
        total_filled = sum(e["fill_qty"] for e in events)
        latest = events[-1] if events else {}

        return {
            "parent_order_id": parent_order_id,
            "fill_count": fill_count,
            "total_filled": total_filled,
            "fill_pct": latest.get("fill_pct", 0.0),
            "average_price": latest.get("average_price", 0.0),
            "remaining_quantity": latest.get("remaining_quantity", 0.0),
            "fill_rate_per_min": await self.get_fill_rate(parent_order_id),
            "snapshot_count": len(snapshots),
            **await self.get_latency_stats(parent_order_id),
        }

    # ── Alerting ───────────────────────────────────────────────────

    async def check_alerts(self, parent_order_id: str) -> list[dict[str, Any]]:
        """Check for alert conditions on an execution.

        Args:
            parent_order_id: Parent order identifier

        Returns:
            List of alert dicts
        """
        alerts: list[dict[str, Any]] = []
        stats = await self.get_stats(parent_order_id)

        # Check fill rate
        fill_rate = stats.get("fill_rate_per_min", 0)
        if fill_rate < self._alert_thresholds["min_fill_rate_pct_per_min"] and fill_rate > 0:
            alerts.append({
                "type": "LOW_FILL_RATE",
                "message": f"Fill rate {fill_rate:.1f}/min below threshold",
                "value": fill_rate,
                "threshold": self._alert_thresholds["min_fill_rate_pct_per_min"],
            })

        # Check fill percentage
        fill_pct = stats.get("fill_pct", 0) * 100
        if 0 < fill_pct < self._alert_thresholds["min_fill_pct"]:
            alerts.append({
                "type": "LOW_FILL_PCT",
                "message": f"Fill percentage {fill_pct:.1f}% below threshold",
                "value": fill_pct,
                "threshold": self._alert_thresholds["min_fill_pct"],
            })

        return alerts

    def set_alert_threshold(self, name: str, value: float) -> None:
        """Set an alert threshold.

        Args:
            name: Threshold name
            value: Threshold value
        """
        self._alert_thresholds[name] = value

    # ── Cleanup ────────────────────────────────────────────────────

    async def clear(self, parent_order_id: str) -> None:
        """Clear monitoring data for a parent order.

        Args:
            parent_order_id: Parent order identifier
        """
        self._snapshots.pop(parent_order_id, None)
        self._fill_events.pop(parent_order_id, None)
        self._latency_samples.pop(parent_order_id, None)

    def to_dict(self) -> dict[str, Any]:
        """Serialize monitor state."""
        return {
            "monitored_parents": len(self._fill_events),
            "total_fill_events": sum(len(v) for v in self._fill_events.values()),
            "total_snapshots": sum(len(v) for v in self._snapshots.values()),
            "alert_thresholds": self._alert_thresholds,
        }
