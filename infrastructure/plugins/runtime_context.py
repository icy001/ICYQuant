from __future__ import annotations

import logging
from typing import Any, Dict, Optional


class RuntimeContext:
    """Unified runtime context for plugin access to platform capabilities.

    Plugins access ALL platform capabilities through this context ONLY.
    It provides a stable, restricted API surface that prevents plugins
    from directly depending on internal framework components.

    Attributes:
        configuration: The configuration platform instance.
        eventbus: The event bus for publishing and subscribing to events.
        logger: A dedicated logger for the plugin.
        metrics: The metrics collector for recording measurements.
        tracing: The tracing system for distributed tracing.
        secrets: The secrets manager for secure credential access.
        crypto: The crypto engine for signing and verification.
        feature_flags: The feature flags service for rollout control.
        plugin_id: The unique identifier of the owning plugin.
    """

    def __init__(
        self,
        plugin_id: str,
        configuration: Any = None,
        eventbus: Any = None,
        logger: Optional[logging.Logger] = None,
        metrics: Any = None,
        tracing: Any = None,
        secrets: Any = None,
        crypto: Any = None,
        feature_flags: Any = None,
    ) -> None:
        self.plugin_id = plugin_id
        self.configuration = configuration
        self.eventbus = eventbus
        self.logger = logger or logging.getLogger(f"plugin.{plugin_id}")
        self.metrics = metrics
        self.tracing = tracing
        self.secrets = secrets
        self.crypto = crypto
        self.feature_flags = feature_flags

    def get_config(self, key: str, default: Any = None) -> Any:
        """Retrieve a configuration value by key.

        Delegates to the configuration platform if available,
        otherwise falls back to the default.

        Args:
            key: The configuration key to look up.
            default: The fallback value if key is not found.

        Returns:
            The configuration value or *default*.
        """
        if self.configuration is None:
            return default
        getter = getattr(self.configuration, "get_value", None)
        if callable(getter):
            return getter(self.plugin_id, key, default)
        get_config = getattr(self.configuration, "get_config", None)
        if callable(get_config):
            config = get_config(self.plugin_id)
            if config is not None:
                return config.get(key, default)
        return default

    def get_secret(self, name: str) -> Any:
        """Retrieve a secret value by name.

        Delegates to the secrets manager if available.

        Args:
            name: The secret name to look up.

        Returns:
            The secret value, or None if not found or secrets
            manager is unavailable.
        """
        if self.secrets is None:
            return None
        getter = getattr(self.secrets, "get", None)
        if callable(getter):
            return getter(name)
        try:
            return self.secrets[name]
        except (TypeError, KeyError, IndexError):
            return None

    def emit(self, event_type: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Publish an event through the event bus.

        Args:
            event_type: The event type identifier.
            data: Optional event payload.
        """
        if self.eventbus is None:
            return
        publish = getattr(self.eventbus, "publish", None)
        if not callable(publish):
            return
        try:
            from .events import PluginEvent, PluginEventBus

            if isinstance(self.eventbus, PluginEventBus):
                event = PluginEvent(
                    event_type=event_type,
                    plugin_id=self.plugin_id,
                    data=data or {},
                )
                publish(event)
            else:
                publish(event_type, data or {})
        except Exception as e:
            self.logger.warning(
                "Failed to emit event '%s': %s", event_type, e
            )

    def log(self, level: str, message: str) -> None:
        """Log a message at the specified level.

        Args:
            level: One of 'debug', 'info', 'warning', 'error', 'critical'.
            message: The log message.
        """
        level_map: Dict[str, int] = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
        }
        numeric_level = level_map.get(level.lower(), logging.INFO)
        self.logger.log(numeric_level, message)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the context metadata to a dictionary.

        Returns:
            A dictionary describing the context state and
            available services.
        """
        return {
            "plugin_id": self.plugin_id,
            "has_configuration": self.configuration is not None,
            "has_eventbus": self.eventbus is not None,
            "has_metrics": self.metrics is not None,
            "has_tracing": self.tracing is not None,
            "has_secrets": self.secrets is not None,
            "has_crypto": self.crypto is not None,
            "has_feature_flags": self.feature_flags is not None,
        }