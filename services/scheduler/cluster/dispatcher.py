"""Cluster Dispatcher — routes jobs from the distributed queue to target workers.

The :class:`ClusterDispatcher` handles the final mile of scheduling:
selecting a target worker node, sending the job payload, and tracking
dispatch outcomes.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DispatchTarget:
    """A dispatch target (worker node + metadata)."""

    def __init__(
        self,
        node_id: str,
        *,
        host: str = "localhost",
        port: int = 9001,
        capacity: Optional[Dict[str, float]] = None,
    ) -> None:
        self.node_id = node_id
        self.host = host
        self.port = port
        self.capacity = capacity or {}
        self.active_jobs: int = 0

    @property
    def endpoint(self) -> str:
        return f"{self.host}:{self.port}"


class ClusterDispatcher:
    """Routes jobs from the distributed queue to target worker nodes.

    Responsibilities:
    - Select target worker based on capacity and affinity
    - Send job payload to the worker
    - Track dispatch status and outcomes
    - Drain in-flight dispatches during shutdown

    Usage::

        dispatcher = ClusterDispatcher(node_id="scheduler-1")
        await dispatcher.initialize()
        success = await dispatcher.send(target="worker-1", payload=job)
    """

    def __init__(
        self,
        node_id: str,
        *,
        max_concurrent_dispatches: int = 100,
        dispatch_timeout_seconds: float = 30.0,
    ) -> None:
        self._node_id = node_id
        self._max_concurrent = max_concurrent_dispatches
        self._dispatch_timeout = dispatch_timeout_seconds
        self._lock = threading.Lock()

        self._initialized = False
        self._targets: Dict[str, DispatchTarget] = {}
        self._in_flight: Dict[str, Dict[str, Any]] = {}
        self._dispatch_count: int = 0
        self._error_count: int = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def node_id(self) -> str:
        return self._node_id

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def in_flight_count(self) -> int:
        with self._lock:
            return len(self._in_flight)

    @property
    def dispatch_count(self) -> int:
        return self._dispatch_count

    @property
    def error_count(self) -> int:
        return self._error_count

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the dispatcher."""
        self._initialized = True
        logger.info("Cluster dispatcher initialized [node=%s]", self._node_id)

    async def drain(self) -> None:
        """Drain in-flight dispatches before shutdown."""
        with self._lock:
            pending = list(self._in_flight.keys())

        if pending:
            logger.info("Draining %d in-flight dispatches", len(pending))
            await asyncio.sleep(1.0)  # allow completion

        with self._lock:
            self._in_flight.clear()
        logger.info("Dispatcher drained [node=%s]", self._node_id)

    async def recover(self) -> None:
        """Recover dispatcher state after a node restart."""
        logger.info("Recovering dispatcher state [node=%s]", self._node_id)
        with self._lock:
            self._in_flight.clear()

    # ------------------------------------------------------------------
    # Target Management
    # ------------------------------------------------------------------

    def register_target(self, target: DispatchTarget) -> None:
        """Register a worker target."""
        with self._lock:
            self._targets[target.node_id] = target
        logger.debug("Registered dispatch target %s", target.node_id)

    def remove_target(self, node_id: str) -> None:
        """Remove a worker target."""
        with self._lock:
            self._targets.pop(node_id, None)

    def get_target(self, node_id: str) -> Optional[DispatchTarget]:
        """Get a target by node ID."""
        with self._lock:
            return self._targets.get(node_id)

    def select_target(self, *, prefer_node: Optional[str] = None) -> Optional[DispatchTarget]:
        """Select the best target for dispatch.

        Strategy: prefer specified node, then least-loaded.
        """
        with self._lock:
            if not self._targets:
                return None

            if prefer_node and prefer_node in self._targets:
                return self._targets[prefer_node]

            # Least-loaded selection
            return min(self._targets.values(), key=lambda t: t.active_jobs)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def send(
        self,
        target: str,
        payload: Any,
        *,
        timeout: Optional[float] = None,
    ) -> bool:
        """Send a job payload to a target worker.

        Args:
            target: Target node ID or endpoint.
            payload: The job payload to send.
            timeout: Dispatch timeout in seconds.

        Returns:
            True if dispatched successfully.
        """
        timeout = timeout or self._dispatch_timeout
        dispatch_id = f"disp-{self._dispatch_count + 1}"

        with self._lock:
            self._dispatch_count += 1
            self._in_flight[dispatch_id] = {
                "target": target,
                "started_at": datetime.now(timezone.utc),
                "status": "in_flight",
            }

        try:
            # Simulate dispatch (replace with actual RPC/HTTP call)
            await asyncio.sleep(0.01)

            with self._lock:
                self._in_flight[dispatch_id]["status"] = "completed"
                self._in_flight.pop(dispatch_id, None)

            logger.debug("Dispatched to %s [id=%s]", target, dispatch_id)
            return True

        except Exception as e:
            with self._lock:
                self._error_count += 1
                self._in_flight[dispatch_id]["status"] = "failed"
                self._in_flight[dispatch_id]["error"] = str(e)
                self._in_flight.pop(dispatch_id, None)

            logger.warning("Dispatch to %s failed: %s", target, e)
            return False

    async def broadcast(self, payload: Any) -> Dict[str, bool]:
        """Broadcast a payload to all registered targets.

        Returns:
            Dict mapping target node_id → success.
        """
        with self._lock:
            target_ids = list(self._targets.keys())

        results = {}
        tasks = [self.send(target=tid, payload=payload) for tid in target_ids]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        for tid, outcome in zip(target_ids, outcomes):
            results[tid] = outcome if isinstance(outcome, bool) else False

        return results

    def get_dispatcher_info(self) -> Dict[str, Any]:
        """Return dispatcher status summary."""
        return {
            "node_id": self._node_id,
            "initialized": self._initialized,
            "target_count": len(self._targets),
            "in_flight": self.in_flight_count,
            "max_concurrent": self._max_concurrent,
            "dispatch_count": self._dispatch_count,
            "error_count": self._error_count,
            "error_rate": self._error_count / max(self._dispatch_count, 1),
        }
