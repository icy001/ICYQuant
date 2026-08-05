"""Platform diagnostics for ICYQuant service discovery.

Provides ``PlatformDiagnostics`` for structured diagnostic
information including operation tracking, error history, and
performance reports across the platform.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from .runtime_context import DiscoveryContext

logger = logging.getLogger(__name__)


class PlatformDiagnostics:
    """Platform diagnostic information aggregator.

    Tracks operations, errors, and performance metrics
    across all platform components.
    """

    def __init__(
        self,
        context: Optional[DiscoveryContext] = None,
        max_history: int = 2000,
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or DiscoveryContext()
        self._max_history = max_history
        self._operations: List[Dict[str, Any]] = []
        self._errors: List[Dict[str, Any]] = []
        self._categories: Dict[str, int] = defaultdict(int)
        self._service_index: Dict[str, List[int]] = defaultdict(list)
        self._error_count = 0
        self._operation_count = 0

    def record_operation(
        self,
        operation: str,
        service_name: str,
        component: str = "",
        duration: float = 0.0,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a platform operation.

        Args:
            operation: The operation name.
            service_name: Service name.
            component: Component name.
            duration: Duration in seconds.
            details: Optional details.
        """
        entry: Dict[str, Any] = {
            "category": "operation",
            "operation": operation,
            "service_name": service_name,
            "component": component,
            "duration": duration,
            "details": dict(details) if details else {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        with self._lock:
            self._operations.append(entry)
            self._operation_count += 1
            self._categories["operation"] += 1
            self._service_index[service_name].append(
                len(self._operations) - 1
            )
            self._trim()

    def record_error(
        self,
        service_name: str,
        error: str,
        operation: str = "",
        component: str = "",
        traceback: str = "",
    ) -> None:
        """Record a platform error.

        Args:
            service_name: Service name.
            error: Error message.
            operation: Operation during which error occurred.
            component: Component name.
            traceback: Optional stack trace.
        """
        entry: Dict[str, Any] = {
            "category": "error",
            "error": error,
            "service_name": service_name,
            "operation": operation,
            "component": component,
            "traceback": traceback,
            "timestamp": datetime.utcnow().isoformat(),
        }
        with self._lock:
            self._errors.append(entry)
            self._error_count += 1
            self._categories["error"] += 1
            self._service_index[service_name].append(
                len(self._operations) + len(self._errors) - 1
            )
            self._trim()

        logger.warning(
            "Platform error for '%s' (%s/%s): %s",
            service_name,
            operation or "unknown",
            component or "unknown",
            error,
        )

    def get_operations(
        self, service_name: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        with self._lock:
            ops = list(self._operations)
        if service_name:
            ops = [
                o for o in ops if o.get("service_name") == service_name
            ]
        return ops[-limit:]

    def get_errors(
        self, service_name: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        with self._lock:
            errs = list(self._errors)
        if service_name:
            errs = [
                e for e in errs if e.get("service_name") == service_name
            ]
        return errs[-limit:]

    def get_performance_report(self) -> Dict[str, Any]:
        with self._lock:
            ops = list(self._operations)

        by_service: Dict[str, List[float]] = defaultdict(list)
        for op in ops:
            svc = op.get("service_name", "")
            dur = op.get("duration", 0.0)
            if dur > 0:
                by_service[svc].append(dur)

        services_report: Dict[str, Any] = {}
        for svc, durations in by_service.items():
            if not durations:
                continue
            services_report[svc] = {
                "operation_count": len(durations),
                "avg_duration_s": sum(durations) / len(durations),
                "min_duration_s": min(durations),
                "max_duration_s": max(durations),
            }

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_operations": len(ops),
            "tracked_services": len(by_service),
            "services": services_report,
        }

    def _trim(self) -> None:
        total = len(self._operations) + len(self._errors)
        if total > self._max_history:
            excess = total - self._max_history
            if len(self._operations) >= excess:
                self._operations = self._operations[excess:]
            else:
                remaining = excess - len(self._operations)
                self._operations = []
                self._errors = self._errors[remaining:]
            self._rebuild_index()

    def _rebuild_index(self) -> None:
        self._service_index.clear()
        for i, op in enumerate(self._operations):
            svc = op.get("service_name", "")
            self._service_index[svc].append(i)
        offset = len(self._operations)
        for i, err in enumerate(self._errors):
            svc = err.get("service_name", "")
            self._service_index[svc].append(offset + i)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "operation_count": self._operation_count,
                "error_count": self._error_count,
                "operations_stored": len(self._operations),
                "errors_stored": len(self._errors),
                "tracked_services": len(self._service_index),
                "categories": dict(self._categories),
                "max_history": self._max_history,
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"PlatformDiagnostics(ops={self._operation_count}, "
                f"errors={self._error_count})"
            )
