"""
Configuration subscriber.

Allows components to subscribe to configuration changes
for specific keys or prefixes. Subscribers only receive
events for their subscribed configuration scope.

Supported subscribers:
- OMS (Order Management System)
- Risk Engine
- Strategy Engine
- Execution Engine
- Gateway
- Monitoring
"""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

from .publisher import ConfigurationEventPublisher, DynamicEvent


class ConfigurationSubscription:
    """
    Represents a configuration subscription.

    A subscriber can filter events by:
    - Specific keys (exact match)
    - Key prefixes (e.g., "oms.*")
    - Event types

    Attributes:
        subscriber_id: Unique subscriber identifier.
        callback: Callback function.
        subscribed_keys: Set of specific keys to watch.
        subscribed_prefixes: Set of key prefixes to watch.
        event_types: Set of event types to listen for.
        metadata: Additional subscription metadata.
    """

    def __init__(
        self,
        subscriber_id: str,
        callback: Callable,
        subscribed_keys: Optional[Set[str]] = None,
        subscribed_prefixes: Optional[Set[str]] = None,
        event_types: Optional[Set[DynamicEvent]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize subscription.

        Args:
            subscriber_id: Unique identifier for the subscriber.
            callback: Callback function to invoke.
            subscribed_keys: Specific keys to watch.
            subscribed_prefixes: Key prefixes to watch.
            event_types: Event types to listen for.
            metadata: Additional metadata.
        """
        self.subscriber_id = subscriber_id
        self.callback = callback
        self.subscribed_keys = subscribed_keys or set()
        self.subscribed_prefixes = subscribed_prefixes or set()
        self.event_types = event_types or {DynamicEvent.CONFIG_CHANGED}
        self.metadata = metadata or {}
        self.created_at = datetime.utcnow()
        self.total_calls = 0
        self.last_called_at: Optional[datetime] = None

    def matches_key(
        self,
        key: str,
    ) -> bool:
        """
        Check if this subscription matches a key.

        Args:
            key: Configuration key.

        Returns:
            True if the key matches subscription filters.
        """
        # Exact match
        if key in self.subscribed_keys:
            return True

        # Prefix match
        for prefix in self.subscribed_prefixes:
            if key.startswith(prefix):
                return True

        # No filter means match all
        if not self.subscribed_keys and not self.subscribed_prefixes:
            return True

        return False

    def matches_event(
        self,
        event_type: DynamicEvent,
    ) -> bool:
        """Check if subscription matches an event type."""
        return event_type in self.event_types

    def invoke(
        self,
        event_type: DynamicEvent,
        event_data: Dict[str, Any],
    ) -> None:
        """
        Invoke the callback if the subscription matches.

        Args:
            event_type: Event type.
            event_data: Event data.
        """
        if not self.matches_event(event_type):
            return

        affected_keys = event_data.get("affected_keys", [])
        if affected_keys:
            # Check if any affected key matches
            matched = any(self.matches_key(k) for k in affected_keys)
            if not matched:
                return

        # Invoke callback
        self.total_calls += 1
        self.last_called_at = datetime.utcnow()
        try:
            self.callback(event_type, event_data)
        except Exception:
            pass


class ConfigurationSubscriber:
    """
    Configuration subscription manager.

    Manages subscriptions and dispatches events
    to matching subscribers. Integrates with
    ConfigurationEventPublisher.

    Usage:
        subscriber = ConfigurationSubscriber()

        # Subscribe OMS to oms.* changes
        sub_id = subscriber.subscribe(
            callback=on_oms_change,
            prefixes={"oms."},
            subscriber_id="oms-engine",
        )

        # Subscribe Risk Engine to risk.* changes
        subscriber.subscribe(
            callback=on_risk_change,
            prefixes={"risk."},
            subscriber_id="risk-engine",
        )

        # Dispatch event
        subscriber.dispatch_event(
            DynamicEvent.CONFIG_CHANGED,
            affected_keys=["risk.max_position", "oms.order_timeout"],
        )
    """

    def __init__(
        self,
        publisher: Optional[ConfigurationEventPublisher] = None,
    ) -> None:
        """
        Initialize subscriber manager.

        Args:
            publisher: ConfigurationEventPublisher instance.
        """
        self._publisher = publisher or ConfigurationEventPublisher()
        self._subscriptions: Dict[str, ConfigurationSubscription] = {}
        self._lock = threading.RLock()

    @property
    def publisher(
        self,
    ) -> ConfigurationEventPublisher:
        """Get event publisher."""
        return self._publisher

    def subscribe(
        self,
        callback: Callable,
        subscribed_keys: Optional[Set[str]] = None,
        subscribed_prefixes: Optional[Set[str]] = None,
        event_types: Optional[Set[DynamicEvent]] = None,
        subscriber_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Subscribe to configuration changes.

        Args:
            callback: Callback function.
            subscribed_keys: Specific keys to watch.
            subscribed_prefixes: Key prefixes to watch.
            event_types: Event types to listen for.
            subscriber_id: Unique ID (auto-generated if None).
            metadata: Additional metadata.

        Returns:
            Subscription ID.
        """
        sub_id = subscriber_id or f"sub_{id(callback):016x}"

        subscription = ConfigurationSubscription(
            subscriber_id=sub_id,
            callback=callback,
            subscribed_keys=subscribed_keys,
            subscribed_prefixes=subscribed_prefixes,
            event_types=event_types,
            metadata=metadata,
        )

        with self._lock:
            self._subscriptions[sub_id] = subscription

        self._publisher.publish(
            DynamicEvent.SUBSCRIBER_ADDED,
            data={"subscriber_id": sub_id, "metadata": metadata},
        )

        return sub_id

    def unsubscribe(
        self,
        subscriber_id: str,
    ) -> bool:
        """
        Remove a subscription.

        Args:
            subscriber_id: Subscription to remove.

        Returns:
            True if removed.
        """
        with self._lock:
            removed = self._subscriptions.pop(subscriber_id, None)

        if removed:
            self._publisher.publish(
                DynamicEvent.SUBSCRIBER_REMOVED,
                data={"subscriber_id": subscriber_id},
            )
            return True
        return False

    def dispatch_event(
        self,
        event_type: DynamicEvent,
        event_data: Optional[Dict[str, Any]] = None,
        affected_keys: Optional[List[str]] = None,
    ) -> int:
        """
        Dispatch an event to matching subscribers.

        Args:
            event_type: Event type.
            event_data: Event data.
            affected_keys: Keys affected by the change.

        Returns:
            Number of subscribers notified.
        """
        event_data = event_data or {}
        if affected_keys:
            event_data["affected_keys"] = affected_keys

        notified = 0
        with self._lock:
            subscriptions = list(self._subscriptions.values())

        for subscription in subscriptions:
            try:
                subscription.invoke(event_type, event_data)
                notified += 1
            except Exception:
                pass

        return notified

    def get_subscription(
        self,
        subscriber_id: str,
    ) -> Optional[ConfigurationSubscription]:
        """Get a subscription by ID."""
        with self._lock:
            return self._subscriptions.get(subscriber_id)

    def list_subscriptions(
        self,
    ) -> List[Dict[str, Any]]:
        """List all active subscriptions."""
        with self._lock:
            return [
                {
                    "id": sub.subscriber_id,
                    "keys": list(sub.subscribed_keys),
                    "prefixes": list(sub.subscribed_prefixes),
                    "event_types": [e.value for e in sub.event_types],
                    "total_calls": sub.total_calls,
                    "created_at": sub.created_at.isoformat(),
                }
                for sub in self._subscriptions.values()
            ]

    def subscriber_count(
        self,
    ) -> int:
        """Get number of active subscribers."""
        with self._lock:
            return len(self._subscriptions)

    def clear(
        self,
    ) -> None:
        """Remove all subscriptions."""
        with self._lock:
            self._subscriptions.clear()
