"""
ICYQuant Unified Market Connectivity Platform.

Commit 16 Part 1.1 — Multi-exchange connectivity with session management,
resilient connection framework, and multi-protocol support.
"""

from .market_connectivity_platform import MarketConnectivityPlatform
from .connectivity_runtime import (
    ConnectivityRuntime,
    ConnectivityRuntimeStatus,
    ConnectivityRuntimeConfig,
)
from .connectivity_manager import ConnectivityManager
from .connectivity_controller import ConnectivityController
from .connectivity_registry import (
    ConnectivityRegistry,
    RegistryEntry,
    RegistryEntryStatus,
)
from .exchange_registry import (
    ExchangeRegistry,
    ExchangeEntry,
    ExchangeStatus,
)
from .exchange_manager import ExchangeManager
from .exchange_session import (
    ExchangeSession,
    SessionState,
    SessionType,
)
from .exchange_capabilities import (
    ExchangeCapabilities,
    Capability,
    ExchangeCapabilityRegistry,
)
from .endpoint_discovery import (
    EndpointDiscovery,
    Endpoint,
    EndpointHealth,
    EndpointType,
)
from .session_pool import SessionPool, SessionPoolConfig
from .session_scheduler import SessionScheduler, SchedulePolicy
from .connection_manager import ConnectionManager
from .connection_pool import ConnectionPool, ConnectionPoolConfig
from .connection_health import ConnectionHealthMonitor, ConnectionHealth
from .heartbeat_monitor import HeartbeatMonitor, HeartbeatStatus
from .reconnect_manager import ReconnectManager, ReconnectPolicy, ReconnectState
from .failover_manager import FailoverManager, FailoverStrategy, FailoverState
from .metrics import MarketConnectivityMetrics
from .telemetry import (
    ConnectivityTelemetry,
    TelemetrySpan,
    TelemetryTrace,
)
from .diagnostics import (
    ConnectivityDiagnostics,
    DiagnosticStatus,
    DiagnosticCheck,
    ConnectivityDiagnosticReport,
)
from .health import (
    ConnectivityHealthChecker,
    ConnectivityHealthStatus,
    ProbeType,
    ComponentHealth,
    ConnectivityHealthReport,
)

__all__ = [
    "MarketConnectivityPlatform",
    "ConnectivityRuntime",
    "ConnectivityRuntimeStatus",
    "ConnectivityRuntimeConfig",
    "ConnectivityManager",
    "ConnectivityController",
    "ConnectivityRegistry",
    "RegistryEntry",
    "RegistryEntryStatus",
    "ExchangeRegistry",
    "ExchangeEntry",
    "ExchangeStatus",
    "ExchangeManager",
    "ExchangeSession",
    "SessionState",
    "SessionType",
    "ExchangeCapabilities",
    "Capability",
    "ExchangeCapabilityRegistry",
    "EndpointDiscovery",
    "Endpoint",
    "EndpointHealth",
    "EndpointType",
    "SessionPool",
    "SessionPoolConfig",
    "SessionScheduler",
    "SchedulePolicy",
    "ConnectionManager",
    "ConnectionPool",
    "ConnectionPoolConfig",
    "ConnectionHealthMonitor",
    "ConnectionHealth",
    "HeartbeatMonitor",
    "HeartbeatStatus",
    "ReconnectManager",
    "ReconnectPolicy",
    "ReconnectState",
    "FailoverManager",
    "FailoverStrategy",
    "FailoverState",
    "MarketConnectivityMetrics",
    "ConnectivityTelemetry",
    "TelemetrySpan",
    "TelemetryTrace",
    "ConnectivityDiagnostics",
    "DiagnosticStatus",
    "DiagnosticCheck",
    "ConnectivityDiagnosticReport",
    "ConnectivityHealthChecker",
    "ConnectivityHealthStatus",
    "ProbeType",
    "ComponentHealth",
    "ConnectivityHealthReport",
]
