"""Cluster Telemetry — unified tracing, logging, and metrics for the workflow cluster.

Unified pipeline::

    Workflow Cluster
         │
    Tracing
         │
    Logging
         │
    Metrics
         │
    Audit

Adds:
* Leader Timeline — track leader elections and tenure
* Cluster Events — node join/leave, shard changes
* Failover Timeline — detection → recovery → completion
* Recovery Timeline — checkpoint load → replay → resume
"""

from __future__ import annotations

import contextlib
import logging
import time
import uuid
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

from .metrics import ClusterMetrics

logger = logging.getLogger(__name__)

# Context variable for distributed tracing
cluster_trace_id: ContextVar[Optional[str]] = ContextVar("cluster_trace_id", default=None)


class ClusterSpan:
    """A tracing span for a cluster operation."""

    def __init__(
        self,
        name: str,
        *,
        trace_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.span_id = str(uuid.uuid4())[:8]
        self.name = name
        self.trace_id = trace_id or str(uuid.uuid4())[:16]
        self.parent_id = parent_id
        self.metadata = metadata or {}
        self.start_time = time.monotonic()
        self.end_time: Optional[float] = None
        self.events: List[Dict[str, Any]] = []

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        self.events.append({
            "name": name,
            "timestamp": datetime.utcnow().isoformat(),
            "attributes": attributes or {},
        })

    def finish(self) -> None:
        self.end_time = time.monotonic()

    @property
    def duration_seconds(self) -> float:
        if self.end_time is None:
            return time.monotonic() - self.start_time
        return self.end_time - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "duration_seconds": round(self.duration_seconds, 6),
            "events": self.events,
            "metadata": self.metadata,
        }


class ClusterTelemetry:
    """Unified telemetry for the distributed workflow cluster.

    Usage::

        telemetry = ClusterTelemetry(metrics=...)
        with telemetry.trace("leader_election") as span:
            span.add_event("campaign_started")
            # ... do work ...
    """

    def __init__(self, *, metrics: ClusterMetrics) -> None:
        self._metrics = metrics
        self._spans: List[ClusterSpan] = []
        self._max_spans = 10000

        # Timeline records
        self._leader_timeline: List[Dict[str, Any]] = []
        self._cluster_events: List[Dict[str, Any]] = []
        self._failover_timeline: List[Dict[str, Any]] = []
        self._recovery_timeline: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Tracing
    # ------------------------------------------------------------------

    @contextlib.contextmanager
    def trace(
        self,
        name: str,
        *,
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Generator[ClusterSpan, None, None]:
        """Create a tracing span for a cluster operation."""
        parent_id = cluster_trace_id.get()
        span = ClusterSpan(
            name=name,
            trace_id=trace_id or cluster_trace_id.get(),
            parent_id=parent_id,
            metadata=metadata,
        )
        token = cluster_trace_id.set(span.trace_id)
        try:
            yield span
        finally:
            cluster_trace_id.reset(token)
            span.finish()
            self._spans.append(span)
            if len(self._spans) > self._max_spans:
                self._spans = self._spans[-self._max_spans:]

            logger.debug("ClusterTelemetry: span %s (%s) completed in %.3fs",
                          span.name, span.span_id, span.duration_seconds)

    def get_spans(self, *, trace_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        spans = self._spans
        if trace_id:
            spans = [s for s in spans if s.trace_id == trace_id]
        return [s.to_dict() for s in spans[-limit:]]

    # ------------------------------------------------------------------
    # Leader Timeline
    # ------------------------------------------------------------------

    def record_leader_change(
        self,
        old_leader: Optional[str],
        new_leader: str,
        term: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "old_leader": old_leader,
            "new_leader": new_leader,
            "term": term,
            "metadata": metadata or {},
        }
        self._leader_timeline.append(entry)
        self._metrics.increment_leader_changes()
        logger.info("ClusterTelemetry: leader changed %s → %s (term %d)", old_leader, new_leader, term)

    def get_leader_timeline(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._leader_timeline[-limit:]

    # ------------------------------------------------------------------
    # Cluster Events
    # ------------------------------------------------------------------

    def record_cluster_event(
        self,
        event_type: str,
        node_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "node_id": node_id,
            "metadata": metadata or {},
        }
        self._cluster_events.append(entry)
        logger.info("ClusterTelemetry: cluster event %s on node %s", event_type, node_id)

    def get_cluster_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._cluster_events[-limit:]

    # ------------------------------------------------------------------
    # Failover Timeline
    # ------------------------------------------------------------------

    def record_failover_event(
        self,
        phase: str,
        failed_node_id: str,
        affected_executions: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "phase": phase,
            "failed_node_id": failed_node_id,
            "affected_executions": affected_executions,
            "metadata": metadata or {},
        }
        self._failover_timeline.append(entry)
        logger.info("ClusterTelemetry: failover phase=%s node=%s affected=%d",
                     phase, failed_node_id, affected_executions)

    def get_failover_timeline(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._failover_timeline[-limit:]

    # ------------------------------------------------------------------
    # Recovery Timeline
    # ------------------------------------------------------------------

    def record_recovery_event(
        self,
        phase: str,
        execution_id: str,
        node_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "phase": phase,
            "execution_id": execution_id,
            "node_id": node_id,
            "metadata": metadata or {},
        }
        self._recovery_timeline.append(entry)
        logger.info("ClusterTelemetry: recovery phase=%s execution=%s node=%s",
                     phase, execution_id, node_id)

    def get_recovery_timeline(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._recovery_timeline[-limit:]

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    def audit_log(
        self,
        action: str,
        actor: str,
        resource: str,
        result: str = "success",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Write an audit log entry."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "actor": actor,
            "resource": resource,
            "result": result,
            "metadata": metadata or {},
        }
        logger.info("ClusterTelemetry: AUDIT action=%s actor=%s resource=%s result=%s",
                     action, actor, resource, result)

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        return {
            "span_count": len(self._spans),
            "leader_timeline_count": len(self._leader_timeline),
            "cluster_events_count": len(self._cluster_events),
            "failover_timeline_count": len(self._failover_timeline),
            "recovery_timeline_count": len(self._recovery_timeline),
            "metrics": self._metrics.get_all_metrics(),
        }
