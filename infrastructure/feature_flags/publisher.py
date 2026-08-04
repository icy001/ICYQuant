"""
Feature flag event publisher.

Provides a unified interface for publishing
feature flag events to the EventBus and
external systems (e.g., ICYQuant EventBus).

All feature flag changes are automatically
broadcast through this layer.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from .events import EventBus, FeatureEvent, FeatureEventType

logger = logging.getLogger(__name__)


class FeatureEventPublisher:
    """
    Publishes feature flag events to the EventBus.

    Centralizes event creation and publication,
    ensuring all feature flag changes are
    consistently broadcast to subscribers.

    Supports:
        - Auto event creation for flag lifecycle
        - Batch event publication
        - External event bus integration
        - Retry logic for failed publications

    Usage:
        publisher = FeatureEventPublisher(bus)
        await publisher.publish_flag_created("my.flag", data={...})
    """

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        max_retries: int = 3,
    ) -> None:
        """
        Initialize event publisher.

        Args:
            event_bus: EventBus instance (created if None).
            max_retries: Max retry attempts for failed publications.
        """
        self._bus = event_bus or EventBus()
        self._max_retries = max_retries
        self._publish_count = 0
        self._error_count = 0

    @property
    def bus(self) -> EventBus:
        """Get the underlying EventBus."""
        return self._bus

    async def publish(
        self,
        event_type: FeatureEventType,
        flag_key: str = "",
        data: Optional[Dict[str, Any]] = None,
        trace_id: str = "",
        operator: str = "system",
    ) -> int:
        """
        Create and publish a feature event.

        Args:
            event_type: Type of event.
            flag_key: Associated flag key.
            data: Event payload.
            trace_id: Correlation ID.
            operator: Who triggered the event.

        Returns:
            Number of subscribers notified.
        """
        event = FeatureEvent(
            event_type=event_type,
            flag_key=flag_key,
            data=data or {},
            trace_id=trace_id,
            operator=operator,
        )
        return await self._publish_with_retry(event)

    async def _publish_with_retry(
        self,
        event: FeatureEvent,
    ) -> int:
        """Publish with retry logic."""
        last_error = None

        for attempt in range(self._max_retries):
            try:
                notified = await self._bus.publish(event)
                self._publish_count += 1
                return notified
            except Exception as e:
                last_error = e
                self._error_count += 1
                logger.warning(
                    "Publish attempt %d failed for %s: %s",
                    attempt + 1,
                    event.event_type.value,
                    e,
                )
                await asyncio.sleep(0.1 * (attempt + 1))

        logger.error(
            "Failed to publish event %s after %d attempts: %s",
            event.event_type.value,
            self._max_retries,
            last_error,
        )
        return 0

    # ── Convenience methods for flag lifecycle ──

    async def publish_flag_created(
        self, key: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any,
    ) -> int:
        """Publish a flag created event."""
        return await self.publish(
            FeatureEventType.FLAG_CREATED, key, data, **kwargs,
        )

    async def publish_flag_updated(
        self, key: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any,
    ) -> int:
        """Publish a flag updated event."""
        return await self.publish(
            FeatureEventType.FLAG_UPDATED, key, data, **kwargs,
        )

    async def publish_flag_deleted(
        self, key: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any,
    ) -> int:
        """Publish a flag deleted event."""
        return await self.publish(
            FeatureEventType.FLAG_DELETED, key, data, **kwargs,
        )

    async def publish_flag_enabled(
        self, key: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any,
    ) -> int:
        """Publish a flag enabled event."""
        return await self.publish(
            FeatureEventType.FLAG_ENABLED, key, data, **kwargs,
        )

    async def publish_flag_disabled(
        self, key: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any,
    ) -> int:
        """Publish a flag disabled event."""
        return await self.publish(
            FeatureEventType.FLAG_DISABLED, key, data, **kwargs,
        )

    # ── Convenience methods for rollout/canary ──

    async def publish_rollout_started(
        self, key: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any,
    ) -> int:
        """Publish a rollout started event."""
        return await self.publish(
            FeatureEventType.ROLLOUT_STARTED, key, data, **kwargs,
        )

    async def publish_canary_started(
        self, key: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any,
    ) -> int:
        """Publish a canary started event."""
        return await self.publish(
            FeatureEventType.CANARY_STARTED, key, data, **kwargs,
        )

    async def publish_canary_completed(
        self, key: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any,
    ) -> int:
        """Publish a canary completed event."""
        return await self.publish(
            FeatureEventType.CANARY_COMPLETED, key, data, **kwargs,
        )

    async def publish_canary_rolled_back(
        self, key: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any,
    ) -> int:
        """Publish a canary rolled back event."""
        return await self.publish(
            FeatureEventType.CANARY_ROLLED_BACK, key, data, **kwargs,
        )

    # ── Convenience methods for experiments ──

    async def publish_experiment_started(
        self, key: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any,
    ) -> int:
        """Publish an experiment started event."""
        return await self.publish(
            FeatureEventType.EXPERIMENT_STARTED, key, data, **kwargs,
        )

    async def publish_experiment_completed(
        self, key: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any,
    ) -> int:
        """Publish an experiment completed event."""
        return await self.publish(
            FeatureEventType.EXPERIMENT_COMPLETED, key, data, **kwargs,
        )

    # ── Convenience methods for snapshots ──

    async def publish_snapshot_activated(
        self, key: str = "", data: Optional[Dict[str, Any]] = None, **kwargs: Any,
    ) -> int:
        """Publish a snapshot activated event."""
        return await self.publish(
            FeatureEventType.SNAPSHOT_ACTIVATED, key, data, **kwargs,
        )

    async def publish_hot_reload(
        self, key: str = "", data: Optional[Dict[str, Any]] = None, **kwargs: Any,
    ) -> int:
        """Publish a hot reload event."""
        return await self.publish(
            FeatureEventType.HOT_RELOAD, key, data, **kwargs,
        )

    # ── Batch operations ──

    async def publish_batch(
        self,
        events: list,
    ) -> int:
        """
        Publish a batch of events.

        Args:
            events: List of FeatureEvent objects.

        Returns:
            Total subscribers notified.
        """
        total = 0
        for event in events:
            total += await self._publish_with_retry(event)
        return total

    def get_stats(self) -> Dict[str, Any]:
        """Get publisher statistics."""
        return {
            "published_count": self._publish_count,
            "error_count": self._error_count,
            "event_bus_stats": self._bus.get_stats(),
        }
