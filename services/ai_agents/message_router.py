"""
ICYQuant Message Router — intelligent message routing and filtering.

Routes messages based on type, priority, topic patterns, and content-based
rules. Provides rate limiting, message transformation, and pipeline processing.
"""

from __future__ import annotations

import asyncio
import fnmatch
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Optional

from .agent_message import MessageEnvelope, MessageType, MessagePriority

logger = logging.getLogger(__name__)

RouteHandler = Callable[[MessageEnvelope], Awaitable[Any]]


class RouteStrategy(str, Enum):
    DIRECT = "direct"           # Route to specific agent
    TOPIC = "topic"             # Route by topic pattern
    TYPE_BASED = "type_based"   # Route by message type
    ROUND_ROBIN = "round_robin" # Load-balanced round-robin
    BROADCAST = "broadcast"     # Send to all matching


@dataclass
class RouteRule:
    """A rule that determines how messages are routed."""
    rule_id: str
    strategy: RouteStrategy
    priority: int = 0

    # Match conditions (all must match if set)
    msg_types: list[MessageType] = field(default_factory=list)
    topic_patterns: list[str] = field(default_factory=list)
    sender_filter: list[str] = field(default_factory=list)
    priority_filter: list[MessagePriority] = field(default_factory=list)

    # Targets
    target_agents: list[str] = field(default_factory=list)
    target_topics: list[str] = field(default_factory=list)
    handler: Optional[RouteHandler] = None

    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def matches(self, envelope: MessageEnvelope) -> bool:
        """Check if this rule matches the given envelope."""
        if not self.enabled:
            return False

        if self.msg_types and envelope.msg_type not in self.msg_types:
            return False

        if self.priority_filter and envelope.priority not in self.priority_filter:
            return False

        if self.sender_filter and envelope.sender_id not in self.sender_filter:
            return False

        if self.topic_patterns:
            if not any(fnmatch.fnmatch(envelope.topic, p) for p in self.topic_patterns):
                return False

        return True


@dataclass
class RouterStats:
    messages_received: int = 0
    messages_routed: int = 0
    messages_skipped: int = 0
    messages_throttled: int = 0
    active_rules: int = 0


class MessageRouter:
    """Intelligent message router with rule-based dispatch.

    Features:
        - Rule-based routing with priority ordering
        - Content-based filtering (type, topic, sender)
        - Round-robin load balancing
        - Rate limiting per agent/topic
        - Message transformation pipeline
        - Fallback routing for unmatched messages
    """

    def __init__(self, communication_bus: Any = None,
                 max_rate_per_second: int = 100) -> None:
        self._comm_bus = communication_bus
        self._max_rate_per_second = max_rate_per_second

        self._rules: list[RouteRule] = []
        self._handlers: dict[MessageType, list[RouteHandler]] = defaultdict(list)
        self._round_robin_counters: dict[str, int] = defaultdict(int)

        # Rate limiting
        self._rate_counters: dict[str, list[float]] = defaultdict(list)

        self._stats = RouterStats()
        self._fallback_handler: Optional[RouteHandler] = None

    # ── Rule Management ──

    def add_rule(self, rule: RouteRule) -> None:
        """Add a routing rule. Rules are evaluated in priority order (higher first)."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: -r.priority)
        self._stats.active_rules = len(self._rules)
        logger.debug("Added route rule %s [priority=%d]", rule.rule_id, rule.priority)

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a routing rule by ID."""
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.rule_id != rule_id]
        self._stats.active_rules = len(self._rules)
        return len(self._rules) < before

    def set_fallback_handler(self, handler: RouteHandler) -> None:
        """Set a handler for messages that match no rule."""
        self._fallback_handler = handler

    # ── Type-based handlers ──

    def register_handler(self, msg_type: MessageType, handler: RouteHandler) -> None:
        """Register a handler for a specific message type."""
        self._handlers[msg_type].append(handler)

    # ── Routing ──

    async def route(self, envelope: MessageEnvelope) -> bool:
        """Route a message through the rule engine."""
        self._stats.messages_received += 1

        # Rate limiting check
        if not self._check_rate(envelope):
            self._stats.messages_throttled += 1
            logger.warning("Rate limited message %s from %s", envelope.message_id, envelope.sender_id)
            return False

        routed = False

        # 1. Evaluate rules in priority order
        for rule in self._rules:
            if not rule.matches(envelope):
                continue

            await self._apply_rule(rule, envelope)
            routed = True
            break  # First matching rule wins (highest priority)

        # 2. Try type-based handlers if no rule matched
        if not routed:
            handlers = self._handlers.get(envelope.msg_type, [])
            for handler in handlers:
                try:
                    await handler(envelope)
                    routed = True
                except Exception as exc:
                    logger.error("Type handler failed for %s: %s", envelope.message_id, exc)

        # 3. Fallback handler
        if not routed and self._fallback_handler:
            try:
                await self._fallback_handler(envelope)
                routed = True
            except Exception as exc:
                logger.error("Fallback handler failed for %s: %s", envelope.message_id, exc)

        if routed:
            self._stats.messages_routed += 1
        else:
            self._stats.messages_skipped += 1

        return routed

    async def _apply_rule(self, rule: RouteRule, envelope: MessageEnvelope) -> None:
        """Execute a matched routing rule."""
        if rule.strategy == RouteStrategy.DIRECT:
            for target in rule.target_agents:
                if self._comm_bus:
                    routed_envelope = MessageEnvelope(
                        msg_type=envelope.msg_type,
                        sender_id=envelope.sender_id,
                        recipient_id=target,
                        topic=envelope.topic,
                        payload=envelope.payload,
                        correlation_id=envelope.correlation_id,
                        trace_id=envelope.trace_id,
                    )
                    await self._comm_bus.send(routed_envelope)

        elif rule.strategy == RouteStrategy.TOPIC:
            for topic in rule.target_topics:
                if self._comm_bus:
                    routed_envelope = MessageEnvelope(
                        msg_type=envelope.msg_type,
                        sender_id=envelope.sender_id,
                        topic=topic,
                        payload=envelope.payload,
                        trace_id=envelope.trace_id,
                    )
                    await self._comm_bus.publish(routed_envelope)

        elif rule.strategy == RouteStrategy.BROADCAST:
            if self._comm_bus:
                await self._comm_bus.broadcast(envelope)

        elif rule.strategy == RouteStrategy.ROUND_ROBIN:
            if rule.target_agents:
                idx = self._round_robin_counters[rule.rule_id] % len(rule.target_agents)
                self._round_robin_counters[rule.rule_id] += 1
                target = rule.target_agents[idx]
                if self._comm_bus:
                    routed_envelope = MessageEnvelope(
                        msg_type=envelope.msg_type,
                        sender_id=envelope.sender_id,
                        recipient_id=target,
                        payload=envelope.payload,
                        trace_id=envelope.trace_id,
                    )
                    await self._comm_bus.send(routed_envelope)

        elif rule.strategy == RouteStrategy.TYPE_BASED:
            if rule.handler:
                await rule.handler(envelope)

    # ── Rate Limiting ──

    def _check_rate(self, envelope: MessageEnvelope) -> bool:
        """Sliding-window rate limit check."""
        key = f"{envelope.sender_id}:{envelope.topic}"
        now = asyncio.get_event_loop().time()

        # Clean old entries (1-second window)
        self._rate_counters[key] = [t for t in self._rate_counters[key] if now - t < 1.0]
        self._rate_counters[key].append(now)

        return len(self._rate_counters[key]) <= self._max_rate_per_second

    # ── Stats ──

    @property
    def stats(self) -> RouterStats:
        return self._stats
