"""
Event router.

Routes domain event types to Kafka topics
using the TopicRegistry, providing a clean
separation between event naming and topic naming.
"""

from __future__ import annotations

from .registry import TopicRegistry


class EventRouter:
    """
    Event router.

    Resolves domain event types to their
    corresponding Kafka topics using the
    TopicRegistry. Provides a stable interface
    for the EventBus to route events.
    """

    def __init__(
        self,
        registry: TopicRegistry,
    ) -> None:

        self.registry = registry

    def topic(
        self,
        event_type: str,
    ) -> str:
        """
        Resolve event type to Kafka topic.

        Args:
            event_type: Domain event type name.

        Returns:
            Kafka topic name.

        Raises:
            KeyError: If event type is not registered.
        """

        return self.registry.resolve(event_type)

    def retry_topic(
        self,
        event_type: str,
        suffix: str = ".retry",
    ) -> str:
        """
        Get the retry topic for an event type.

        Args:
            event_type: Domain event type name.
            suffix: Suffix to append for retry topic.

        Returns:
            Retry topic name.
        """

        base_topic = self.registry.resolve(event_type)
        return f"{base_topic}{suffix}"

    def dead_letter_topic(
        self,
        event_type: str,
        prefix: str = "dlq.",
    ) -> str:
        """
        Get the dead letter queue topic.

        Args:
            event_type: Domain event type name.
            prefix: Prefix for DLQ topic.

        Returns:
            Dead letter queue topic name.
        """

        base_topic = self.registry.resolve(event_type)
        return f"{prefix}{base_topic}"
