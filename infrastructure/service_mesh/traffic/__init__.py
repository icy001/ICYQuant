"""Traffic Management module for ICYQuant Service Mesh.

Provides production-grade traffic management including routing,
load balancing, deployment strategies (blue-green, canary),
resilience (retry, circuit breaker, rate limiting), and
observability.
"""

# Policies
from .policies import (
    RetryPolicy,
    TimeoutPolicy,
    CircuitPolicy,
    TrafficPolicy,
    RatePolicy,
    PolicyManager,
)

# Metrics & Telemetry & Diagnostics
from .metrics import TrafficMetrics
from .telemetry import TrafficTelemetry
from .diagnostics import TrafficDiagnostics

# Routing
from .route import (
    RouteMatchType,
    RouteDestination,
    TrafficRoute,
    RouteTable,
)
from .route_matcher import RouteMatcher
from .route_rewriter import RouteRewriter
from .virtual_service import VirtualService
from .destination_rule import (
    DestinationRule,
    DestinationRuleManager,
)

# Traffic strategies
from .traffic_split import TrafficSplit
from .weighted_router import WeightedRouter
from .load_balancer import (
    LoadBalancerStrategy,
    LoadBalancer,
)

# Deployment strategies
from .blue_green import (
    BlueGreenPhase,
    BlueGreenDeployer,
)
from .canary import (
    CanaryRule,
    CanaryRelease,
)
from .mirror import (
    MirrorPolicy,
    TrafficMirror,
)

# Resilience
from .retry import (
    RetryStrategy,
    RetryManager,
)
from .hedging import HedgeManager
from .timeout import TimeoutManager
from .circuit_breaker import (
    CircuitState,
    CircuitBreakerConfig,
    TrafficCircuitBreaker,
)
from .outlier_detection import OutlierDetector
from .rate_limiter import (
    RateLimitStrategy,
    TokenBucket,
    LeakyBucket,
    SlidingWindow,
    RateLimiter,
)
from .connection_pool import (
    ConnectionProtocol,
    PooledConnection,
    ConnectionPool,
)

# Orchestration
from .traffic_manager import TrafficManager
from .scheduler import (
    ScheduledTask,
    TrafficScheduler,
)

__all__ = [
    # Policies
    "RetryPolicy",
    "TimeoutPolicy",
    "CircuitPolicy",
    "TrafficPolicy",
    "RatePolicy",
    "PolicyManager",
    # Metrics/Telemetry/Diagnostics
    "TrafficMetrics",
    "TrafficTelemetry",
    "TrafficDiagnostics",
    # Routing
    "RouteMatchType",
    "RouteDestination",
    "TrafficRoute",
    "RouteTable",
    "RouteMatcher",
    "RouteRewriter",
    "VirtualService",
    "DestinationRule",
    "DestinationRuleManager",
    # Traffic strategies
    "TrafficSplit",
    "WeightedRouter",
    "LoadBalancerStrategy",
    "LoadBalancer",
    # Deployment
    "BlueGreenPhase",
    "BlueGreenDeployer",
    "CanaryRule",
    "CanaryRelease",
    "MirrorPolicy",
    "TrafficMirror",
    # Resilience
    "RetryStrategy",
    "RetryManager",
    "HedgeManager",
    "TimeoutManager",
    "CircuitState",
    "CircuitBreakerConfig",
    "TrafficCircuitBreaker",
    "OutlierDetector",
    "RateLimitStrategy",
    "TokenBucket",
    "LeakyBucket",
    "SlidingWindow",
    "RateLimiter",
    "ConnectionProtocol",
    "PooledConnection",
    "ConnectionPool",
    # Orchestration
    "TrafficManager",
    "ScheduledTask",
    "TrafficScheduler",
]