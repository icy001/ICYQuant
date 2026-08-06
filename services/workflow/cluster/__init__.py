"""Workflow Cluster — distributed execution, scheduling, and high availability.

Package modules::

    cluster_manager      — unified cluster entry point
    cluster_node         — node data model (role, resources, capabilities)
    coordinator          — cluster-wide coordination (election, heartbeat, failover)
    leader_election      — leader election with pluggable backends
    consensus            — consensus abstraction (log replication, terms)
    lease_manager        — distributed lease management
    heartbeat            — heartbeat monitoring and timeout detection
    node_registry        — cluster node directory
    worker_registry      — worker resource tracking for scheduling
    scheduler            — distributed workflow scheduler
    dispatcher           — task dispatch with affinity and load balancing
    shard_manager        — workflow sharding (hash/range/dynamic)
    shard_allocator      — shard-to-worker allocation and rebalancing
    placement_strategy   — intelligent node placement
    load_balancer        — load balancing algorithms
    failover_manager     — automatic failover orchestration
    recovery_coordinator — cross-node workflow recovery
    checkpoint_sync      — cross-node checkpoint synchronization
    state_replication    — workflow state replication
    event_replication    — workflow event replication
    synchronization      — cluster metadata and config sync
    quorum               — majority-based decision making
    metrics              — Prometheus-compatible cluster metrics
    telemetry            — unified tracing, logging, and audit
    diagnostics          — cluster inspection and troubleshooting
    health               — aggregated health checking
"""

from .cluster_manager import WorkflowClusterManager, ClusterConfig, ClusterState
from .cluster_node import ClusterNode, NodeRole, NodeStatus, NodeResources, NodeCapabilities
from .coordinator import ClusterCoordinator, CoordinatorState
from .leader_election import LeaderElection, LeaderElectionBackend, ElectionState, LeaderLease
from .consensus import ConsensusEngine, ConsensusBackend, LogEntry
from .lease_manager import LeaseManager, Lease, LeaseType, LeaseState
from .heartbeat import HeartbeatMonitor, HeartbeatRecord
from .node_registry import NodeRegistry
from .worker_registry import WorkerRegistry, WorkerRecord
from .scheduler import DistributedScheduler, ScheduleRequest, ScheduleResult, SchedulePriority
from .dispatcher import Dispatcher, DispatchRequest, DispatchResult, DispatchPolicy
from .shard_manager import ShardManager, Shard, ShardStrategy
from .shard_allocator import ShardAllocator, ShardAllocation
from .placement_strategy import PlacementStrategy, PlacementDecision, PlacementPolicy
from .load_balancer import LoadBalancer, LoadBalancerAlgorithm, WorkerWeight
from .failover_manager import FailoverManager, FailoverRecord, FailoverState
from .recovery_coordinator import RecoveryCoordinator, RecoveryTask, RecoveryPhase
from .checkpoint_sync import CheckpointSync, SyncedCheckpoint
from .state_replication import StateReplication, StateEntry, ReplicationMode, ReplicationStatus
from .event_replication import EventReplication, ReplicatedEvent, EventType
from .synchronization import ClusterSynchronizer
from .quorum import QuorumManager, QuorumDecision, QuorumResult, QuorumVote
from .metrics import ClusterMetrics
from .telemetry import ClusterTelemetry, ClusterSpan
from .diagnostics import ClusterDiagnostics
from .health import ClusterHealthChecker

__all__ = [
    # Cluster management
    "WorkflowClusterManager",
    "ClusterConfig",
    "ClusterState",
    "ClusterNode",
    "NodeRole",
    "NodeStatus",
    "NodeResources",
    "NodeCapabilities",
    "ClusterCoordinator",
    "CoordinatorState",
    # Leadership & consensus
    "LeaderElection",
    "LeaderElectionBackend",
    "ElectionState",
    "LeaderLease",
    "ConsensusEngine",
    "ConsensusBackend",
    "LogEntry",
    # Leases & heartbeat
    "LeaseManager",
    "Lease",
    "LeaseType",
    "LeaseState",
    "HeartbeatMonitor",
    "HeartbeatRecord",
    # Registries
    "NodeRegistry",
    "WorkerRegistry",
    "WorkerRecord",
    # Scheduling
    "DistributedScheduler",
    "ScheduleRequest",
    "ScheduleResult",
    "SchedulePriority",
    "Dispatcher",
    "DispatchRequest",
    "DispatchResult",
    "DispatchPolicy",
    # Sharding
    "ShardManager",
    "Shard",
    "ShardStrategy",
    "ShardAllocator",
    "ShardAllocation",
    # Placement & load balancing
    "PlacementStrategy",
    "PlacementDecision",
    "PlacementPolicy",
    "LoadBalancer",
    "LoadBalancerAlgorithm",
    "WorkerWeight",
    # HA & recovery
    "FailoverManager",
    "FailoverRecord",
    "FailoverState",
    "RecoveryCoordinator",
    "RecoveryTask",
    "RecoveryPhase",
    # Checkpoint & replication
    "CheckpointSync",
    "SyncedCheckpoint",
    "StateReplication",
    "StateEntry",
    "ReplicationMode",
    "ReplicationStatus",
    "EventReplication",
    "ReplicatedEvent",
    "EventType",
    # Synchronization & quorum
    "ClusterSynchronizer",
    "QuorumManager",
    "QuorumDecision",
    "QuorumResult",
    "QuorumVote",
    # Observability
    "ClusterMetrics",
    "ClusterTelemetry",
    "ClusterSpan",
    "ClusterDiagnostics",
    "ClusterHealthChecker",
]
