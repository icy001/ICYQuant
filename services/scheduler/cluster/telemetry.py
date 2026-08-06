"""Cluster Telemetry — unified tracing, metrics, and logging for the scheduler cluster.

Provides:
* Leader Timeline — track leadership changes
* Failover Timeline — record failover events with timing
* Recovery Timeline — trace recovery operations
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ClusterTelemetry:
    """Unified telemetry for the scheduler cluster.

    Collects:
    - Leader election timeline
    - Failover event timeline
    - Recovery operation traces
    - Queue replication traces

    Usage::

        telemetry = ClusterTelemetry()
        telemetry.record_leader_change(old_leader="s1", new_leader="s2", term=3)
        telemetry.record_failover(failed_leader="s1", new_leader="s2", duration_ms=450.0)
    """

    def __init__(self, *, max_events: int = 1000) -> None:
        self._max_events = max_events
        self._lock = threading.Lock()

        self._leader_timeline: List[Dict[str, Any]] = []
        self._failover_timeline: List[Dict[str, Any]] = []
        self._recovery_timeline: List[Dict[str, Any]] = []
        self._replication_traces: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Leader Timeline
    # ------------------------------------------------------------------

    def record_leader_change(
        self,
        old_leader: Optional[str],
        new_leader: str,
        term: int,
    ) -> str:
        """Record a leadership change event."""
        event_id = str(uuid.uuid4())[:8]
        event = {
            "event_id": event_id,
            "old_leader": old_leader,
            "new_leader": new_leader,
            "term": term,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._leader_timeline.append(event)
            if len(self._leader_timeline) > self._max_events:
                self._leader_timeline = self._leader_timeline[-self._max_events:]
        logger.info("Leader changed: %s → %s [term=%d]", old_leader, new_leader, term)
        return event_id

    # ------------------------------------------------------------------
    # Failover Timeline
    # ------------------------------------------------------------------

    def record_failover(
        self,
        failed_leader: str,
        new_leader: str,
        duration_ms: float,
        *,
        jobs_recovered: int = 0,
        success: bool = True,
    ) -> str:
        """Record a failover event."""
        event_id = str(uuid.uuid4())[:8]
        event = {
            "event_id": event_id,
            "failed_leader": failed_leader,
            "new_leader": new_leader,
            "duration_ms": duration_ms,
            "jobs_recovered": jobs_recovered,
            "success": success,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._failover_timeline.append(event)
            if len(self._failover_timeline) > self._max_events:
                self._failover_timeline = self._failover_timeline[-self._max_events:]
        logger.info("Failover: %s → %s [%.1fms, success=%s]",
                     failed_leader, new_leader, duration_ms, success)
        return event_id

    # ------------------------------------------------------------------
    # Recovery Timeline
    # ------------------------------------------------------------------

    def record_recovery(
        self,
        node_id: str,
        plan_id: str,
        duration_ms: float,
        *,
        steps_completed: int = 0,
        total_steps: int = 0,
        success: bool = True,
    ) -> str:
        """Record a recovery event."""
        event_id = str(uuid.uuid4())[:8]
        event = {
            "event_id": event_id,
            "node_id": node_id,
            "plan_id": plan_id,
            "duration_ms": duration_ms,
            "steps_completed": steps_completed,
            "total_steps": total_steps,
            "success": success,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._recovery_timeline.append(event)
            if len(self._recovery_timeline) > self._max_events:
                self._recovery_timeline = self._recovery_timeline[-self._max_events:]
        logger.info("Recovery: node=%s plan=%s [%.1fms, success=%s]",
                     node_id, plan_id, duration_ms, success)
        return event_id

    # ------------------------------------------------------------------
    # Replication Trace
    # ------------------------------------------------------------------

    def record_replication(
        self,
        entry_id: str,
        target_node: str,
        latency_ms: float,
        *,
        success: bool = True,
    ) -> None:
        """Record a queue replication trace."""
        trace = {
            "entry_id": entry_id,
            "target_node": target_node,
            "latency_ms": latency_ms,
            "success": success,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._replication_traces.append(trace)
            if len(self._replication_traces) > self._max_events:
                self._replication_traces = self._replication_traces[-self._max_events:]

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------

    def get_leader_timeline(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent leader change events."""
        with self._lock:
            return list(self._leader_timeline[-limit:])

    def get_failover_timeline(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent failover events."""
        with self._lock:
            return list(self._failover_timeline[-limit:])

    def get_recovery_timeline(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent recovery events."""
        with self._lock:
            return list(self._recovery_timeline[-limit:])

    def get_telemetry_snapshot(self) -> Dict[str, Any]:
        """Return a telemetry summary."""
        with self._lock:
            return {
                "leader_changes": len(self._leader_timeline),
                "failover_events": len(self._failover_timeline),
                "recovery_events": len(self._recovery_timeline),
                "replication_traces": len(self._replication_traces),
                "last_leader_change": self._leader_timeline[-1] if self._leader_timeline else None,
                "last_failover": self._failover_timeline[-1] if self._failover_timeline else None,
            }
