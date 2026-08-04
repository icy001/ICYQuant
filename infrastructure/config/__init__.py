"""
Configuration platform.

Provides comprehensive configuration management
for the ICYQuant platform, including multi-source
loading, validation, caching, and immutable snapshots.

Components:
- ConfigurationManager: Unified entry point
- ConfigurationRegistry: Registry with immutable snapshots
- ConfigurationCache: TTL-based cache with LRU eviction
- ConfigurationValidator: Validation framework
- ConfigurationLoader: Multi-format loader (YAML/JSON/TOML/ENV)
- ConfigurationHealth: Health monitoring
- ConfigurationItem / ConfigurationSnapshot: Data models
- ConfigurationPlatformConfig: Platform configuration

Design:
- Immutable Snapshot Pattern: Business threads read
  complete, unmodifiable snapshots; updates create
  new snapshots and perform atomic switches.

- Multi-Source Priority: CLI > ENV > SECRETS > REMOTE > FILE > DEFAULT

Usage:
    from infrastructure.config import ConfigurationManager

    manager = ConfigurationManager()
    manager.set("server.port", 8080)
    port = manager.get("server.port")  # 8080
    snapshot = manager.get_snapshot()
"""

# Config
from .config import ConfigurationPlatformConfig

# Constants
from .constants import (
    DEFAULT_CACHE_MAX_SIZE,
    DEFAULT_CACHE_TTL,
    DEFAULT_CONFIG_VERSION,
    DEFAULT_ENVIRONMENT,
    DEFAULT_LOADER,
    DEFAULT_RELOAD_INTERVAL,
    DEFAULT_VALIDATION_LEVEL,
    ConfigSource,
    Environment,
    LoaderType,
    ValidationLevel,
)

# Exceptions
from .exceptions import (
    ConfigCacheError,
    ConfigDependencyError,
    ConfigError,
    ConfigLoadError,
    ConfigNotFoundError,
    ConfigParseError,
    ConfigRangeError,
    ConfigReloadError,
    ConfigSnapshotError,
    ConfigTypeError,
    ConfigValidationError,
)

# Models
from .models import (
    ConfigurationItem,
    ConfigurationSnapshot,
    ValidationResult,
)

# Cache
from .cache import ConfigurationCache

# Registry
from .registry import ConfigurationRegistry

# Validator
from .validator import (
    ChoiceRule,
    ConfigurationValidator,
    DependencyRule,
    RangeRule,
    SchemaRule,
    TypeRule,
    ValidationRule,
)

# Loader
from .loader import (
    ConfigurationLoader,
    EnvLoader,
    JSONLoader,
    LoaderFactory,
    MultiSourceLoader,
    TOMLLoader,
    YAMLLoader,
)

# Manager
from .manager import ConfigurationManager

# Health
from .health import ConfigurationHealth

# Utils
from .import utils

# ── Part 1.2: Multi-Source Loader ──

# Priority
from .priority import ConfigurationPriority, MergeStrategy

# Sources
from .sources import (
    CLISource,
    ConfigurationSource,
    DefaultsSource,
    EnvironmentSource,
    JSONSource,
    RemoteSource,
    SecretsSource,
    TOMLSource,
    YAMLSource,
)

# Merger
from .merger import ConfigurationMerger

# Resolver
from .resolver import ConfigurationResolver

# Snapshot (Part 1.2)
from .snapshot import ConfigurationSnapshot, SnapshotStore

# Events
from .events import (
    ConfigurationEvent,
    ConfigurationEventBus,
    ConfigurationEventData,
)

# Cache (Part 1.2 - SnapshotCache)
from .cache import SnapshotCache

# Loader (Part 1.2 - Unified)
from .loader import UnifiedConfigurationLoader

# ── Part 1.3: Environment Management ──

