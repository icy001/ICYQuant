"""Resource Telemetry — tracing and timeline tracking for resource scheduling.

Tracks placement timelines, scaling events, and resource usage patterns
for observability and debugging.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class PlacementEvent:
    """A single placement event for timeline tracking."""

    job_id: str
    node_id: str
    cpu_cores: float
    memory_mb: float
    score: float
    strategy: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "node_id": self.node_id,
            "cpu_cores": self.cpu_cores,
            "memory_mb": self.memory_mb,
            "score": self.score,
            "strategy": self.strategy,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
        }


@dataclass
class ScalingEvent:
    """A scaling event for timeline tracking."""

    action: str
    from_nodes: int
    to_nodes: int
    reason: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "from_nodes": self.from_nodes,
            "to_nodes": self.to_nodes,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
        }


class ResourceTelemetry:
    """Telemetry for resource scheduling decisions.

    Usage::

        tel = ResourceTelemetry()
        tel.record_placement(PlacementEvent(job_id="j1", node_id="n1", ...))
        tel.record_scaling(ScalingEvent(action="scale_out", ...))
    """

    def __init__(self, max_placement_events: int = 100_000,
                 max_scaling_events: int = 10_000) -> None:
        self._lock = threading.RLock()
        self._placement_timeline: List[PlacementEvent] = []
        self._scaling_timeline: List[ScalingEvent] = []
        self._max_placement = max_placement_events
        self._max_scaling = max_scaling_events

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_placement(self, event: PlacementEvent) -> None:
        with self._lock:
            self._placement_timeline.append(event)
            if len(self._placement_timeline) > self._max_placement:
                self._placement_timeline = self._placement_timeline[-self._max_placement:]

    def record_scaling(self, event: ScalingEvent) -> None:
        with self._lock:
            self._scaling_timeline.append(event)
            if len(self._scaling_timeline) > self._max_scaling:
                self._scaling_timeline = self._scaling_timeline[-self._max_scaling:]

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_recent_placements(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return [e.to_dict() for e in self._placement_timeline[-limit:]]

    def get_recent_scaling(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return [e.to_dict() for e in self._scaling_timeline[-limit:]]

    def get_placement_stats(self) -> Dict[str, Any]:
        with self._lock:
            if not self._placement_timeline:
                return {"count": 0}
            scores = [e.score for e in self._placement_timeline]
            return {
                "count": len(self._placement_timeline),
                "avg_score": sum(scores) / len(scores),
                "max_score": max(scores),
                "min_score": min(scores),
            }

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "placement_events": len(self._placement_timeline),
                "scaling_events": len(self._scaling_timeline),
            }
