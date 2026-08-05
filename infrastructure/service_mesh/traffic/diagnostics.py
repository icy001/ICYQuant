"""Traffic diagnostics for ICYQuant Service Mesh.

Provides ``TrafficDiagnostics`` for in-depth inspection of
traffic management state including routing tables, policy
evaluation history, and component health.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TrafficDiagnostics:
    """Diagnostics for traffic management components."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._routing_table: List[Dict[str, Any]] = []
        self._decision_history: List[Dict[str, Any]] = []
        self._component_status: Dict[str, Dict[str, Any]] = {}
        self._max_history = 500
        self._snapshot_count = 0

    def update_routing_table(
        self, routes: List[Dict[str, Any]]
    ) -> None:
        with self._lock:
            self._routing_table = [
                {**r, "_updated_at": datetime.utcnow().isoformat()}
                for r in routes
            ]

    def record_decision(
        self,
        route_id: str,
        matched: bool,
        target: str,
        reason: str = "",
    ) -> None:
        with self._lock:
            self._snapshot_count += 1
            decision = {
                "route_id": route_id,
                "matched": matched,
                "target": target,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
                "seq": self._snapshot_count,
            }
            self._decision_history.append(decision)
            if len(self._decision_history) > self._max_history:
                self._decision_history = self._decision_history[
                    -self._max_history:
                ]

    def set_component_status(
        self,
        component: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._lock:
            self._component_status[component] = {
                "status": status,
                "details": details or {},
                "updated_at": datetime.utcnow().isoformat(),
            }

    def get_routing_table(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._routing_table)

    def get_decision_history(
        self, limit: int = 50
    ) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._decision_history[-limit:])

    def get_component_status(
        self, component: Optional[str] = None
    ) -> Dict[str, Any]:
        with self._lock:
            if component:
                return self._component_status.get(component, {})
            return dict(self._component_status)

    def get_snapshot(self) -> Dict[str, Any]:
        """Get a full diagnostic snapshot."""
        with self._lock:
            return {
                "routing_table_count": len(self._routing_table),
                "decision_history_count": len(self._decision_history),
                "component_status": dict(self._component_status),
                "snapshot_count": self._snapshot_count,
                "timestamp": datetime.utcnow().isoformat(),
            }

    def get_stats(self) -> Dict[str, Any]:
        return self.get_snapshot()

    def clear(self) -> None:
        with self._lock:
            self._routing_table.clear()
            self._decision_history.clear()
            self._component_status.clear()
            self._snapshot_count = 0