# Environment subpackage
from .environment import (
    BASE_PROFILE,
    DEVELOPMENT_PROFILE,
    PRODUCTION_PROFILE,
    STAGING_PROFILE,
    STANDARD_PROFILES,
    TESTING_PROFILE,
    ConfigurationOverlay,
    EnvironmentDetector,
    EnvironmentManager,
    EnvironmentProfile,
    EnvironmentRegistry,
    EnvironmentValidator,
    OverlayResult,
    ProfileInheritance,
    ProfileLoader,
    TenantProfile,
    get_profile,
    list_profiles,
)

# Top-level environment files
from .diagnostics import EnvironmentDiagnostics
from .discovery import EnvironmentDiscovery
from .dotenv import DotEnvLoader
from .metadata import EnvironmentMetadata
from .profiles import ProfileConfiguration

# ── Part 1.4: Dynamic Configuration Platform ──

# Dynamic subpackage
from .dynamic import (
    DynamicConfigurationManager,
    DynamicSnapshot,
    DynamicSnapshotStore,
    AtomicSnapshotManager,
    HotReloadEngine,
    ReloadResult,
    FileWatcher,
    RemoteConfigWatcher,
    ConfigurationWatcher,
    ConfigurationRollback,
    RollbackResult,
    DynamicEvent,
    ConfigurationEventPublisher,
    ConfigurationSubscription,
    ConfigurationSubscriber,
    ConfigurationNotifier,
    DEFAULT_ROUTES,
    ReloadScheduler,
    DynamicValidator,
    Debounce,
    AsyncDebounce,
    MetricsCollector,
    CounterMetric,
    GaugeMetric,
    HistogramMetric,
    create_default_metrics,
)

# Top-level dynamic files
from .version import (
    ConfigurationVersion,
    ConfigurationVersionManager,
)
from .history import (
    ConfigChangeEntry,
    ConfigurationHistory,
)
from .transaction import (
    TransactionStatus,
    ConfigurationTransaction,
    ConfigurationTransactionManager,
    TransactionResult,
)
from .audit import (
    AuditEntry,
    ConfigurationAudit,
)

# ── Part 1.5: Bootstrap & Integration ──

from .bootstrap import ConfigurationBootstrap
from .service import ConfigurationService
from .container import DIContainer, create_default_container
from .lifecycle import ConfigurationLifecycle, LifecycleState
from .startup import ConfigurationStartup, StartupPhase, StartupResult
from .shutdown import GracefulShutdown, ShutdownPhase, ShutdownResult
from .recovery import AutomaticRecovery, RecoveryState, RecoveryEvent
from .protection import ConfigurationProtection, CircuitState
from .integrity import SnapshotIntegrity, IntegrityResult
from .scheduler import ConfigurationScheduler, ScheduledTask
from .monitoring import ConfigurationMonitor
from .telemetry import ConfigurationTelemetry, TraceSpan
from .health import PlatformHealthCheck
from .diagnostics import ConfigurationDiagnostics

