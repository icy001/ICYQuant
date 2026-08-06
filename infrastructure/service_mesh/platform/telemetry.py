"""Platform Telemetry for the Service Mesh Platform.

Provides ``PlatformTelemetry`` for structured logging, tracing,
and metrics emission for all mesh platform operations including
bootstrap, runtime, control API, plugin lifecycle, and upgrade.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PlatformTelemetry:
    """Unified telemetry for the service mesh platform."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: List[Dict[str, Any]] = []
        self._max_records = 10000
        self._trace_id: Optional[str] = None

    def set_trace_id(self, trace_id: str) -> None:
        with self._lock:
            self._trace_id = trace_id

    def get_trace_id(self) -> Optional[str]:
        with self._lock:
            return self._trace_id

    def log_bootstrap(
        self,
        phase: str,
        status: str,
        duration_s: float = 0.0,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._record(
            "bootstrap",
            phase,
            status,
            {"duration_s": duration_s, **(details or {})},
        )

    def log_runtime(
        self,
        operation: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._record(
            "runtime",
            operation,
            status,
            details,
        )

    def log_control_api(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        duration_s: float,
    ) -> None:
        self._record(
            "control_api",
            endpoint,
            f"{method} -> {status_code}",
            {"duration_s": duration_s},
        )

    def log_plugin(
        self,
        plugin_name: str,
        event: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._record(
            "plugin",
            plugin_name,
            event,
            details,
        )

    def log_upgrade(
        self,
        version: str,
        event: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._record(
            "upgrade",
            version,
            event,
            details,
        )

    def log_snapshot(
        self,
        operation: str,
        status: str,
        size_bytes: int = 0,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._record(
            "snapshot",
            operation,
            status,
            {"size_bytes": size_bytes, **(details or {})},
        )

    def log_injection(
        self,
        service: str,
        mode: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._record(
            "injection",
            service,
            f"[{mode}] {status}",
            details,
        )

    def log_platform_event(
        self,
        event_type: str,
        component: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._record("platform_event", component, event_type, details)

    def log_error(
        self,
        component: str,
        error_type: str,
        error_message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._record(
            "error",
            component,
            f"{error_type}: {error_message}",
            details,
        )
        logger.error(
            "Platform error [%s] %s: %s",
            component,
            error_type,
            error_message,
        )

    def _record(
        self,
        category: str,
        component: str,
        event: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._lock:
            record = {
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": self._trace_id,
                "category": category,
                "component": component,
                "event": event,
                "details": details or {},
            }
            self._records.append(record)
            if len(self._records) > self._max_records:
                self._records = self._records[-self._max_records:]

    def get_records(
        self,
        category: Optional[str] = None,
        component: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            records = list(self._records)
        if category:
            records = [r for r in records if r["category"] == category]
        if component:
            records = [r for r in records if r["component"] == component]
        return records[-limit:]

    def get_error_records(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.get_records(category="error", limit=limit)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            categories: Dict[str, int] = {}
            for r in self._records:
                cat = r["category"]
                categories[cat] = categories.get(cat, 0) + 1
            return {
                "total_records": len(self._records),
                "categories": categories,
                "trace_id": self._trace_id,
            }

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
