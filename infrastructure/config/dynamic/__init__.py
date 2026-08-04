"""
Dynamic configuration platform.

Provides hot reload, atomic snapshot switching,
configuration watching, and dynamic config
management for the ICYQuant platform.

Components:
- DynamicConfigurationManager: Unified entry point
- DynamicSnapshot: Versioned, integrity-checked snapshot
- AtomicSnapshotManager: Lock-free atomic snapshot swaps
- HotReloadEngine: Full reload pipeline
- ConfigurationWatcher: File/remote watching
- ConfigurationRollback: Rollback management
- ConfigurationEventPublisher: Event publishing
- ConfigurationSubscriber: Key-prefixed subscriptions
- ConfigurationNotifier: Service routing
- ReloadScheduler: Periodic reload scheduling
- DynamicValidator: Pre-reload validation
- MetricsCollector: Prometheus metrics
"""

from .snapshot import (
    DynamicSnapshot,
    DynamicSnapshotStore,
)
from .atomic import AtomicSnapshotManager
from .reload import HotReloadEngine, ReloadResult
from .watcher import (
    FileWatcher,
    RemoteConfigWatcher,
    ConfigurationWatcher,
)
from .rollback import ConfigurationRollback, RollbackResult
from .publisher import (
    DynamicEvent,
    ConfigurationEventPublisher,
)
from .subscriber import (
    ConfigurationSubscription,
    ConfigurationSubscriber,
)
from .notifier import ConfigurationNotifier, DEFAULT_ROUTES
from .scheduler import ReloadScheduler
from .validator import DynamicValidator
from .debounce import Debounce, AsyncDebounce
from .metrics import (
    MetricsCollector,
    CounterMetric,
    GaugeMetric,
    HistogramMetric,
    create_default_metrics,
)
from .manager import DynamicConfigurationManager

__all__ = [
    # Manager
    "DynamicConfigurationManager",
    # Snapshot
    "DynamicSnapshot",
    "DynamicSnapshotStore",
    # Atomic
    "AtomicSnapshotManager",
    # Reload
    "HotReloadEngine",
    "ReloadResult",
    # Watcher
    "FileWatcher",
    "RemoteConfigWatcher",
    "ConfigurationWatcher",
    # Rollback
    "ConfigurationRollback",
    "RollbackResult",
    # Publisher
    "DynamicEvent",
    "ConfigurationEventPublisher",
    # Subscriber
    "ConfigurationSubscription",
    "ConfigurationSubscriber",
    # Notifier
    "ConfigurationNotifier",
    "DEFAULT_ROUTES",
    # Scheduler
    "ReloadScheduler",
    # Validator
    "DynamicValidator",
    # Debounce
    "Debounce",
    "AsyncDebounce",
    # Metrics
    "MetricsCollector",
    "CounterMetric",
    "GaugeMetric",
    "HistogramMetric",
    "create_default_metrics",
]
