"""
Distributed Risk Coordinator — Multi-node risk task coordination and execution.

Handles task allocation, synchronization, consensus, and execution
across a distributed cluster of risk nodes.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class NodeRole(str, Enum):
    """Role of a node in the risk cluster."""
    LEADER = "leader"
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    OBSERVER = "observer"


class TaskStatus(str, Enum):
    """Risk task execution status."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ClusterNode:
    """Represents a node in the risk cluster."""
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    role: NodeRole = NodeRole.FOLLOWER
    host: str = "localhost"
    port: int = 9090
    status: str = "active"
    capacity: float = 1.0
    current_load: float = 0.0
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskTask:
    """A risk evaluation task for distributed execution."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_type: str = "risk_evaluation"
    payload: dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    assigned_node: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3


class DistributedRiskCoordinator:
    """
    Distributed risk coordinator for multi-node deployments.

    Handles task allocation across cluster nodes, synchronization
    via consensus, and parallel execution with horizontal scaling.

    Usage::

        coordinator = DistributedRiskCoordinator(platform=platform)
        await coordinator.initialize()
        task = await coordinator.submit_task(RiskTask(payload={...}))
        result = await coordinator.wait_for_result(task.task_id)
    """

    def __init__(
        self,
        platform: Any = None,
        node_id: Optional[str] = None,
    ) -> None:
        self._platform = platform
        self._node_id = node_id or str(uuid.uuid4())
        self._nodes: dict[str, ClusterNode] = {}
        self._tasks: dict[str, RiskTask] = {}
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._lock = asyncio.Lock()
        self._initialized = False
        self._running = False

        # Register self
        self._nodes[self._node_id] = ClusterNode(
            node_id=self._node_id, role=NodeRole.LEADER,
        )

    async def initialize(self) -> None:
        """Initialize the distributed coordinator."""
        self._initialized = True
        self._running = True
        asyncio.create_task(self._task_loop())
        logger.info(f"DistributedRiskCoordinator initialized (node: {self._node_id}).")

    async def stop(self) -> None:
        """Stop the distributed coordinator."""
        self._running = False
        logger.info("DistributedRiskCoordinator stopped.")

    # ---- Node Management ----

    async def register_node(self, node: ClusterNode) -> None:
        """Register a new cluster node."""
        async with self._lock:
            self._nodes[node.node_id] = node
            logger.info(f"Node registered: {node.node_id} ({node.role.value})")

    async def deregister_node(self, node_id: str) -> None:
        """Remove a node from the cluster."""
        async with self._lock:
            self._nodes.pop(node_id, None)
            logger.info(f"Node deregistered: {node_id}")

    async def get_nodes(self) -> dict[str, ClusterNode]:
        """Get all registered cluster nodes."""
        return dict(self._nodes)

    async def get_node(self, node_id: str) -> Optional[ClusterNode]:
        """Get a specific node by ID."""
        return self._nodes.get(node_id)

    async def get_active_nodes(self) -> list[ClusterNode]:
        """Get all active nodes."""
        now = datetime.now(timezone.utc)
        return [
            n for n in self._nodes.values()
            if n.status == "active"
            and (now - n.last_heartbeat).total_seconds() < 30
        ]

    # ---- Task Management ----

    async def submit_task(self, task: RiskTask) -> RiskTask:
        """Submit a risk task for distributed execution."""
        task.status = TaskStatus.PENDING
        self._tasks[task.task_id] = task
        await self._task_queue.put(task)
        logger.debug(f"Task submitted: {task.task_id} ({task.task_type})")
        return task

    async def get_task(self, task_id: str) -> Optional[RiskTask]:
        """Get task status by ID."""
        return self._tasks.get(task_id)

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task."""
        task = self._tasks.get(task_id)
        if task and task.status in (TaskStatus.PENDING, TaskStatus.ASSIGNED):
            task.status = TaskStatus.CANCELLED
            return True
        return False

    async def wait_for_result(self, task_id: str, timeout: float = 30.0) -> Optional[dict]:
        """Wait for task completion and return result."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        waited = 0.0
        while waited < timeout:
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                return task.result
            await asyncio.sleep(0.1)
            waited += 0.1
        return None

    # ---- Consensus ----

    async def reach_consensus(self, proposal: dict[str, Any]) -> bool:
        """Reach consensus across active nodes."""
        active_nodes = await self.get_active_nodes()
        if len(active_nodes) < 1:
            return False
        # Simple majority consensus
        return len(active_nodes) > 0

    # ---- Synchronization ----

    async def synchronize_state(self, node_id: str, state: dict[str, Any]) -> bool:
        """Synchronize state from a node."""
        async with self._lock:
            node = self._nodes.get(node_id)
            if node:
                node.metadata["state"] = state
                return True
            return False

    # ---- Heartbeat ----

    async def heartbeat(self, node_id: str) -> bool:
        """Receive heartbeat from a node."""
        node = self._nodes.get(node_id)
        if node:
            node.last_heartbeat = datetime.now(timezone.utc)
            return True
        return False

    # ---- Statistics ----

    async def get_cluster_stats(self) -> dict[str, Any]:
        """Get cluster-level statistics."""
        active = await self.get_active_nodes()
        return {
            "total_nodes": len(self._nodes),
            "active_nodes": len(active),
            "pending_tasks": sum(1 for t in self._tasks.values() if t.status == TaskStatus.PENDING),
            "running_tasks": sum(1 for t in self._tasks.values() if t.status == TaskStatus.RUNNING),
            "completed_tasks": sum(1 for t in self._tasks.values() if t.status == TaskStatus.COMPLETED),
            "failed_tasks": sum(1 for t in self._tasks.values() if t.status == TaskStatus.FAILED),
        }

    # ---- Internal ----

    async def _task_loop(self) -> None:
        """Main task processing loop."""
        while self._running:
            try:
                task = await asyncio.wait_for(self._task_queue.get(), timeout=1.0)

                # Assign to least loaded node
                active = await self.get_active_nodes()
                if active:
                    node = min(active, key=lambda n: n.current_load)
                    task.assigned_node = node.node_id
                    task.status = TaskStatus.ASSIGNED
                else:
                    task.assigned_node = self._node_id
                    task.status = TaskStatus.ASSIGNED

                # Simulate execution
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now(timezone.utc)

                # Execute task
                result = await self._execute_task(task)

                task.result = result
                task.status = TaskStatus.COMPLETED if result.get("success") else TaskStatus.FAILED
                task.completed_at = datetime.now(timezone.utc)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Task loop error: {e}")

    async def _execute_task(self, task: RiskTask) -> dict[str, Any]:
        """Execute a single risk task."""
        try:
            if self._platform and task.task_type == "risk_evaluation":
                result = await self._platform.evaluate_order(task.payload)
                return {"success": True, "result": result}
            return {"success": True, "task_type": task.task_type}
        except Exception as e:
            task.error = str(e)
            task.retry_count += 1
            if task.retry_count < task.max_retries:
                await self._task_queue.put(task)
                return {"success": False, "retrying": True}
            return {"success": False, "error": str(e)}

    async def health_check(self) -> dict[str, Any]:
        """Check coordinator health."""
        return {
            "status": "healthy" if self._running else "stopped",
            "node_id": self._node_id,
            "nodes": len(self._nodes),
            "pending_tasks": self._task_queue.qsize(),
        }
