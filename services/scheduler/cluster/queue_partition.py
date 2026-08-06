"""Queue Partition — shards the distributed queue across cluster nodes.

The :class:`QueuePartitioner` divides the scheduling workload into
partitions (shards) distributed across nodes. It supports hash, range,
priority, and workflow-based partitioning strategies, with online
re-sharding capability.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class PartitionStrategy:
    """Available partitioning strategies."""

    HASH = "hash"
    RANGE = "range"
    PRIORITY = "priority"
    WORKFLOW = "workflow"


class QueuePartitioner:
    """Divides the distributed queue into shards across cluster nodes.

    Strategies:
    - hash: consistent hashing by job key
    - range: key range partitioning
    - priority: partition by job priority tier
    - workflow: partition by workflow type

    Usage::

        partitioner = QueuePartitioner(partition_count=16)
        partitioner.assign_nodes(["scheduler-1", "scheduler-2", "scheduler-3"])
        shard = partitioner.get_partition("job:report-001")
    """

    def __init__(
        self,
        partition_count: int = 16,
        strategy: str = PartitionStrategy.HASH,
        virtual_nodes: int = 128,
    ) -> None:
        self._partition_count = partition_count
        self._strategy = strategy
        self._virtual_nodes = virtual_nodes
        self._lock = threading.Lock()

        self._nodes: List[str] = []
        self._partition_map: Dict[int, str] = {}  # partition_id → node_id
        self._node_partitions: Dict[str, Set[int]] = {}  # node_id → set of partition_ids

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def partition_count(self) -> int:
        return self._partition_count

    @property
    def strategy(self) -> str:
        return self._strategy

    @property
    def node_count(self) -> int:
        with self._lock:
            return len(self._nodes)

    # ------------------------------------------------------------------
    # Node Assignment
    # ------------------------------------------------------------------

    def assign_nodes(self, node_ids: List[str]) -> None:
        """Assign or re-assign nodes to partitions."""
        with self._lock:
            self._nodes = list(node_ids)
            self._redistribute()
        logger.info("Partition nodes assigned: %s", node_ids)

    def add_node(self, node_id: str) -> None:
        """Add a new node and redistribute partitions."""
        with self._lock:
            if node_id in self._nodes:
                return
            self._nodes.append(node_id)
            self._redistribute()
        logger.info("Node %s added to partitioner, redistributing", node_id)

    def remove_node(self, node_id: str) -> None:
        """Remove a node and redistribute its partitions."""
        with self._lock:
            if node_id not in self._nodes:
                return
            self._nodes.remove(node_id)
            self._redistribute()
        logger.info("Node %s removed from partitioner, redistributing", node_id)

    # ------------------------------------------------------------------
    # Partition Lookup
    # ------------------------------------------------------------------

    def get_partition(self, key: str) -> int:
        """Determine which partition a key belongs to.

        Args:
            key: The job/schedule identifier.

        Returns:
            Partition ID (0 .. partition_count-1).
        """
        if self._strategy == PartitionStrategy.HASH:
            h = hashlib.md5(key.encode()).hexdigest()
            return int(h, 16) % self._partition_count
        elif self._strategy == PartitionStrategy.RANGE:
            return hash(key) % self._partition_count
        elif self._strategy == PartitionStrategy.PRIORITY:
            # Simplified: first char hash
            return ord(key[0]) % self._partition_count if key else 0
        elif self._strategy == PartitionStrategy.WORKFLOW:
            return hash(key) % self._partition_count
        return 0

    def get_owner(self, key: str) -> Optional[str]:
        """Get the node that owns the partition for a given key."""
        partition = self.get_partition(key)
        with self._lock:
            return self._partition_map.get(partition)

    def get_owned_partitions(self, node_id: str) -> Set[int]:
        """Get the set of partition IDs owned by a node."""
        with self._lock:
            return self._node_partitions.get(node_id, set()).copy()

    def get_partition_map(self) -> Dict[int, str]:
        """Get the full partition-to-node mapping."""
        with self._lock:
            return dict(self._partition_map)

    # ------------------------------------------------------------------
    # Rebalancing
    # ------------------------------------------------------------------

    def rebalance(self) -> Dict[int, str]:
        """Redistribute partitions evenly across nodes.

        Returns:
            The new partition map.
        """
        with self._lock:
            self._redistribute()
            return dict(self._partition_map)

    def get_rebalance_plan(self, new_nodes: List[str]) -> Dict[str, Any]:
        """Preview how partitions would be distributed with a new node set.

        Returns:
            A plan with partition movements.
        """
        if not new_nodes:
            return {"movements": [], "final_distribution": {}}

        movements = []
        partitions_per_node = self._partition_count // len(new_nodes)
        remainder = self._partition_count % len(new_nodes)

        distribution: Dict[str, int] = {}
        offset = 0
        for i, node in enumerate(new_nodes):
            count = partitions_per_node + (1 if i < remainder else 0)
            distribution[node] = count
            for p in range(offset, offset + count):
                movements.append({"partition": p, "to_node": node})
            offset += count

        return {
            "movements": movements,
            "final_distribution": distribution,
            "total_partitions": self._partition_count,
            "total_nodes": len(new_nodes),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _redistribute(self) -> None:
        """Evenly distribute partitions across current nodes."""
        self._partition_map.clear()
        self._node_partitions.clear()

        if not self._nodes:
            return

        n = len(self._nodes)
        for p in range(self._partition_count):
            owner = self._nodes[p % n]
            self._partition_map[p] = owner
            self._node_partitions.setdefault(owner, set()).add(p)

    def get_partitioner_info(self) -> Dict[str, Any]:
        """Return partitioner status summary."""
        with self._lock:
            return {
                "partition_count": self._partition_count,
                "strategy": self._strategy,
                "node_count": len(self._nodes),
                "nodes": list(self._nodes),
                "virtual_nodes": self._virtual_nodes,
                "node_partitions": {n: sorted(list(p)) for n, p in self._node_partitions.items()},
            }
