"""
Configuration notifier.

Manages targeted delivery of configuration change
events to registered service components. Routes
events based on key prefixes to the appropriate
subsystem.

Routes:
- oms.* → OMS Engine
- risk.* → Risk Engine
- strategy.* → Strategy Engine
- execution.* → Execution Engine
- gateway.* → Gateway
- monitoring.* → Monitoring
- system.* → System Services
"""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

from .publisher import ConfigurationEventPublisher, DynamicEvent


# Default routing table
DEFAULT_ROUTES = {
    "oms": "oms-engine",
    "risk": "risk-engine",
    "strategy": "strategy-engine",
    "execution": "execution-engine",
    "gateway": "gateway",
    "monitoring": "monitoring",
    "system": "system-services",
    "database": "database-service",
    "cache": "cache-service",
}


class ConfigurationNotifier:
    """
    Configuration change notifier.

    Routes configuration change events to the
    appropriate service components based on
    key prefix matching.

    Usage:
        notifier = ConfigurationNotifier()

        # Register a service
        notifier.register_service("oms-engine", on_oms_change)

        # Notify (routing based on key prefix)
        notifier.notify(
            event_type=DynamicEvent.CONFIG_CHANGED,
            keys=["oms.order_timeout", "risk.max_position"],
            data={...},
        )
    """

    def __init__(
        self,
        publisher: Optional[ConfigurationEventPublisher] = None,
    ) -> None:
        """
        Initialize notifier.

        Args:
            publisher: Event publisher.
        """
        self._publisher = publisher or ConfigurationEventPublisher()
        self._services: Dict[str, ServiceRegistration] = {}
        self._routes: Dict[str, str] = dict(DEFAULT_ROUTES)
        self._notification_log: List[Dict[str, Any]] = []
        self._max_log_size = 500
        self._lock = threading.Lock()

    @property
    def routes(
        self,
    ) -> Dict[str, str]:
        """Get current routing table."""
        return dict(self._routes)

    def register_service(
        self,
        service_id: str,
        callback: Callable,
        key_prefixes: Optional[Set[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Register a service for configuration notifications.

        Args:
            service_id: Unique service identifier.
            callback: Callback function.
            key_prefixes: Key prefixes this service is interested in.
            metadata: Service metadata.
        """
        self._services[service_id] = ServiceRegistration(
            service_id=service_id,
            callback=callback,
            key_prefixes=key_prefixes,
            metadata=metadata or {},
            registered_at=datetime.utcnow(),
        )

    def unregister_service(
        self,
        service_id: str,
    ) -> bool:
        """
        Unregister a service.

        Args:
            service_id: Service to unregister.

        Returns:
            True if removed.
        """
        with self._lock:
            return self._services.pop(service_id, None) is not None

    def add_route(
        self,
        key_prefix: str,
        service_id: str,
    ) -> None:
        """
        Add a routing rule.

        Args:
            key_prefix: Key prefix to route.
            service_id: Target service.
        """
        self._routes[key_prefix] = service_id

    def remove_route(
        self,
        key_prefix: str,
    ) -> bool:
        """Remove a routing rule."""
        return self._routes.pop(key_prefix, None) is not None

    def notify(
        self,
        event_type: DynamicEvent,
        keys: Optional[List[str]] = None,
        data: Optional[Dict[str, Any]] = None,
        source: str = "system",
    ) -> Dict[str, List[str]]:
        """
        Notify relevant services of configuration changes.

        Routes each key to the appropriate service based
        on the routing table.

        Args:
            event_type: Event type.
            keys: Changed configuration keys.
            data: Event data.
            source: Event source.

        Returns:
            Dict mapping service_id to list of keys delivered.
        """
        keys = keys or []
        delivery_log: Dict[str, List[str]] = {}

        # Group keys by target service
        service_keys: Dict[str, List[str]] = {}
        unmatched_keys = list(keys)

        for key in keys:
            target_service = self._route_key(key)
            if target_service:
                if target_service not in service_keys:
                    service_keys[target_service] = []
                service_keys[target_service].append(key)
                if key in unmatched_keys:
                    unmatched_keys.remove(key)

        # Also check services with custom key prefixes
        for service_id, registration in self._services.items():
            if registration.key_prefixes:
                matched = [
                    k for k in unmatched_keys
                    if any(k.startswith(p) for p in registration.key_prefixes)
                ]
                if matched:
                    if service_id not in service_keys:
                        service_keys[service_id] = []
                    service_keys[service_id].extend(matched)
                    for k in matched:
                        if k in unmatched_keys:
                            unmatched_keys.remove(k)

        # Deliver to services
        for service_id, matched_keys in service_keys.items():
            registration = self._services.get(service_id)
            if registration:
                try:
                    registration.callback(
                        event_type=event_type,
                        keys=matched_keys,
                        data=data or {},
                        source=source,
                    )
                    delivery_log[service_id] = matched_keys
                except Exception:
                    pass

        # Log the notification
        self._log_notification(event_type, keys, delivery_log, source)

        # Also publish via event bus
        self._publisher.publish(
            event_type,
            data=data,
            source=source,
            affected_keys=keys,
        )

        return delivery_log

    def _route_key(
        self,
        key: str,
    ) -> Optional[str]:
        """
        Route a key to the appropriate service.

        Args:
            key: Configuration key.

        Returns:
            Target service ID or None.
        """
        # Try exact route match (longest prefix first)
        best_match = None
        best_length = 0

        for prefix, service_id in self._routes.items():
            if key.startswith(prefix + ".") or key == prefix:
                if len(prefix) > best_length:
                    best_match = service_id
                    best_length = len(prefix)

        return best_match

    def _log_notification(
        self,
        event_type: DynamicEvent,
        keys: List[str],
        delivery_log: Dict[str, List[str]],
        source: str,
    ) -> None:
        """Log a notification for audit."""
        log_entry = {
            "event_type": event_type.value,
            "keys": keys,
            "delivered_to": list(delivery_log.keys()),
            "source": source,
            "timestamp": datetime.utcnow().isoformat(),
        }

        with self._lock:
            self._notification_log.append(log_entry)
            if len(self._notification_log) > self._max_log_size:
                self._notification_log.pop(0)

    def get_notification_log(
        self,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get recent notification log."""
        with self._lock:
            return self._notification_log[-limit:]

    def list_services(
        self,
    ) -> List[Dict[str, Any]]:
        """List registered services."""
        with self._lock:
            return [
                {
                    "id": reg.service_id,
                    "key_prefixes": list(reg.key_prefixes) if reg.key_prefixes else None,
                    "metadata": reg.metadata,
                    "registered_at": reg.registered_at.isoformat(),
                }
                for reg in self._services.values()
            ]


class ServiceRegistration:
    """Internal service registration data."""

    def __init__(
        self,
        service_id: str,
        callback: Callable,
        key_prefixes: Optional[Set[str]],
        metadata: Dict[str, Any],
        registered_at: datetime,
    ) -> None:
        self.service_id = service_id
        self.callback = callback
        self.key_prefixes = key_prefixes
        self.metadata = metadata
        self.registered_at = registered_at
