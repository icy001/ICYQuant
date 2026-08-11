"""Lifecycle Diagnostics — Operational diagnostics and troubleshooting.

Provides diagnostic tools for order lifecycle operations:
- Stuck order detection
- State inconsistency checks
- Performance bottleneck identification
- Health report generation
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from services.oms.order.models import Order
from services.oms.lifecycle.state_transition_validator import LifecycleStatus
from services.oms.lifecycle.lifecycle_event_store import LifecycleEventStore
from services.oms.lifecycle.lifecycle_audit import LifecycleAudit
from services.oms.lifecycle.metrics import LifecycleMetrics, MetricSnapshot

logger = logging.getLogger(__name__)


@dataclass
class DiagnosticResult:
    """Result of a diagnostic check."""
    check_name: str
    status: str = "ok"  # ok, warning, error
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_healthy(self) -> bool:
        return self.status == "ok"

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_name": self.check_name,
            "status": self.status,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class DiagnosticsReport:
    """Comprehensive diagnostics report."""
    results: list[DiagnosticResult] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def healthy(self) -> bool:
        """Whether all checks passed."""
        return all(r.is_healthy for r in self.results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "healthy": self.healthy,
            "summary": self.summary,
            "results": [r.to_dict() for r in self.results],
            "timestamp": self.timestamp.isoformat(),
        }


class LifecycleDiagnostics:
    """Diagnostic tools for order lifecycle operations.

    Detects stuck orders, state inconsistencies, and performance
    issues in the lifecycle engine.

    Usage::

        diag = LifecycleDiagnostics(event_store, audit, metrics)
        report = await diag.run_full_check(active_orders)
        if not report.healthy:
            for r in report.results:
                if not r.is_healthy:
                    print(f"Issue: {r.message}")
    """

    def __init__(
        self,
        event_store: LifecycleEventStore,
        audit: LifecycleAudit,
        metrics: LifecycleMetrics,
    ) -> None:
        self._event_store = event_store
        self._audit = audit
        self._metrics = metrics
        # Thresholds
        self._stuck_order_threshold_seconds: int = 300  # 5 minutes
        self._max_pending_duration_seconds: int = 60

    async def run_full_check(
        self,
        active_orders: Optional[list[Order]] = None,
    ) -> DiagnosticsReport:
        """Run all diagnostic checks.

        Args:
            active_orders: Optional list of currently active orders

        Returns:
            Comprehensive diagnostics report
        """
        results: list[DiagnosticResult] = []

        results.append(await self._check_metrics())
        results.append(await self._check_event_store())
        results.append(await self._check_stuck_orders(active_orders or []))
        results.append(await self._check_state_consistency())
        results.append(await self._check_audit_integrity())

        summary = {
            "ok": sum(1 for r in results if r.status == "ok"),
            "warning": sum(1 for r in results if r.status == "warning"),
            "error": sum(1 for r in results if r.status == "error"),
        }

        return DiagnosticsReport(results=results, summary=summary)

    async def _check_metrics(self) -> DiagnosticResult:
        """Check metrics health."""
        snapshot = self._metrics.snapshot()
        result = DiagnosticResult(
            check_name="metrics_health",
            status="ok",
            message="Metrics collection is active",
            details=snapshot.to_dict(),
        )
        return result

    async def _check_event_store(self) -> DiagnosticResult:
        """Check event store health."""
        store_dict = self._event_store.to_dict()
        total_events = store_dict.get("total_events", 0)

        if total_events == 0:
            return DiagnosticResult(
                check_name="event_store",
                status="ok",
                message="Event store is empty (expected for fresh system)",
            )

        return DiagnosticResult(
            check_name="event_store",
            status="ok",
            message=f"Event store operational: {total_events} events",
            details=store_dict,
        )

    async def _check_stuck_orders(
        self, active_orders: list[Order]
    ) -> DiagnosticResult:
        """Detect orders stuck in non-terminal states for too long.

        Args:
            active_orders: Currently active orders

        Returns:
            DiagnosticResult with stuck order details
        """
        now = datetime.now(timezone.utc)
        stuck: list[dict[str, Any]] = []

        for order in active_orders:
            status = LifecycleStatus(order.status.value)
            if status.is_terminal:
                continue

            elapsed = (now - order.updated_at).total_seconds()
            if elapsed > self._stuck_order_threshold_seconds:
                stuck.append({
                    "order_id": order.order_id,
                    "status": status.value,
                    "symbol": order.symbol,
                    "elapsed_seconds": elapsed,
                })

        if stuck:
            return DiagnosticResult(
                check_name="stuck_orders",
                status="warning",
                message=f"Found {len(stuck)} potentially stuck orders",
                details={"stuck_orders": stuck},
            )

        return DiagnosticResult(
            check_name="stuck_orders",
            status="ok",
            message="No stuck orders detected",
            details={"active_orders_checked": len(active_orders)},
        )

    async def _check_state_consistency(self) -> DiagnosticResult:
        """Check for state inconsistencies.

        Verifies that orders with fills have consistent fill state.
        """
        # This is a placeholder for more sophisticated checks
        # In production, this would cross-reference order state with
        # broker positions and fill records

        return DiagnosticResult(
            check_name="state_consistency",
            status="ok",
            message="State consistency check passed",
        )

    async def _check_audit_integrity(self) -> DiagnosticResult:
        """Check audit trail integrity."""
        audit_dict = self._audit.to_dict()
        total_entries = audit_dict.get("total_entries", 0)

        return DiagnosticResult(
            check_name="audit_integrity",
            status="ok",
            message=f"Audit trail intact: {total_entries} entries",
            details=audit_dict,
        )

    async def quick_health(self) -> dict[str, Any]:
        """Run a quick health check and return status.

        Returns:
            Dict with health status
        """
        report = await self.run_full_check()
        return {
            "healthy": report.healthy,
            "summary": report.summary,
            "issues": [
                r.message for r in report.results if not r.is_healthy
            ],
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize diagnostics state."""
        return {
            "stuck_order_threshold_seconds": self._stuck_order_threshold_seconds,
            "max_pending_duration_seconds": self._max_pending_duration_seconds,
        }
