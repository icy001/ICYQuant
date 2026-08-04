from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
import logging


@dataclass
class PluginContext:
    """Context passed to plugins for accessing platform services.

    Plugins receive this context and must NOT access
    platform internals directly.
    """

    plugin_id: str
    config: dict = field(default_factory=dict)
    logger: Optional[logging.Logger] = None
    eventbus: Any = None
    metrics: Any = None
    secrets: Any = None
    crypto: Any = None
    storage: Any = None
    scheduler: Any = None
    health: Any = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.logger is None:
            self.logger = logging.getLogger(f"plugin.{self.plugin_id}")

    def get_config(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set_config(self, key: str, value: Any) -> None:
        self.config[key] = value

    def get_secret(self, name: str) -> Any:
        """Delegate secret access to the injected secrets service."""
        if self.secrets is None:
            return None
        getter = getattr(self.secrets, "get", None)
        if callable(getter):
            return getter(name)
        try:
            return self.secrets[name]
        except (TypeError, KeyError, IndexError):
            return None

    def log(self, level: int, msg: str, **kwargs: Any) -> None:
        if self.logger is not None:
            self.logger.log(level, msg, **kwargs)

    def emit(self, event_type: str, data: dict) -> Any:
        """Delegate event publication to the injected eventbus."""
        if self.eventbus is None:
            return None
        publish = getattr(self.eventbus, "publish", None)
        if not callable(publish):
            return None
        return publish(event_type, data)

    def record_metric(self, name: str, value: float, tags: dict = None) -> None:
        if self.metrics is None:
            return
        record = getattr(self.metrics, "record", None)
        if not callable(record):
            return
        try:
            record(name, value, tags or {})
        except TypeError:
            # Metrics service may not accept a tags argument.
            record(name, value)

    def to_dict(self) -> dict:
        return {
            "plugin_id": self.plugin_id,
            "config": dict(self.config),
            "metadata": dict(self.metadata),
            "has_eventbus": self.eventbus is not None,
            "has_metrics": self.metrics is not None,
            "has_secrets": self.secrets is not None,
            "has_crypto": self.crypto is not None,
            "has_storage": self.storage is not None,
            "has_scheduler": self.scheduler is not None,
            "has_health": self.health is not None,
        }

    @classmethod
    def create(cls, plugin_id: str, **services: Any) -> PluginContext:
        return cls(plugin_id=plugin_id, **services)


class ContextBuilder:
    """Builder for plugin contexts."""

    def __init__(self, plugin_id: str) -> None:
        self._plugin_id = plugin_id
        self._config: dict = {}
        self._logger: Optional[logging.Logger] = None
        self._eventbus: Any = None
        self._metrics: Any = None
        self._secrets: Any = None
        self._crypto: Any = None
        self._storage: Any = None
        self._scheduler: Any = None

    def with_config(self, config: dict) -> ContextBuilder:
        self._config = dict(config)
        return self

    def with_logger(self, logger: logging.Logger) -> ContextBuilder:
        self._logger = logger
        return self

    def with_eventbus(self, eventbus: Any) -> ContextBuilder:
        self._eventbus = eventbus
        return self

    def with_metrics(self, metrics: Any) -> ContextBuilder:
        self._metrics = metrics
        return self

    def with_secrets(self, secrets: Any) -> ContextBuilder:
        self._secrets = secrets
        return self

    def with_crypto(self, crypto: Any) -> ContextBuilder:
        self._crypto = crypto
        return self

    def with_storage(self, storage: Any) -> ContextBuilder:
        self._storage = storage
        return self

    def with_scheduler(self, scheduler: Any) -> ContextBuilder:
        self._scheduler = scheduler
        return self

    def build(self) -> PluginContext:
        return PluginContext(
            plugin_id=self._plugin_id,
            config=self._config,
            logger=self._logger,
            eventbus=self._eventbus,
            metrics=self._metrics,
            secrets=self._secrets,
            crypto=self._crypto,
            storage=self._storage,
            scheduler=self._scheduler,
        )
