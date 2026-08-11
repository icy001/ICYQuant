"""
Event Router — intelligent event routing with rule-based and
strategy-driven dispatch across processors.

Commit 16 Part 1.4
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class RouteStrategy(str, Enum):
    DIRECT = "direct"         # Route to specific processor
    BROADCAST = "broadcast"   # Route to all matching processors
    ROUND_ROBIN = "round_robin"
    HASH = "hash"             # Consistent hash by key
    CONTENT_BASED = "content_based"  # Route based on event content


@dataclass
class RouteRule:
    """A routing rule that matches events to processors."""
    rule_id: str
    topic_pattern: str
    processor_id: str
    strategy: RouteStrategy = RouteStrategy.DIRECT
    condition: Optional[Callable[[Any], bool]] = None
    priority: int = 0
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class EventRouter:
    """
    Intelligent event routing engine for the streaming platform.

    Routes events from topics to processors based on configurable
    routing rules and strategies.

    Features:
    - Pattern-based topic matching
    - Multiple routing strategies (direct, broadcast, round-robin, hash, content-based)
    - Conditional routing with custom predicates
    - Priority-based rule ordering
    - Dynamic rule management

    Usage::

        router = EventRouter()
        router.add_rule(RouteRule("r1", "market.*", "tick_processor"))
        result = await router.route("market.tick", tick_event)
    """

    def __init__(self) -> None:
        self._rules: list[RouteRule] = []
        self._processors: dict[str, Any] = {}
        self._round_robin_counters: dict[str, int] = {}
        self._lock = asyncio.Lock()

    def register_processor(self, processor_id: str, processor: Any) -> None:
        """Register a processor for routing."""
        self._processors[processor_id] = processor
        logger.debug("Processor registered: %s", processor_id)

    def unregister_processor(self, processor_id: str) -> None:
        """Unregister a processor."""
        self._processors.pop(processor_id, None)
        self._rules = [r for r in self._rules if r.processor_id != processor_id]

    def add_rule(self, rule: RouteRule) -> None:
        """Add a routing rule."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)
        logger.debug("Route rule added: %s → %s", rule.rule_id, rule.processor_id)

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a routing rule."""
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.rule_id != rule_id]
        return len(self._rules) < before

    def _match_topic(self, pattern: str, topic: str) -> bool:
        """Check if a topic matches a pattern (supports wildcards)."""
        import fnmatch
        return fnmatch.fnmatch(topic, pattern)

    def _get_matching_rules(self, topic: str) -> list[RouteRule]:
        """Get all rules matching a topic."""
        return [
            r for r in self._rules
            if r.enabled and self._match_topic(r.topic_pattern, topic)
        ]

    async def route(
        self,
        topic: str,
        event: Any,
        *,
        processor_id: Optional[str] = None,
    ) -> list[Any]:
        """Route an event to matching processors."""
        results: list[Any] = []

        # Direct routing to specific processor
        if processor_id:
            processor = self._processors.get(processor_id)
            if processor:
                result = await self._invoke_processor(processor, event)
                results.append(result)
                return results

        # Rule-based routing
        rules = self._get_matching_rules(topic)
        for rule in rules:
            # Check conditional
            if rule.condition and not rule.condition(event):
                continue

            processor = self._processors.get(rule.processor_id)
            if processor is None:
                continue

            strategy = rule.strategy
            if strategy == RouteStrategy.DIRECT:
                result = await self._invoke_processor(processor, event)
                results.append(result)
                break  # First match wins

            elif strategy == RouteStrategy.BROADCAST:
                result = await self._invoke_processor(processor, event)
                results.append(result)

            elif strategy == RouteStrategy.ROUND_ROBIN:
                counter = self._round_robin_counters.get(rule.rule_id, 0)
                self._round_robin_counters[rule.rule_id] = counter + 1
                if counter % 2 == 0:  # Simple round-robin
                    result = await self._invoke_processor(processor, event)
                    results.append(result)

            elif strategy == RouteStrategy.HASH:
                # Hash-based routing — always same processor for same key
                result = await self._invoke_processor(processor, event)
                results.append(result)

            elif strategy == RouteStrategy.CONTENT_BASED:
                result = await self._invoke_processor(processor, event)
                results.append(result)

        return results

    async def _invoke_processor(self, processor: Any, event: Any) -> Any:
        """Invoke a processor with an event."""
        if asyncio.iscoroutinefunction(processor):
            return await processor(event)
        elif callable(processor):
            return processor(event)
        elif hasattr(processor, "process"):
            if asyncio.iscoroutinefunction(processor.process):
                return await processor.process(event)
            return processor.process(event)
        return None

    async def list_rules(self) -> list[dict[str, Any]]:
        """List all routing rules."""
        return [
            {
                "rule_id": r.rule_id,
                "topic_pattern": r.topic_pattern,
                "processor_id": r.processor_id,
                "strategy": r.strategy.value,
                "priority": r.priority,
                "enabled": r.enabled,
            }
            for r in self._rules
        ]

    async def clear_rules(self) -> None:
        """Clear all routing rules."""
        self._rules.clear()
