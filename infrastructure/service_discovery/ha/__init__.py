"""High Availability subpackage for ICYQuant service discovery.

Provides fault tolerance, failover, self-healing, retry logic,
replica management, traffic draining, graceful eviction,
registry recovery, snapshotting, rebalancing, and split-brain
detection for distributed service resilience.
"""

from __future__ import annotations

from .failover import FailoverManager
from .self_healing import SelfHealingEngine
from .retry import AdaptiveRetryEngine, RetryBudget
from .replica import ReplicaManager
from .traffic_drain import TrafficDrain
from .eviction import GracefulEviction
from .recovery import RegistryRecovery
from .snapshot import RegistrySnapshot
from .rebalancer import ClusterRebalancer
from .split_brain import SplitBrainDetector
from .registry_failover import MultiRegistryFailover
from .coordinator import HAController
from .state_machine import HAState, HAStateMachine
from .scheduler import HAScheduler
from .policies import HAPolicy, HAPolicyManager
from .metrics import HAMetrics
from .telemetry import HATelemetry
from .audit import HAAudit
from .diagnostics import HADiagnostics
from .health import HAHealth

__all__ = [
    "FailoverManager",
    "SelfHealingEngine",
    "AdaptiveRetryEngine",
    "RetryBudget",
    "ReplicaManager",
    "TrafficDrain",
    "GracefulEviction",
    "RegistryRecovery",
    "RegistrySnapshot",
    "ClusterRebalancer",
    "SplitBrainDetector",
    "MultiRegistryFailover",
    "HAController",
    "HAState",
    "HAStateMachine",
    "HAScheduler",
    "HAPolicy",
    "HAPolicyManager",
    "HAMetrics",
    "HATelemetry",
    "HAAudit",
    "HADiagnostics",
    "HAHealth",
]