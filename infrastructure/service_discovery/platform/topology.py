"""Service topology for ICYQuant platform.

Provides ``ServiceTopology`` for exporting service graphs,
instance graphs, dependency graphs, and health graphs.
Enables future dashboard, workflow engine, and service
mesh integration.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .runtime_context import DiscoveryContext

logger = logging.getLogger(__name__)


class ServiceTopology:
    """Service topology graph management.

    Maintains service, instance, dependency, and health
    graphs for visualization and analysis.
    """

    def __init__(
        self, context: Optional[DiscoveryContext] = None
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or DiscoveryContext()
        self._service_graph: Dict[str, List[str]] = {}
        self._instance_graph: Dict[str, List[str]] = {}
        self._dependency_graph: Dict[str, List[str]] = {}
        self._health_graph: Dict[str, bool] = {}
        self._update_count = 0
        self._last_update: Optional[Dict[str, Any]] = None

    def update_service_graph(
        self, edges: Dict[str, List[str]]
    ) -> None:
        """Update the service graph.

        Args:
            edges: Mapping of service name to connected
                service names.
        """
        with self._lock:
            self._service_graph = dict(edges)
            self._update_count += 1
            self._record_update("service_graph", len(edges))

    def update_instance_graph(
        self, edges: Dict[str, List[str]]
    ) -> None:
        with self._lock:
            self._instance_graph = dict(edges)
            self._update_count += 1
            self._record_update("instance_graph", len(edges))

    def update_dependency_graph(
        self, edges: Dict[str, List[str]]
    ) -> None:
        with self._lock:
            self._dependency_graph = dict(edges)
            self._update_count += 1
            self._record_update("dependency_graph", len(edges))

    def update_health_graph(
        self, health_status: Dict[str, bool]
    ) -> None:
        with self._lock:
            self._health_graph = dict(health_status)
            self._update_count += 1
            self._record_update("health_graph", len(health_status))

    def get_service_graph(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "type": "service_graph",
                "nodes": sorted(self._service_graph.keys()),
                "edges": {
                    k: list(v)
                    for k, v in self._service_graph.items()
                },
                "timestamp": self._now_iso(),
            }

    def get_instance_graph(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "type": "instance_graph",
                "nodes": sorted(self._instance_graph.keys()),
                "edges": {
                    k: list(v)
                    for k, v in self._instance_graph.items()
                },
                "timestamp": self._now_iso(),
            }

    def get_dependency_graph(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "type": "dependency_graph",
                "nodes": sorted(self._dependency_graph.keys()),
                "edges": {
                    k: list(v)
                    for k, v in self._dependency_graph.items()
                },
                "timestamp": self._now_iso(),
            }

    def get_health_graph(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "type": "health_graph",
                "nodes": sorted(self._health_graph.keys()),
                "status": dict(self._health_graph),
                "healthy_count": sum(
                    1 for v in self._health_graph.values() if v
                ),
                "unhealthy_count": sum(
                    1 for v in self._health_graph.values() if not v
                ),
                "timestamp": self._now_iso(),
            }

    def get_topology(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "service_graph": {
                    k: list(v)
                    for k, v in self._service_graph.items()
                },
                "instance_graph": {
                    k: list(v)
                    for k, v in self._instance_graph.items()
                },
                "dependency_graph": {
                    k: list(v)
                    for k, v in self._dependency_graph.items()
                },
                "health_graph": dict(self._health_graph),
                "update_count": self._update_count,
                "timestamp": self._now_iso(),
            }

    def _record_update(
        self, graph_type: str, size: int
    ) -> None:
        self._last_update = {
            "graph_type": graph_type,
            "size": size,
            "timestamp": self._now_iso(),
        }

    @staticmethod
    def _now_iso() -> str:
        return datetime.utcnow().isoformat()

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "service_nodes": len(self._service_graph),
                "instance_nodes": len(self._instance_graph),
                "dependency_nodes": len(
                    self._dependency_graph
                ),
                "health_entries": len(self._health_graph),
                "update_count": self._update_count,
                "last_update": self._last_update,
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"ServiceTopology(services={len(self._service_graph)}, "
                f"instances={len(self._instance_graph)})"
            )
