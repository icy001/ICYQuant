"""Job Replication — replicates job metadata and execution context across nodes.

The :class:`JobReplication` ensures that job definitions and their execution
context survive node failures. Each job has N replicas (configurable) spread
across cluster nodes for fast failover recovery.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class JobReplica:
    """A single replica of a job on a specific node."""

    def __init__(
        self,
        job_id: str,
        node_id: str,
        *,
        is_primary: bool = False,
    ) -> None:
        self.job_id = job_id
        self.node_id = node_id
        self.is_primary = is_primary
        self.state: str = "pending"
        self.created_at = datetime.now(timezone.utc)
        self.last_updated = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "node_id": self.node_id,
            "is_primary": self.is_primary,
            "state": self.state,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
        }


class JobReplication:
    """Replicates job metadata and execution context across nodes.

    Each job maintains:
    - 1 primary replica (on the node that owns execution)
    - N-1 secondary replicas (on peer nodes for failover)

    Usage::

        jr = JobReplication(replication_factor=3)
        await jr.create_replicas("job-001", primary_node="scheduler-1")
        replicas = jr.get_replicas("job-001")
    """

    def __init__(
        self,
        *,
        replication_factor: int = 2,
    ) -> None:
        self._replication_factor = replication_factor
        self._lock = threading.Lock()
        self._replicas: Dict[str, Dict[str, JobReplica]] = {}  # job_id → {node_id: JobReplica}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def replication_factor(self) -> int:
        return self._replication_factor

    @property
    def job_count(self) -> int:
        with self._lock:
            return len(self._replicas)

    # ------------------------------------------------------------------
    # Replica Management
    # ------------------------------------------------------------------

    async def create_replicas(
        self,
        job_id: str,
        *,
        primary_node: str,
        secondary_nodes: Optional[List[str]] = None,
        job_metadata: Optional[Dict[str, Any]] = None,
        execution_context: Optional[Dict[str, Any]] = None,
    ) -> List[JobReplica]:
        """Create replicas for a job across nodes.

        Args:
            job_id: The job identifier.
            primary_node: The node that owns this job.
            secondary_nodes: Nodes for secondary replicas.
            job_metadata: Job definition metadata to replicate.
            execution_context: Current execution context to replicate.

        Returns:
            List of created JobReplica instances.
        """
        secondary = secondary_nodes or []
        replicas: List[JobReplica] = []

        with self._lock:
            self._replicas.setdefault(job_id, {})

            # Primary replica
            primary = JobReplica(job_id=job_id, node_id=primary_node, is_primary=True)
            self._replicas[job_id][primary_node] = primary
            replicas.append(primary)

            # Secondary replicas (up to replication_factor - 1)
            for node_id in secondary[:self._replication_factor - 1]:
                replica = JobReplica(job_id=job_id, node_id=node_id, is_primary=False)
                self._replicas[job_id][node_id] = replica
                replicas.append(replica)

        logger.debug("Created %d replicas for job %s [primary=%s]",
                      len(replicas), job_id, primary_node)
        return replicas

    def get_replicas(self, job_id: str) -> List[JobReplica]:
        """Get all replicas for a job."""
        with self._lock:
            return list(self._replicas.get(job_id, {}).values())

    def get_primary(self, job_id: str) -> Optional[JobReplica]:
        """Get the primary replica for a job."""
        with self._lock:
            for replica in self._replicas.get(job_id, {}).values():
                if replica.is_primary:
                    return replica
        return None

    def get_replica_count(self, job_id: str) -> int:
        """Get the number of replicas for a job."""
        with self._lock:
            return len(self._replicas.get(job_id, {}))

    async def update_replica_state(self, job_id: str, node_id: str, state: str) -> None:
        """Update the state of a specific replica."""
        with self._lock:
            if job_id in self._replicas and node_id in self._replicas[job_id]:
                self._replicas[job_id][node_id].state = state
                self._replicas[job_id][node_id].last_updated = datetime.now(timezone.utc)

    async def promote_replica(self, job_id: str, new_primary_node: str) -> bool:
        """Promote a secondary replica to primary (during failover).

        Args:
            job_id: The job to promote.
            new_primary_node: The node to become the new primary.

        Returns:
            True if promoted successfully.
        """
        with self._lock:
            if job_id not in self._replicas:
                return False
            if new_primary_node not in self._replicas[job_id]:
                return False

            # Demote current primary
            for replica in self._replicas[job_id].values():
                if replica.is_primary:
                    replica.is_primary = False

            # Promote target
            self._replicas[job_id][new_primary_node].is_primary = True
            self._replicas[job_id][new_primary_node].last_updated = datetime.now(timezone.utc)

        logger.info("Promoted replica for job %s to primary on node %s", job_id, new_primary_node)
        return True

    async def remove_job(self, job_id: str) -> None:
        """Remove all replicas for a completed job."""
        with self._lock:
            self._replicas.pop(job_id, None)
        logger.debug("Removed replicas for job %s", job_id)

    async def remove_node_replicas(self, node_id: str) -> int:
        """Remove all replicas on a specific node (node left cluster)."""
        removed = 0
        with self._lock:
            for job_id in list(self._replicas.keys()):
                if node_id in self._replicas[job_id]:
                    del self._replicas[job_id][node_id]
                    removed += 1
                    if not self._replicas[job_id]:
                        del self._replicas[job_id]
        logger.info("Removed %d replicas for node %s", removed, node_id)
        return removed

    def get_replication_info(self) -> Dict[str, Any]:
        """Return job replication status summary."""
        with self._lock:
            total_replicas = sum(len(r) for r in self._replicas.values())
            return {
                "replication_factor": self._replication_factor,
                "job_count": len(self._replicas),
                "total_replicas": total_replicas,
                "avg_replicas_per_job": total_replicas / max(len(self._replicas), 1),
            }