__all__ = [
    # Config
    "ConfigurationPlatformConfig",
    # Constants
    "ConfigSource",
    "Environment",
    "LoaderType",
    "ValidationLevel",
    "DEFAULT_ENVIRONMENT",
    "DEFAULT_LOADER",
    "DEFAULT_CACHE_TTL",
    "DEFAULT_CACHE_MAX_SIZE",
    "DEFAULT_CONFIG_VERSION",
    "DEFAULT_VALIDATION_LEVEL",
    "DEFAULT_RELOAD_INTERVAL",
    # Models
    "ConfigurationItem",
    "ConfigurationSnapshot",
    "ValidationResult",
    # Cache
    "ConfigurationCache",
    # Registry
    "ConfigurationRegistry",
    # Validator
    "ConfigurationValidator",
    "ValidationRule",
    "TypeRule",
    "RangeRule",
    "DependencyRule",
    "SchemaRule",
    "ChoiceRule",
    # Loader
    "ConfigurationLoader",
    "YAMLLoader",
    "JSONLoader",
    "TOMLLoader",
    "EnvLoader",
    "LoaderFactory",
    "MultiSourceLoader",
    # Manager
    "ConfigurationManager",
    # Health
    "ConfigurationHealth",
    # Utils
    "utils",
    # Part 1.2 - Priority
    "ConfigurationPriority",
    "MergeStrategy",
    # Part 1.2 - Sources
    "ConfigurationSource",
    "YAMLSource",
    "JSONSource",
    "TOMLSource",
    "EnvironmentSource",
    "CLISource",
    "RemoteSource",
    "SecretsSource",
    "DefaultsSource",
    # Part 1.2 - Merger
    "ConfigurationMerger",
    # Part 1.2 - Resolver
    "ConfigurationResolver",
    # Part 1.2 - Snapshot (updated)
    "SnapshotStore",
    # Part 1.2 - Events
    "ConfigurationEvent",
    "ConfigurationEventData",
    "ConfigurationEventBus",
    # Part 1.2 - Cache (updated)
    "SnapshotCache",
    # Part 1.2 - Unified Loader
    "UnifiedConfigurationLoader",
    # Part 1.3 - Environment Management
    "EnvironmentProfile",
    "TenantProfile",
    "OverlayResult",
    "BASE_PROFILE",
    "DEVELOPMENT_PROFILE",
    "TESTING_PROFILE",
    "STAGING_PROFILE",
    "PRODUCTION_PROFILE",
    "STANDARD_PROFILES",
    "get_profile",
    "list_profiles",
    "EnvironmentRegistry",
    "EnvironmentDetector",
    "ProfileInheritance",
    "ConfigurationOverlay",
    "ProfileLoader",
    "EnvironmentValidator",
    "EnvironmentManager",
    "EnvironmentDiscovery",
    "EnvironmentMetadata",
    "EnvironmentDiagnostics",
    "DotEnvLoader",
    "ProfileConfiguration",
    # Part 1.4 - Dynamic Configuration Platform
    "DynamicConfigurationManager",
    "DynamicSnapshot",
    "DynamicSnapshotStore",
    "AtomicSnapshotManager",
    "HotReloadEngine",
    "ReloadResult",
    "FileWatcher",
    "RemoteConfigWatcher",
    "ConfigurationWatcher",
    "ConfigurationRollback",
    "RollbackResult",
    "DynamicEvent",
    "ConfigurationEventPublisher",
    "ConfigurationSubscription",
    "ConfigurationSubscriber",
    "ConfigurationNotifier",
    "DEFAULT_ROUTES",
    "ReloadScheduler",
    "DynamicValidator",
    "Debounce",
    "AsyncDebounce",
    "MetricsCollector",
    "CounterMetric",
    "GaugeMetric",
    "HistogramMetric",
    "create_default_metrics",
    # Part 1.4 - Version/History/Transaction/Audit
    "ConfigurationVersion",
    "ConfigurationVersionManager",
    "ConfigChangeEntry",
    "ConfigurationHistory",
    "TransactionStatus",
    "ConfigurationTransaction",
    "ConfigurationTransactionManager",
    "TransactionResult",
    "AuditEntry",
    "ConfigurationAudit",
    # Part 1.5 - Bootstrap & Integration
    "ConfigurationBootstrap",
    "ConfigurationService",
    "DIContainer",
    "create_default_container",
    "ConfigurationLifecycle",
    "LifecycleState",
    "ConfigurationStartup",
    "StartupPhase",
    "StartupResult",
    "GracefulShutdown",
    "ShutdownPhase",
    "ShutdownResult",
    "AutomaticRecovery",
    "RecoveryState",
    "RecoveryEvent",
    "ConfigurationProtection",
    "CircuitState",
    "SnapshotIntegrity",
    "IntegrityResult",
    "ConfigurationScheduler",
    "ScheduledTask",
    "ConfigurationMonitor",
    "ConfigurationTelemetry",
    "TraceSpan",
    "PlatformHealthCheck",
    "ConfigurationDiagnostics",
    # Exceptions
    "ConfigError",
    "ConfigNotFoundError",
    "ConfigValidationError",
    "ConfigLoadError",
    "ConfigParseError",
    "ConfigTypeError",
    "ConfigRangeError",
    "ConfigDependencyError",
    "ConfigCacheError",
    "ConfigSnapshotError",
    "ConfigReloadError",
]
