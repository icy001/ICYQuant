"""
Feature flag platform telemetry.

Provides unified telemetry integration for
the feature flag platform, connecting events
to logging, tracing, and monitoring systems.

Automatically generates:
    - Audit logs for all events
    - Trace spans for distributed tracing
    - Metrics for monitoring dashboards
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .events import EventBus, FeatureEvent, FeatureEventType
from .monitoring import FeatureFlagRuntimeMetrics

logger = logging.getLogger(__name__)


class FeatureFlagTelemetry:
    """
    Unified telemetry for feature flag events.

    Automatically processes all feature flag
    events and generates:
        1. Audit log entries
        2. Trace spans (for distributed tracing)
        3. Metrics updates (for monitoring)

    Usage:
        telemetry = FeatureFlagTelemetry(bus, metrics)
        await telemetry.start()
        # All events are automatically processed
    """

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        metrics: Optional[FeatureFlagRuntimeMetrics] = None,
    ) -> None:
        """
        Initialize telemetry handler.

        Args:
            event_bus: EventBus to subscribe to.
            metrics: Metrics collector.
        """
        self._bus = event_bus or EventBus()
        self._metrics = metrics or FeatureFlagRuntimeMetrics()
        self._audit_log: List[Dict[str, Any]] = []
        self._trace_spans: List[Dict[str, Any]] = []
        self._max_audit_entries = 10000
        self._max_trace_spans = 5000
        self._handler_count = 0
        self._error_count = 0

    @property
    def metrics(self) -> FeatureFlagRuntimeMetrics:
        """Get the metrics collector."""
        return self._metrics

    async def start(self) -> None:
        """
        Start telemetry processing.

        Subscribes to all feature flag events
        and processes them for audit, tracing,
        and metrics.
        """
        # Subscribe to all events
        event_types = list(FeatureEventType)
        for event_type in event_types:
            await self._bus.subscribe(event_type, self._process_event)

        logger.info(
            "Telemetry started: subscribed to %d event types",
            len(event_types),
        )

    async def _process_event(self, event: FeatureEvent) -> None:
        """
        Process a feature flag event for telemetry.

        Args:
            event: The event to process.
        """
        self._handler_count += 1

        try:
            # Generate audit log
            self._generate_audit(event)

            # Generate trace span
            self._generate_trace(event)

            # Update metrics
            self._update_metrics(event)

        except Exception as e:
            self._error_count += 1
            logger.error(
                "Telemetry processing error for %s: %s",
                event.event_type.value,
                e,
            )

    def _generate_audit(self, event: FeatureEvent) -> None:
        """Generate an audit log entry."""
        entry = {
            "event_type": event.event_type.value,
            "timestamp": datetime.utcnow().isoformat(),
            "flag_key": event.flag_key,
            "data": event.data,
            "trace_id": event.trace_id,
            "operator": event.operator,
        }

        self._audit_log.append(entry)

        # Trim if needed
        if len(self._audit_log) > self._max_audit_entries:
            excess = len(self._audit_log) - self._max_audit_entries
            self._audit_log = self._audit_log[excess:]

    def _generate_trace(self, event: FeatureEvent) -> None:
        """Generate a trace span."""
        span = {
            "span_id": f"span_{id(event)}_{time.time_ns()}",
            "trace_id": event.trace_id or f"trace_{time.time_ns()}",
            "event_type": event.event_type.value,
            "flag_key": event.flag_key,
            "start_time": datetime.utcnow().isoformat(),
            "attributes": event.data,
        }

        self._trace_spans.append(span)

        # Trim if needed
        if len(self._trace_spans) > self._max_trace_spans:
            excess = len(self._trace_spans) - self._max_trace_spans
            self._trace_spans = self._trace_spans[excess:]

    def _update_metrics(self, event: FeatureEvent) -> None:
        """Update metrics based on event type."""
        event_type = event.event_type

        if event_type == FeatureEventType.HOT_RELOAD:
            self._metrics.record_reload()

        elif event_type in (
            FeatureEventType.SNAPSHOT_CREATED,
            FeatureEventType.SNAPSHOT_ACTIVATED,
        ):
            version = event.data.get("version", 0)
            if version:
                self._metrics.record_snapshot_version(version)

        elif event_type in (
            FeatureEventType.CANARY_STARTED,
            FeatureEventType.CANARY_PROMOTED,
            FeatureEventType.CANARY_COMPLETED,
        ):
            self._metrics.set_canary_active(
                self._metrics._canary_active + 1,
            )

        elif event_type == FeatureEventType.CANARY_ROLLED_BACK:
            self._metrics.set_canary_active(
                max(0, self._metrics._canary_active - 1),
            )

        elif event_type in (
            FeatureEventType.EXPERIMENT_STARTED,
            FeatureEventType.EXPERIMENT_RESUMED,
        ):
            self._metrics.set_experiment_running(
                self._metrics._experiment_running + 1,
            )

        elif event_type in (
            FeatureEventType.EXPERIMENT_PAUSED,
            FeatureEventType.EXPERIMENT_COMPLETED,
            FeatureEventType.EXPERIMENT_ARCHIVED,
        ):
            self._metrics.set_experiment_running(
                max(0, self._metrics._experiment_running - 1),
            )

    def query_audit(
        self,
        event_type: Optional[str] = None,
        flag_key: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Query audit log entries.

        Args:
            event_type: Filter by event type.
            flag_key: Filter by flag key.
            limit: Max entries to return.

        Returns:
            Matching audit entries.
        """
        results = list(reversed(self._audit_log))

        if event_type:
            results = [e for e in results if e["event_type"] == event_type]
        if flag_key:
            results = [e for e in results if e["flag_key"] == flag_key]

        return results[:limit]

    def query_traces(
        self,
        trace_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Query trace spans.

        Args:
            trace_id: Filter by trace ID.
            event_type: Filter by event type.
            limit: Max spans to return.

        Returns:
            Matching trace spans.
        """
        results = list(reversed(self._trace_spans))

        if trace_id:
            results = [s for s in results if s["trace_id"] == trace_id]
        if event_type:
            results = [s for s in results if s["event_type"] == event_type]

        return results[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get telemetry statistics."""
        return {
            "handler_count": self._handler_count,
            "error_count": self._error_count,
            "audit_log_size": len(self._audit_log),
            "trace_spans_size": len(self._trace_spans),
            "metrics_snapshot": self._metrics.snapshot(),
        }

    async def flush(self) -> None:
        """Flush all pending telemetry data."""
        # In production, this would send data to external systems
        pass

    async def shutdown(self) -> None:
        """Shutdown telemetry processing."""
        await self.flush()
        self._audit_log.clear()
        self._trace_spans.clear()
