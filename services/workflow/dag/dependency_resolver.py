"""
Dependency Resolver — resolves node dependencies and determines execution readiness.

Automatically tracks which nodes are ready to execute based on completed predecessors.
Thread-safe for concurrent access from the scheduler and worker pool.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from services.workflow.dag.dependency_graph import DependencyGraph, Dependency

logger = logging.getLogger(__name__)


@dataclass
class ResolverState:
    """Mutable state for the dependency resolver."""

    completed: Set[str] = field(default_factory=set)
    failed: Set[str] = field(default_factory=set)
    skipped: Set[str] = field(default_factory=set)
    running: Set[str] = field(default_factory=set)
    pending: Set[str] = field(default_factory=set)
    remaining_indegrees: Dict[str, int] = field(default_factory=dict)


class DependencyResolver:
    """
    Resolves node dependencies and tracks execution readiness.

    Uses indegree counting for O(1) readiness checks:
    - When a node completes, decrement indegree of all its dependents.
    - A node is ready when its remaining indegree reaches 0.

    Thread-safe via asyncio.Lock.
    """

    def __init__(self, graph: DependencyGraph):
        self.graph = graph
        self._state = ResolverState()
        self._lock = asyncio.Lock()
        self._ready_event = asyncio.Event()

        # Initialize: all nodes are pending, indegree from graph
        for node_id in graph.nodes:
            self._state.pending.add(node_id)
            self._state.remaining_indegrees[node_id] = graph.get_indegree(node_id)

    async def mark_completed(self, node_id: str) -> List[str]:
        """
        Mark a node as completed. Returns list of newly-ready nodes.

        Thread-safe: uses lock to ensure atomic state updates.
        """
        async with self._lock:
            if node_id in self._state.running:
                self._state.running.discard(node_id)
            self._state.completed.add(node_id)
            self._state.pending.discard(node_id)

            newly_ready: List[str] = []
            for dep in self.graph.get_dependents(node_id):
                target = dep.target_id
                if target in self._state.completed or target in self._state.failed:
                    continue
                self._state.remaining_indegrees[target] -= 1
                if self._state.remaining_indegrees[target] <= 0 and target in self._state.pending:
                    newly_ready.append(target)

            if newly_ready:
                self._ready_event.set()
                self._ready_event.clear()

            return newly_ready

    async def mark_failed(self, node_id: str) -> None:
        """Mark a node as failed."""
        async with self._lock:
            self._state.running.discard(node_id)
            self._state.failed.add(node_id)
            self._state.pending.discard(node_id)

    async def mark_skipped(self, node_id: str) -> None:
        """Mark a node as skipped (e.g., conditional branch not taken)."""
        async with self._lock:
            self._state.skipped.add(node_id)
            self._state.pending.discard(node_id)
            # Skipped nodes release their dependents
            for dep in self.graph.get_dependents(node_id):
                target = dep.target_id
                if target not in self._state.completed and target not in self._state.failed:
                    self._state.remaining_indegrees[target] = max(
                        0, self._state.remaining_indegrees[target] - 1
                    )

    async def mark_running(self, node_id: str) -> None:
        """Mark a node as currently executing."""
        async with self._lock:
            self._state.running.add(node_id)
            self._state.pending.discard(node_id)

    async def get_ready_nodes(self) -> List[str]:
        """
        Get all currently ready nodes (indegree == 0, not yet completed/failed/running).
        """
        async with self._lock:
            ready = []
            for node_id in list(self._state.pending):
                if node_id in self._state.running:
                    continue
                if self._state.remaining_indegrees.get(node_id, 0) <= 0:
                    ready.append(node_id)
            return ready

    async def is_complete(self) -> bool:
        """Check if all nodes have been processed."""
        async with self._lock:
            return len(self._state.pending) == 0 and len(self._state.running) == 0

    async def has_failures(self) -> bool:
        """Check if any nodes have failed."""
        async with self._lock:
            return len(self._state.failed) > 0

    async def wait_for_ready(self, timeout: Optional[float] = None) -> List[str]:
        """Wait for nodes to become ready. Returns list of ready nodes."""
        ready = await self.get_ready_nodes()
        if ready:
            return ready
        try:
            await asyncio.wait_for(self._ready_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass
        return await self.get_ready_nodes()

    @property
    def completed_count(self) -> int:
        return len(self._state.completed)

    @property
    def failed_count(self) -> int:
        return len(self._state.failed)

    @property
    def running_count(self) -> int:
        return len(self._state.running)

    @property
    def pending_count(self) -> int:
        return len(self._state.pending)

    def get_state_summary(self) -> Dict[str, Any]:
        return {
            "completed": self.completed_count,
            "failed": self.failed_count,
            "skipped": len(self._state.skipped),
            "running": self.running_count,
            "pending": self.pending_count,
            "total": self.graph.node_count,
        }
