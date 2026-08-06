"""ICYQuant Scheduler Cluster — high-availability distributed scheduler cluster.

Provides:
- Cluster lifecycle management (join/leave/sync)
- Leader election with consensus abstraction
- Distributed queue with partitioning and replication
- State replication for seamless failover
- Automatic failover and disaster recovery
- Multi-region scheduling framework
"""

from .cluster_manager import SchedulerClusterManager, ClusterState
from .cluster_runtime import ClusterRuntime, ClusterRuntimePhase
from .coordinator import ClusterCoordinator, CoordinatorRole
from .scheduler_node import SchedulerNode, NodeRole
from .node_registry import NodeRegistry, NodeStatus
from .heartbeat_manager import HeartbeatManager, HeartbeatStatus
from .health_monitor import ClusterHealthMonitor, NodeHealthStatus
from .leader_election import LeaderElection, ElectionResult, ElectionProvider
from .consensus import ConsensusLayer, ConsensusResult
from .lease_manager import LeaseManager, LeaseStatus
from .distributed_lock import DistributedLock, LockType, LockAcquisition
from .distributed_queue import DistributedQueue, QueueType, QueueEntry
from .queue_partition import QueuePartitioner, PartitionStrategy
from .queue_replication import QueueReplication, ReplicationMode
from .queue_rebalancer import QueueRebalancer, RebalancePlan
from .scheduler_replication import SchedulerReplication, ReplicationState
from .state_sync import StateSync, SyncMode
from .job_replication import JobReplication, JobReplica
from .dispatcher import ClusterDispatcher, DispatchTarget
from .failover_manager import FailoverManager, FailoverState
from .recovery_coordinator import RecoveryCoordinator, RecoveryPlan
from .disaster_recovery import DisasterRecovery, DRSite
from .multi_region import MultiRegionManager, RegionRole
from .topology_manager import ClusterTopologyManager, ClusterDomain
from .metrics import ClusterMetrics
from .telemetry import ClusterTelemetry
from .diagnostics import ClusterDiagnostics
from .health import ClusterHealth

__all__ = [
    # Core Cluster
    "SchedulerClusterManager",
    "ClusterState",
    "ClusterRuntime",
    "ClusterRuntimePhase",
    "ClusterCoordinator",
    "CoordinatorRole",
    "SchedulerNode",
    "NodeRole",
    # Node & Heartbeat
    "NodeRegistry",
    "NodeStatus",
    "HeartbeatManager",
    "HeartbeatStatus",
    "ClusterHealthMonitor",
    "NodeHealthStatus",
    # Leader Election & Consensus
    "LeaderElection",
    "ElectionResult",
    "ElectionProvider",
    "ConsensusLayer",
    "ConsensusResult",
    # Lease & Lock
    "LeaseManager",
    "LeaseStatus",
    "DistributedLock",
    "LockType",
    "LockAcquisition",
    # Distributed Queue
    "DistributedQueue",
    "QueueType",
    "QueueEntry",
    "QueuePartitioner",
    "PartitionStrategy",
    "QueueReplication",
    "ReplicationMode",
    "QueueRebalancer",
    "RebalancePlan",
    # State & Job Replication
    "SchedulerReplication",
    "ReplicationState",
    "StateSync",
    "SyncMode",
    "JobReplication",
    "JobReplica",
    # Dispatch
    "ClusterDispatcher",
    "DispatchTarget",
    # Failover & Recovery
    "FailoverManager",
    "FailoverState",
    "RecoveryCoordinator",
    "RecoveryPlan",
    "DisasterRecovery",
    "DRSite",
    # Multi-Region
    "MultiRegionManager",
    "RegionRole",
    # Topology
    "ClusterTopologyManager",
    "ClusterDomain",
    # Observability
    "ClusterMetrics",
    "ClusterTelemetry",
    "ClusterDiagnostics",
    "ClusterHealth",
]
