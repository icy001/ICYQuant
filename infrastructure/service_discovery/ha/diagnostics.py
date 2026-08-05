"""HA diagnostics for ICYQuant service discovery HA.

Provides ``HADiagnostics`` for recording operations and errors,
generating performance reports, and tracking diagnostic history
across all HA components.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HADiagnostics:
    """Collects and exposes HA diagnostic information.

    Records operations and errors with timestamps and
    durations, supports querying by service name, and
    generates aggregated performance reports.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._operations: List[Dict[str, Any]] = []
        self._errors: List[Dict[str, Any]] = []
        self._operation_count = 0
        self._error_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._max_operations = 1000
        self._max_errors = 500

    # ── Helpers ──

    @staticmethod
    def _now_iso() -> str:
        return datetime.utcnow().isoformat()

    def _trim_operations(self) -> None:
        if len(self._operations) > self._max_operations:
            excess = len(self._operations) - self._max_operations
            del self._operations[:excess]

    def _trim_errors(self) -> None:
        if len(self._errors) > self._max_errors:
            excess = len(self._errors) - self._max_errors
            del self._errors[:excess]

    # ── Public API ──

    def record_operation(
        self,
        operation: str,
        service_name: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record an HA operation.

        Args:
            operation: The operation name (e.g., 'failover',
                'heartbeat_check', 'snapshot_create').
            service_name: The affected service.
            status: Outcome status ('success', 'failed',
                'skipped', etc.).
            details: Optional operation details.
        """
        with self._lock:
            self._operation_count += 1
            if status == "success":
                self._success_count += 1
            else:
                self._failure_count += 1

            self._operations.append(
                {
                    "operation": operation,
                    "service_name": service_name,
                    "status": status,
                    "details": dict(details) if details else {},
                    "timestamp": self._now_iso(),
                    "epoch": time.time(),
                }
            )
            self._trim_operations()

        logger.debug(
            "Diagnostics operation: '%s' service='%s' status='%s'.",
            operation,
            service_name,
            status,
        )

    def record_error(
        self,
        service_name: str,
        error: str,
        operation: str = "",
    ) -> None:
        """Record an HA error.

        Args:
            service_name: The affected service.
            error: Error description or message.
            operation: The operation during which the error
                occurred.
        """
        with self._lock:
            self._error_count += 1
            self._errors.append(
                {
                    "service_name": service_name,
                    "error": error,
                    "operation": operation,
                    "timestamp": self._now_iso(),
                    "epoch": time.time(),
                }
            )
            self._trim_errors()

        logger.warning(
            "Diagnostics error: '%s' op='%s': %s",
            service_name,
            operation,
            error,
        )

    def get_operations(
        self, service_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve recorded operations.

        Args:
            service_name: Optional filter by service name.

        Returns:
            A list of operation entries (most recent first).
        """
        with self._lock:
            ops = list(self._operations)
        if service_name is not None:
            ops = [
                o
                for o in ops
                if o.get("service_name") == service_name
            ]
        ops.sort(key=lambda o: o.get("epoch", 0), reverse=True)
        return ops

    def get_errors(
        self, service_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve recorded errors.

        Args:
            service_name: Optional filter by service name.

        Returns:
            A list of error entries (most recent first).
        """
        with self._lock:
            errs = list(self._errors)
        if service_name is not None:
            errs = [
                e
                for e in errs
                if e.get("service_name") == service_name
            ]
        errs.sort(key=lambda e: e.get("epoch", 0), reverse=True)
        return errs

    def get_performance_report(self) -> Dict[str, Any]:
        """Generate an aggregated performance report.

        Returns:
            A dictionary with operation summaries, error
            rates, and per-service breakdowns.
        """
        with self._lock:
            total_ops = self._operation_count
            success_rate = (
                self._success_count / total_ops
                if total_ops > 0
                else 0.0
            )

            service_ops: Dict[str, int] = {}
            service_errors: Dict[str, int] = {}
            op_counts: Dict[str, int] = {}
            for op in self._operations:
                svc = op.get("service_name", "unknown")
                service_ops[svc] = service_ops.get(svc, 0) + 1
                op_name = op.get("operation", "unknown")
                op_counts[op_name] = op_counts.get(op_name, 0) + 1

            for err in self._errors:
                svc = err.get("service_name", "unknown")
                service_errors[svc] = (
                    service_errors.get(svc, 0) + 1
                )

            return {
                "total_operations": total_ops,
                "success_count": self._success_count,
                "failure_count": self._failure_count,
                "success_rate": success_rate,
                "total_errors": self._error_count,
                "operations_by_service": service_ops,
                "errors_by_service": service_errors,
                "operation_type_counts": op_counts,
                "timestamp": self._now_iso(),
            }

    def clear(
        self, service_name: Optional[str] = None
    ) -> None:
        """Clear diagnostic entries.

        Args:
            service_name: If provided, only clear entries for
                this service.  Otherwise clears all.
        """
        with self._lock:
            if service_name is None:
                self._operations.clear()
                self._errors.clear()
                self._operation_count = 0
                self._error_count = 0
                self._success_count = 0
                self._failure_count = 0
                logger.info("Diagnostics cleared (all).")
            else:
                before_ops = len(self._operations)
                before_errs = len(self._errors)
                self._operations = [
                    o
                    for o in self._operations
                    if o.get("service_name") != service_name
                ]
                self._errors = [
                    e
                    for e in self._errors
                    if e.get("service_name") != service_name
                ]
                removed_ops = before_ops - len(self._operations)
                removed_errs = before_errs - len(self._errors)
                logger.info(
                    "Diagnostics cleared for '%s': %d ops, %d errs.",
                    service_name,
                    removed_ops,
                    removed_errs,
                )

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the diagnostics."""
        with self._lock:
            return {
                "operation_count": self._operation_count,
                "success_count": self._success_count,
                "failure_count": self._failure_count,
                "error_count": self._error_count,
                "operations_in_memory": len(self._operations),
                "errors_in_memory": len(self._errors),
                "max_operations": self._max_operations,
                "max_errors": self._max_errors,
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"HADiagnostics(ops={self._operation_count}, "
                f"errors={self._error_count})"
            )