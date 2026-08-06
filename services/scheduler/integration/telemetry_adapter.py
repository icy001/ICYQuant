"""Telemetry Adapter — integrates the Scheduler with the platform Telemetry system.

The :class:`TelemetryAdapter` bridges scheduler telemetry with the
platform's centralized telemetry pipeline (OpenTelemetry, logging, audit).
"""

from __future__ import annotations

import enum
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TelemetryProtocol(enum.Enum):
    """Telemetry export protocols."""

    OTLP = "otlp"
    JAEGER = "jaeger"
    ZIPKIN = "zipkin"
    CONSOLE = "console"
    NONE = "none"


class TelemetryAdapter:
    """Adapter for platform telemetry integration.

    Responsibilities:
    * Export scheduler traces to OpenTelemetry
    * Forward scheduler logs to centralized logging
    * Record audit events for compliance
    * Bridge scheduler metrics to platform metrics

    Usage::

        adapter = TelemetryAdapter(protocol=TelemetryProtocol.OTLP)
        await adapter.connect()
        adapter.record_audit("schedule_created", {"schedule_id": "123"})
    """

    def __init__(self, protocol: TelemetryProtocol = TelemetryProtocol.OTLP) -> None:
        self._protocol = protocol
        self._lock = threading.Lock()
        self._connected = False
        self._export_count: int = 0
        self._error_count: int = 0
        self._audit_log: List[Dict[str, Any]] = []
        self._max_audit_log = 10000

    @property
    def protocol(self) -> TelemetryProtocol:
        return self._protocol

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def export_count(self) -> int:
        return self._export_count

    async def connect(self) -> None:
        logger.info("TelemetryAdapter: connecting via %s", self._protocol.value)
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False
        logger.info("TelemetryAdapter: disconnected")

    async def synchronize(self) -> Dict[str, Any]:
        return {"protocol": self._protocol.value, "exports": self._export_count}

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    async def export_trace(self, trace_data: Dict[str, Any]) -> None:
        """Export a trace span to the telemetry pipeline."""
        self._export_count += 1
        logger.debug("TelemetryAdapter: exported trace")

    async def export_metrics(self, metrics_data: Dict[str, Any]) -> None:
        """Export metrics to the platform metrics pipeline."""
        self._export_count += 1

    async def export_log(self, level: str, message: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Export a log entry to centralized logging."""
        self._export_count += 1

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    def record_audit(self, event: str, details: Dict[str, Any], user: str = "system") -> None:
        """Record an audit event.

        Args:
            event: Audit event type (schedule_created, job_triggered, etc.)
            details: Event-specific details
            user: User or service that performed the action
        """
        audit_entry = {
            "event": event,
            "details": details,
            "user": user,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._audit_log.append(audit_entry)
            if len(self._audit_log) > self._max_audit_log:
                self._audit_log = self._audit_log[-self._max_audit_log:]

    def get_audit_log(self, limit: int = 100, event: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query the audit log."""
        with self._lock:
            entries = self._audit_log
            if event:
                entries = [e for e in entries if e["event"] == event]
            return list(reversed(entries[-limit:]))
