"""
Topic registry.

Maps domain event types to Kafka topics,
providing a central registry for event-to-topic
resolution across the ICYQuant platform.
"""

from __future__ import annotations

from typing import Dict, Optional


class TopicRegistry:
    """
    Topic registry.

    Maintains a mapping between domain event
    types (e.g., OrderCreated) and Kafka topics
    (e.g., order.created). Supports default
    registration of known event types.
    """

    def __init__(
        self,
    ) -> None:

        self._topics: Dict[str, str] = {}

    def register(
        self,
        event: str,
        topic: str,
    ) -> None:
        """
        Register an event-to-topic mapping.

        Args:
            event: Domain event type.
            topic: Kafka topic name.
        """

        self._topics[event] = topic

    def resolve(
        self,
        event: str,
    ) -> str:
        """
        Resolve event type to topic.

        Args:
            event: Domain event type.

        Returns:
            Kafka topic name.

        Raises:
            KeyError: If event type is not registered.
        """

        if event not in self._topics:
            raise KeyError(
                f"Event '{event}' is not registered "
                f"in the topic registry. "
                f"Known events: "
                f"{list(self._topics.keys())}"
            )

        return self._topics[event]

    def get(
        self,
        event: str,
        default: Optional[str] = None,
    ) -> Optional[str]:
        """
        Safely resolve event type to topic.

        Args:
            event: Domain event type.
            default: Default value if not found.

        Returns:
            Kafka topic name or default value.
        """

        return self._topics.get(event, default)

    def list_events(
        self,
    ) -> list:
        """
        List all registered event types.

        Returns:
            List of registered event type names.
        """

        return list(self._topics.keys())

    def list_topics(
        self,
    ) -> list:
        """
        List all registered topics.

        Returns:
            List of registered topic names.
        """

        return list(set(self._topics.values()))

    @classmethod
    def with_defaults(
        cls,
    ) -> TopicRegistry:
        """
        Create registry with default event mappings.

        Registers all core ICYQuant event types
        with their Kafka topics following the
        <domain>.<entity>.<event> naming convention.

        Returns:
            Pre-configured TopicRegistry instance.
        """

        registry = cls()

        # Market events
        registry.register(
            "MarketTick",
            "market.ticks",
        )
        registry.register(
            "MarketOrderBook",
            "market.orderbook",
        )

        # Strategy events
        registry.register(
            "StrategySignalGenerated",
            "strategy.signal.generated",
        )
        registry.register(
            "StrategySignalApproved",
            "strategy.signal.approved",
        )

        # Order events
        registry.register(
            "OrderCreated",
            "order.created",
        )
        registry.register(
            "OrderSubmitted",
            "order.submitted",
        )
        registry.register(
            "OrderCancelled",
            "order.cancelled",
        )

        # Trade events
        registry.register(
            "TradeExecuted",
            "trade.executed",
        )
        registry.register(
            "TradeRejected",
            "trade.rejected",
        )

        # Position events
        registry.register(
            "PositionUpdated",
            "position.updated",
        )

        # Risk events
        registry.register(
            "RiskLimitTriggered",
            "risk.limit.triggered",
        )

        # Ledger events
        registry.register(
            "LedgerEntryCreated",
            "ledger.entry.created",
        )

        # Notification events
        registry.register(
            "NotificationEmail",
            "notification.email",
        )
        registry.register(
            "NotificationWebhook",
            "notification.webhook",
        )

        return registry
