"""HA telemetry and tracing for ICYQuant service discovery HA.

Provides ``HATelemetry`` for recording distributed tracing
spans, tracking failover latency, recovery steps, and traffic
migration across regions.

Supports span-based tracing for HA operations.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HATelemetry:
    """Records and exposes HA telemetry data.

    Captures spans for HA operations (failover, recovery,
    traffic migration) and stores them for querying.  Spans
    follow an open-tracing inspired model with operation names,
    service names, timing, and status.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._spans: Dict[str, Dict[str, Any]] = {}
        self._failover_records: List[Dict[str, Any]] = []
        self._recovery_records: List[Dict[str, Any]] = []
        self._migration_records: List[Dict[str, Any]] = []
        self._span_count = 0
        self._failover_count = 0
        self._recovery_count = 0
        self._migration_count = 0
        self._max_records = 500

    # ── Helpers ──

    @staticmethod
    def _now_iso() -> str:
        return datetime.utcnow().isoformat()

    def _trim_list(self, lst: List[Dict[str, Any]]) -> None:
        if len(lst) > self._max_records:
            excess = len(lst) - self._max_records
            del lst[:excess]

    # ── Public API ──

    def record_failover(
        self,
        service_name: str,
        from_instance: str,
        to_instance: str,
        latency: float,
    ) -> None:
        """Record a failover telemetry event.

        Args:
            service_name: The affected service.
            from_instance: The source instance.
            to_instance: The target instance.
            latency: Failover latency in seconds.
        """
        with self._lock:
            self._failover_count += 1
            record: Dict[str, Any] = {
                "service_name": service_name,
                "from_instance": from_instance,
                "to_instance": to_instance,
                "latency": latency,
                "timestamp": self._now_iso(),
            }
            self._failover_records.append(record)
            self._trim_list(self._failover_records)
        logger.info(
            "Failover telemetry: '%s' %s -> %s (latency=%.3fs).",
            service_name,
            from_instance,
            to_instance,
            latency,
        )

    def record_recovery(
        self,
        service_name: str,
        steps: List[str],
        success: bool,
    ) -> None:
        """Record a recovery telemetry event.

        Args:
            service_name: The affected service.
            steps: Ordered list of recovery step names.
            success: Whether recovery succeeded.
        """
        with self._lock:
            self._recovery_count += 1
            record: Dict[str, Any] = {
                "service_name": service_name,
                "steps": list(steps),
                "step_count": len(steps),
                "success": success,
                "timestamp": self._now_iso(),
            }
            self._recovery_records.append(record)
            self._trim_list(self._recovery_records)
        logger.info(
            "Recovery telemetry: '%s' steps=%d success=%s.",
            service_name,
            len(steps),
            success,
        )

    def record_traffic_migration(
        self,
        service_name: str,
        from_region: str,
        to_region: str,
    ) -> None:
        """Record a traffic migration event.

        Args:
            service_name: The affected service.
            from_region: Source region.
            to_region: Destination region.
        """
        with self._lock:
            self._migration_count += 1
            record: Dict[str, Any] = {
                "service_name": service_name,
                "from_region": from_region,
                "to_region": to_region,
                "timestamp": self._now_iso(),
            }
            self._migration_records.append(record)
            self._trim_list(self._migration_records)
        logger.info(
            "Traffic migration telemetry: '%s' %s -> %s.",
            service_name,
            from_region,
            to_region,
        )

    def start_span(
        self, operation: str, service_name: Optional[str] = None
    ) -> str:
        """Start a new tracing span.

        Args:
            operation: The operation name (e.g., 'failover',
                'recovery', 'snapshot').
            service_name: Optional service name.

        Returns:
            A unique span ID for later completion.
        """
        span_id = uuid.uuid4().hex
        with self._lock:
            self._span_count += 1
            self._spans[span_id] = {
                "span_id": span_id,
                "operation": operation,
                "service_name": service_name,
                "started_at": self._now_iso(),
                "started_epoch": time.time(),
                "status": "started",
                "duration": None,
                "ended_at": None,
            }
        logger.debug(
            "Span started: %s (operation=%s, service=%s).",
            span_id,
            operation,
            service_name,
        )
        return span_id

    def end_span(
        self, span_id: str, status: str = "ok"
    ) -> None:
        """End a previously started tracing span.

        Args:
            span_id: The span ID returned by ``start_span``.
            status: Outcome status (e.g., 'ok', 'error',
                'cancelled').
        """
        with self._lock:
            span = self._spans.get(span_id)
            if span is None:
                logger.warning(
                    "Span '%s' not found; cannot end.", span_id
                )
                return
            started = span["started_epoch"]
            duration = time.time() - started
            span["status"] = status
            span["duration"] = duration
            span["ended_at"] = self._now_iso()
        logger.debug(
            "Span ended: %s (status=%s, duration=%.3fs).",
            span_id,
            status,
            duration,
        )

    def get_spans(
        self, service_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve spans, optionally filtered by service.

        Args:
            service_name: Optional filter by service name.

        Returns:
            A list of span dictionaries (most recent first).
        """
        with self._lock:
            spans = list(self._spans.values())
        if service_name is not None:
            spans = [
                s
                for s in spans
                if s.get("service_name") == service_name
            ]
        spans.sort(
            key=lambda s: s.get("started_epoch", 0), reverse=True
        )
        return spans

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the telemetry collector."""
        with self._lock:
            return {
                "span_count": self._span_count,
                "active_spans": sum(
                    1
                    for s in self._spans.values()
                    if s.get("status") == "started"
                ),
                "completed_spans": sum(
                    1
                    for s in self._spans.values()
                    if s.get("status") != "started"
                ),
                "failover_count": self._failover_count,
                "recovery_count": self._recovery_count,
                "migration_count": self._migration_count,
                "failover_records": len(self._failover_records),
                "recovery_records": len(self._recovery_records),
                "migration_records": len(self._migration_records),
                "max_records": self._max_records,
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"HATelemetry(spans={self._span_count}, "
                f"failovers={self._failover_count}, "
                f"recoveries={self._recovery_count})"
            )