"""ICYQuant Resource Scheduler — resource-aware scheduling engine.

The resource scheduler is the *where* layer. It manages CPU, memory, GPU,
IO, and concurrency resources across the cluster, making intelligent
placement decisions that optimize utilization, cost, and reliability.

Architecture::

    SchedulerEngine
           │
    ResourceScheduler
           │
    ResourceManager / ResourcePool
           │
    ┌──────┬─────────┬──────────┐
    CPU    GPU       Memory/IO
    └──────┴─────────┴──────────┘
           │
    PlacementPlanner → Worker Cluster
"""

from .resource_manager import ResourceManager, ResourceManagerState
from .resource_pool import ResourcePool
from .resource_tracker import ResourceTracker
from .resource_monitor import ResourceMonitor
from .resource_estimator import ResourceEstimator, EstimateResult
from .resource_predictor import ResourcePredictor, PredictionResult
from .resource_quota import ResourceQuota, QuotaLimit
from .resource_reservation import ResourceReservation, ReservationStatus
from .resource_allocator import ResourceAllocator, AllocationResult
from .resource_reclaimer import ResourceReclaimer

from .node_inventory import NodeInventory, NodeRecord
from .node_score import NodeScoringEngine, NodeScore
from .node_selector import NodeSelector, SelectionStrategy
from .placement_planner import PlacementPlanner, PlacementPlan

from .affinity import AffinityRule, AffinityType
from .anti_affinity import AntiAffinityRule
from .topology import TopologyManager, TopologyDomain

from .scheduler_policy import SchedulerPolicy, PolicyType
from .fair_share import FairShareScheduler, FairShareResult
from .priority_scheduler import PriorityScheduler
from .preemption import PreemptionScheduler, PreemptionResult
from .bin_packing import BinPackingOptimizer, PackingResult

from .auto_scaler import AutoScaler, ScalingResult
from .capacity_planner import CapacityPlanner, CapacityPlan
from .cost_optimizer import CostOptimizer, CostResult
from .gpu_scheduler import GPUScheduler
from .io_scheduler import IOScheduler

from .metrics import ResourceMetrics
from .telemetry import ResourceTelemetry
from .diagnostics import ResourceDiagnostics
from .health import ResourceHealth

__all__ = [
    # Core resource management
    "ResourceManager",
    "ResourceManagerState",
    "ResourcePool",
    "ResourceTracker",
    "ResourceMonitor",
    # Estimation & prediction
    "ResourceEstimator",
    "EstimateResult",
    "ResourcePredictor",
    "PredictionResult",
    "ResourceQuota",
    "QuotaLimit",
    "ResourceReservation",
    "ReservationStatus",
    "ResourceAllocator",
    "AllocationResult",
    "ResourceReclaimer",
    # Node management
    "NodeInventory",
    "NodeRecord",
    "NodeScoringEngine",
    "NodeScore",
    "NodeSelector",
    "SelectionStrategy",
    "PlacementPlanner",
    "PlacementPlan",
    # Affinity & topology
    "AffinityRule",
    "AffinityType",
    "AntiAffinityRule",
    "TopologyManager",
    "TopologyDomain",
    # Scheduling policies
    "SchedulerPolicy",
    "PolicyType",
    "FairShareScheduler",
    "FairShareResult",
    "PriorityScheduler",
    "PreemptionScheduler",
    "PreemptionResult",
    "BinPackingOptimizer",
    "PackingResult",
    # Elastic & cost
    "AutoScaler",
    "ScalingResult",
    "CapacityPlanner",
    "CapacityPlan",
    "CostOptimizer",
    "CostResult",
    "GPUScheduler",
    "IOScheduler",
    # Observability
    "ResourceMetrics",
    "ResourceTelemetry",
    "ResourceDiagnostics",
    "ResourceHealth",
]
