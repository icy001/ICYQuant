"""Message Router — rule-based routing of inter-agent messages by topic, sender, and content.

Pipeline:
    Message (from MessageBus)
        -> MessageRouter.match_rules() (evaluate routing rules)
        -> MessageRouter.route() (determine destination agents)
        -> deliver to matched subscribers
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Pattern

logger = logging.getLogger(__name__)


class RoutingAction(str, Enum):
    """Action to take when a routing rule matches."""
    DELIVER = "deliver"
    DROP = "drop"
    DEFER = "defer"
    TRANSFORM = "transform"
    BROADCAST = "broadcast"


@dataclass
class RoutingRule:
    """A rule for routing messages based on topic, sender, or content patterns.

    Attributes:
        rule_id: Unique rule identifier.
        name: Human-readable rule name.
        topic_pattern: Regex pattern to match message topics.
        sender_pattern: Regex pattern to match sender agent IDs.
        content_filter: Optional callable to filter by message content.
        action: Action to take on match.
        targets: List of target agent IDs for DELIVER action.
        priority: Rule evaluation priority (lower = evaluated first).
        enabled: Whether the rule is active.
    """

    rule_id: str = ""
    name: str = ""
    topic_pattern: str = ".*"
    sender_pattern: str = ".*"
    content_filter: Optional[Callable[[Dict[str, Any]], bool]] = None
    action: RoutingAction = RoutingAction.DELIVER
    targets: List[str] = field(default_factory=list)
    priority: int = 100
    enabled: bool = True

    _compiled_topic: Optional[Pattern] = field(default=None, repr=False, init=False)
    _compiled_sender: Optional[Pattern] = field(default=None, repr=False, init=False)

    def __post_init__(self) -> None:
        """Compile regex patterns after initialization."""
        try:
            self._compiled_topic = re.compile(self.topic_pattern)
        except re.error:
            self._compiled_topic = re.compile(".*")
        try:
            self._compiled_sender = re.compile(self.sender_pattern)
        except re.error:
            self._compiled_sender = re.compile(".*")

    def matches(self, topic: str, sender_id: str, content: Dict[str, Any]) -> bool:
        """Check whether this rule matches a message.

        Args:
            topic: Message topic.
            sender_id: Sender agent ID.
            content: Message content.

        Returns:
            True if the rule matches.
        """
        if not self.enabled:
            return False
        if self._compiled_topic and not self._compiled_topic.match(topic):
            return False
        if self._compiled_sender and not self._compiled_sender.match(sender_id):
            return False
        if self.content_filter and not self.content_filter(content):
            return False
        return True


class MessageRouter:
    """Rule-based router for inter-agent messages.

    Evaluates messages against a set of routing rules and determines
    which agents should receive each message.

    Supports:
        - Topic-based routing (regex patterns)
        - Sender-based routing
        - Content-based filtering (callable predicates)
        - Priority-ordered rule evaluation
        - Actions: DELIVER, DROP, DEFER, TRANSFORM, BROADCAST
        - Rule enable/disable at runtime

    Usage:
        router = MessageRouter()
        await router.initialize()
        rule = RoutingRule(
            name="market_updates",
            topic_pattern=r"market\..*",
            action=RoutingAction.DELIVER,
            targets=["research_agent", "risk_agent"],
        )
        router.add_rule(rule)
        targets = router.route("market.update", "market_agent", {...})
    """

    def __init__(self) -> None:
        """Initialize the message router."""
        self._rules: List[RoutingRule] = []
        self._initialized: bool = False
        logger.info("MessageRouter created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the router."""
        if self._initialized:
            logger.warning("MessageRouter already initialized")
            return
        self._initialized = True
        logger.info("MessageRouter initialized")

    async def shutdown(self) -> None:
        """Shut down the router."""
        if not self._initialized:
            return
        self._rules.clear()
        self._initialized = False
        logger.info("MessageRouter shutdown complete")

    # ── Rule Management ──

    def add_rule(self, rule: RoutingRule) -> None:
        """Add a routing rule.

        Args:
            rule: The routing rule to add.
        """
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority)
        logger.debug("Routing rule added: %s (priority=%d)", rule.name, rule.priority)

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a routing rule by ID.

        Args:
            rule_id: The rule identifier.

        Returns:
            True if removed, False if not found.
        """
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.rule_id != rule_id]
        removed = before > len(self._rules)
        if removed:
            logger.debug("Routing rule removed: %s", rule_id)
        return removed

    def enable_rule(self, rule_id: str) -> bool:
        """Enable a routing rule.

        Args:
            rule_id: The rule identifier.

        Returns:
            True if the rule was found and enabled.
        """
        for rule in self._rules:
            if rule.rule_id == rule_id:
                rule.enabled = True
                return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        """Disable a routing rule.

        Args:
            rule_id: The rule identifier.

        Returns:
            True if the rule was found and disabled.
        """
        for rule in self._rules:
            if rule.rule_id == rule_id:
                rule.enabled = False
                return True
        return False

    # ── Routing ──

    def route(
        self, topic: str, sender_id: str, content: Dict[str, Any],
    ) -> Dict[RoutingAction, List[str]]:
        """Route a message based on matching rules.

        Evaluates all rules in priority order. The first matching rule
        determines the routing action and targets.

        Args:
            topic: Message topic.
            sender_id: Sender agent ID.
            content: Message content.

        Returns:
            Dict mapping actions to lists of target agent IDs.
        """
        if not self._initialized:
            return {RoutingAction.DELIVER: []}

        for rule in self._rules:
            if rule.matches(topic, sender_id, content):
                logger.debug("Message routed by rule '%s': %s -> %s",
                             rule.name, topic, rule.action.value)
                if rule.action == RoutingAction.DROP:
                    return {}
                if rule.action == RoutingAction.BROADCAST:
                    return {RoutingAction.BROADCAST: ["*"]}
                return {rule.action: list(rule.targets)}

        # Default: deliver to empty list (no targets)
        return {RoutingAction.DELIVER: []}

    # ── Default Rules ──

    def add_default_rules(self) -> None:
        """Add a set of sensible default routing rules."""
        import uuid

        # Market updates → research + risk + strategy agents
        self.add_rule(RoutingRule(
            rule_id=uuid.uuid4().hex[:8],
            name="market_to_research",
            topic_pattern=r"market\..*",
            action=RoutingAction.DELIVER,
            targets=["research_agent", "risk_agent", "strategy_agent"],
            priority=10,
        ))

        # Risk alerts → portfolio + coordinator
        self.add_rule(RoutingRule(
            rule_id=uuid.uuid4().hex[:8],
            name="risk_alerts",
            topic_pattern=r"risk\.alert\..*",
            action=RoutingAction.DELIVER,
            targets=["portfolio_agent", "coordinator"],
            priority=5,
        ))

        # Task events → coordinator
        self.add_rule(RoutingRule(
            rule_id=uuid.uuid4().hex[:8],
            name="task_to_coordinator",
            topic_pattern=r"task\..*",
            action=RoutingAction.DELIVER,
            targets=["coordinator"],
            priority=15,
        ))

        # Heartbeat messages → drop (handled by monitor directly)
        self.add_rule(RoutingRule(
            rule_id=uuid.uuid4().hex[:8],
            name="drop_heartbeats",
            topic_pattern=r"system\.heartbeat",
            action=RoutingAction.DROP,
            priority=1,
        ))

        logger.info("Default routing rules added")

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the router state.

        Returns:
            Dict with rule count and status.
        """
        return {
            "initialized": self._initialized,
            "total_rules": len(self._rules),
            "enabled_rules": sum(1 for r in self._rules if r.enabled),
        }
