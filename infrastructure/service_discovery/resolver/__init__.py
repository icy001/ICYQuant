"""Service discovery resolver subpackage.

Provides context, strategy, selection, load balancing, and routing
components for resolving service instances with advanced strategies
including round-robin, weighted, least-connection, least-latency,
random, and consistent-hash algorithms.
"""

from __future__ import annotations

from .least_connection import LeastConnection
from .least_latency import LeastLatency
from .round_robin import RoundRobin
from .weighted import Weighted
from .random import Random
from .consistent_hash import ConsistentHash
from .context import ResolveContext
from .strategy import ResolveStrategy, StrategyConfig
from .selector import (
    LoadBalancerSelector,
    RoundRobinLoadBalancer,
    WeightedLoadBalancer,
    LeastConnectionLoadBalancer,
    LeastLatencyLoadBalancer,
    RandomLoadBalancer,
    ConsistentHashLoadBalancer,
)
from .load_balancer import LoadBalancer
from .router import ServiceRouter
from .service_resolver import ServiceResolver
from .locality import LocalityRouter
from .version_router import VersionRouter
from .canary import CanaryRouter
from .feature_flag import FeatureFlagRouter
from .health_filter import HealthFilter
from .circuit_filter import CircuitFilter
from .cache import ResolverCache
from .metrics import ResolverMetrics
from .diagnostics import ResolverDiagnostics
from .telemetry import ResolverTelemetry
from .resolver import IntelligentServiceResolver

__all__ = [
    "LeastConnection",
    "LeastLatency",
    "RoundRobin",
    "Weighted",
    "Random",
    "ConsistentHash",
    "ResolveContext",
    "ResolveStrategy",
    "StrategyConfig",
    "LoadBalancerSelector",
    "RoundRobinLoadBalancer",
    "WeightedLoadBalancer",
    "LeastConnectionLoadBalancer",
    "LeastLatencyLoadBalancer",
    "RandomLoadBalancer",
    "ConsistentHashLoadBalancer",
    "LoadBalancer",
    "ServiceRouter",
    "ServiceResolver",
    "LocalityRouter",
    "VersionRouter",
    "CanaryRouter",
    "FeatureFlagRouter",
    "HealthFilter",
    "CircuitFilter",
    "ResolverCache",
    "ResolverMetrics",
    "ResolverDiagnostics",
    "ResolverTelemetry",
    "IntelligentServiceResolver",
]