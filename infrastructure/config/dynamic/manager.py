"""
Dynamic configuration manager.

Unified entry point for the dynamic configuration platform.
Coordinates all dynamic components:
- Hot reload engine
- Configuration watcher
- Rollback manager
- Event publisher
- Subscription manager
- Scheduled reload
- Metrics collection

Runtime Flow:
    Watcher → Configuration Changed → Debounce → Reload
    → Load → Merge → Validate → Build Snapshot
    → Atomic Swap → Publish Event → Subscribers

Rollback Flow:
    Current Snapshot → Rollback Request → History
    → Restore Snapshot → Atomic Swap → Notify Services
"""

from __future__ import annotations

import asyncio
import time
import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

from .snapshot import DynamicSnapshot, DynamicSnapshotStore
from .atomic import AtomicSnapshotManager
from .reload import HotReloadEngine, ReloadResult
from .watcher import ConfigurationWatcher
from .rollback import ConfigurationRollback, RollbackResult
from .publisher import ConfigurationEventPublisher, DynamicEvent
from .subscriber import ConfigurationSubscriber
from .notifier import ConfigurationNotifier
from .scheduler import ReloadScheduler
from .validator import DynamicValidator
from .metrics import MetricsCollector, create_default_metrics


class DynamicConfigurationManager:
    """
    Unified dynamic configuration manager.

    Provides a single entry point for all dynamic
    configuration operations: reload, rollback,
    subscription, and monitoring.

    Usage:
        manager = DynamicConfigurationManager()

        # Register sources
        manager.add_source("yaml", load_yaml, priority=30)
        manager.add_source("env", load_env, priority=80)

        # Start watching
        manager.watch_files(["config.yaml"])
        manager.start()

        # Manual reload
        result = manager.reload(operator="admin")

        # Subscribe to changes
        manager.subscribe(
            callback=on_change,
            prefixes={"oms.", "risk."},
        )

        # Rollback
        manager.rollback_to(version=5)
    """

    def __init__(
        self,
        snapshot_store: Optional[DynamicSnapshotStore] = None,
        metrics: Optional[MetricsCollector] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        """
        Initialize dynamic configuration manager.

        Args:
            snapshot_store: Custom snapshot store.
            metrics: Custom metrics collector.
            loop: Event loop for async operations.
        """
        self._loop = loop or asyncio.get_event_loop()

        # Core components
        self._snapshot_store = snapshot_store or DynamicSnapshotStore()
        self._atomic_manager = AtomicSnapshotManager(self._snapshot_store)
        self._reload_engine = HotReloadEngine(self._atomic_manager)
        self._watcher = ConfigurationWatcher(loop=self._loop)
        self._rollback_manager = ConfigurationRollback(self._snapshot_store)
        self._publisher = ConfigurationEventPublisher()
        self._subscriber = ConfigurationSubscriber(self._publisher)
        self._notifier = ConfigurationNotifier(self._publisher)
        self._scheduler = ReloadScheduler(
            reload_func=self.reload,
            loop=self._loop,
        )
        self._validator = DynamicValidator()

        # Metrics
        self._metrics = metrics or create_default_metrics()

        # Wire up watcher
        self._watcher.on_any_change(self._on_watcher_change)

        # Wire up reload engine
        self._reload_engine.add_post_hook(self._on_reload_complete)

        # State
        self._started = False
        self._lock = threading.RLock()

    # ── Properties ──

    @property
    def snapshot_store(
        self,
    ) -> DynamicSnapshotStore:
        return self._snapshot_store

    @property
    def atomic_manager(
        self,
    ) -> AtomicSnapshotManager:
        return self._atomic_manager

    @property
    def reload_engine(
        self,
    ) -> HotReloadEngine:
        return self._reload_engine

    @property
    def watcher(
        self,
    ) -> ConfigurationWatcher:
        return self._watcher

    @property
    def rollback_manager(
        self,
    ) -> ConfigurationRollback:
        return self._rollback_manager

    @property
    def publisher(
        self,
    ) -> ConfigurationEventPublisher:
        return self._publisher

    @property
    def subscriber(
        self,
    ) -> ConfigurationSubscriber:
        return self._subscriber

    @property
    def notifier(
        self,
    ) -> ConfigurationNotifier:
        return self._notifier

    @property
    def scheduler(
        self,
    ) -> ReloadScheduler:
        return self._scheduler

    @property
    def validator(
        self,
    ) -> DynamicValidator:
        return self._validator

    @property
    def metrics(
        self,
    ) -> MetricsCollector:
        return self._metrics

    @property
    def current_snapshot(
        self,
    ) -> Optional[DynamicSnapshot]:
        """Get current active snapshot."""
        return self._atomic_manager.current

    # ── Source Management ──

    def add_source(
        self,
        name: str,
        loader_func: Callable,
        priority: int = 50,
    ) -> None:
        """Register a configuration source."""
        self._reload_engine.add_loader(name, loader_func, priority)

    def add_file_source(
        self,
        path: str,
        priority: int = 30,
    ) -> None:
        """Register a file source with auto-loading."""
        def _load_file():
            import yaml
            import json
            import os

            ext = os.path.splitext(path)[1].lower()
            try:
                with open(path, "r") as f:
                    if ext in (".yaml", ".yml"):
                        return yaml.safe_load(f) or {}
                    elif ext == ".json":
                        return json.load(f)
                    elif ext == ".toml":
                        import tomllib
                        return tomllib.loads(f.read())
            except Exception:
                pass
            return {}

        self.add_source(name=path, loader_func=_load_file, priority=priority)

    # ── Watcher Management ──

    def watch_files(
        self,
        paths: List[str],
    ) -> None:
        """Watch specific files for changes."""
        for path in paths:
            self._watcher.add_file(path)

    def watch_directory(
        self,
        directory: str,
        patterns: Optional[List[str]] = None,
    ) -> None:
        """Watch a directory for configuration changes."""
        self._watcher.add_directory(directory, patterns)

    def watch_env_vars(
        self,
        var_names: List[str],
    ) -> None:
        """Watch environment variables."""
        self._watcher.watch_env_vars(var_names)

    # ── Lifecycle ──

    def start(
        self,
        enable_watcher: bool = True,
        enable_scheduler: bool = False,
        interval: float = 30.0,
    ) -> None:
        """
        Start the dynamic configuration system.

        Args:
            enable_watcher: Enable file watching.
            enable_scheduler: Enable scheduled reload.
            interval: Scheduler interval.
        """
        with self._lock:
            if self._started:
                return

            if enable_watcher:
                self._watcher.start()

            if enable_scheduler:
                self._scheduler.interval = interval
                self._scheduler.start()

            self._started = True

    def stop(
        self,
    ) -> None:
        """Stop the dynamic configuration system."""
        with self._lock:
            self._watcher.stop()
            self._scheduler.stop()
            self._started = False

    # ── Reload ──

    def reload(
        self,
        operator: str = "system",
        reason: str = "manual reload",
        force: bool = False,
    ) -> ReloadResult:
        """
        Trigger a configuration reload.

        Args:
            operator: Who triggered the reload.
            reason: Reason for the reload.
            force: Force reload even if unchanged.

        Returns:
            ReloadResult with status.
        """
        start = time.time()
        self._metrics.inc_counter("icyquant_config_reload_total")

        result = self._reload_engine.reload(
            operator=operator,
            reason=reason,
            force=force,
        )

        duration = time.time() - start
        self._metrics.observe_histogram(
            "icyquant_config_reload_duration_seconds", duration
        )

        if result.success:
            self._metrics.inc_counter("icyquant_config_reload_success_total")
            self._metrics.set_gauge(
                "icyquant_config_snapshot_version",
                result.new_version or 0,
            )
        else:
            self._metrics.inc_counter("icyquant_config_reload_failure_total")

        return result

    def _on_reload_complete(
        self,
        snapshot: DynamicSnapshot,
    ) -> None:
        """Handle reload completion."""
        history = self._snapshot_store.get_history()
        prev_snapshot = history[-1] if history else None
        changed_keys = []
        if prev_snapshot:
            changed_keys = prev_snapshot.diff_keys(snapshot)
        self._publisher.publish_snapshot_activated(
            version=snapshot.version,
            changed_keys=changed_keys,
        )

    def _on_watcher_change(
        self,
        changes: Any,
    ) -> None:
        """Handle watcher-detected changes."""
        self.reload(
            operator="watcher",
            reason=f"auto-reload: {changes}",
        )

    # ── Rollback ──

    def rollback_to(
        self,
        version: int,
        operator: str = "admin",
        reason: str = "manual rollback",
    ) -> Optional[RollbackResult]:
        """
        Rollback to a specific version.

        Args:
            version: Target version.
            operator: Who triggered the rollback.
            reason: Reason for rollback.

        Returns:
            RollbackResult or None.
        """
        result = self._rollback_manager.rollback_to(
            version=version,
            operator=operator,
            reason=reason,
        )

        if result and result.success:
            self._publisher.publish_rollback(
                from_version=result.from_version,
                to_version=result.to_version,
            )
            self._metrics.set_gauge(
                "icyquant_config_snapshot_version",
                result.to_version,
            )

        return result

    def rollback_steps(
        self,
        steps: int = 1,
        operator: str = "admin",
        reason: str = "step rollback",
    ) -> Optional[RollbackResult]:
        """Rollback N steps back."""
        return self._rollback_manager.rollback_steps(
            steps=steps,
            operator=operator,
            reason=reason,
        )

    def verify_rollback_target(
        self,
        version: int,
    ) -> Dict[str, Any]:
        """Verify a rollback target."""
        return self._rollback_manager.verify_rollback_target(version)

    # ── Subscription ──

    def subscribe(
        self,
        callback: Callable,
        subscribed_keys: Optional[Set[str]] = None,
        subscribed_prefixes: Optional[Set[str]] = None,
        subscriber_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Subscribe to configuration changes.

        Args:
            callback: Callback function(event_type, event_data).
            subscribed_keys: Specific keys to watch.
            subscribed_prefixes: Key prefixes to watch.
            subscriber_id: Unique ID (auto-generated if None).
            metadata: Subscription metadata.

        Returns:
            Subscription ID.
        """
        sub_id = self._subscriber.subscribe(
            callback=lambda e, d: callback(e, d),
            subscribed_keys=subscribed_keys,
            subscribed_prefixes=subscribed_prefixes,
            subscriber_id=subscriber_id,
            metadata=metadata,
        )
        self._metrics.set_gauge(
            "icyquant_config_subscriber_total",
            self._subscriber.subscriber_count(),
        )
        return sub_id

    def unsubscribe(
        self,
        subscriber_id: str,
    ) -> bool:
        """Remove a subscription."""
        result = self._subscriber.unsubscribe(subscriber_id)
        self._metrics.set_gauge(
            "icyquant_config_subscriber_total",
            self._subscriber.subscriber_count(),
        )
        return result

    # ── Notification ──

    def notify(
        self,
        keys: List[str],
        data: Optional[Dict[str, Any]] = None,
        source: str = "manual",
    ) -> Dict[str, List[str]]:
        """
        Notify services of configuration changes.

        Args:
            keys: Changed configuration keys.
            data: Change data.
            source: Change source.

        Returns:
            Delivery log.
        """
        return self._notifier.notify(
            event_type=DynamicEvent.CONFIG_CHANGED,
            keys=keys,
            data=data,
            source=source,
        )

    # ── Validation ──

    def add_validation_rule(
        self,
        rule_type: str,
        **kwargs: Any,
    ) -> None:
        """
        Add a validation rule.

        Args:
            rule_type: Rule type (required_key, type_check, range_check, etc.).
            **kwargs: Rule parameters.
        """
        if rule_type == "required_key":
            self._validator.add_required_key(**kwargs)
        elif rule_type == "type_check":
            self._validator.add_type_check(**kwargs)
        elif rule_type == "range_check":
            self._validator.add_range_check(**kwargs)
        elif rule_type == "pattern_check":
            self._validator.add_pattern_check(**kwargs)
        elif rule_type == "dependency":
            self._validator.add_dependency(**kwargs)
        elif rule_type == "custom":
            self._validator.add_validator(**kwargs)

    # ── Status ──

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """Get manager status."""
        snapshot = self.current_snapshot
        return {
            "started": self._started,
            "current_version": snapshot.version if snapshot else 0,
            "current_checksum": snapshot.checksum if snapshot else None,
            "environment": snapshot.environment if snapshot else None,
            "reload_stats": self._reload_engine.reload_stats,
            "subscriber_count": self._subscriber.subscriber_count(),
            "scheduler_stats": self._scheduler.stats,
            "store_stats": self._snapshot_store.get_stats(),
            "publisher_stats": self._publisher.get_stats(),
        }

    def get_metrics(
        self,
    ) -> Dict[str, Any]:
        """Get all collected metrics."""
        return self._metrics.get_all_metrics()

    def get_prometheus_metrics(
        self,
    ) -> str:
        """Get metrics in Prometheus format."""
        return self._metrics.get_prometheus_format()
