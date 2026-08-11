"""Conflict Resolver — resolves disagreements between agents using rules, confidence, and escalation.

Pipeline:
    Conflict (agent A opinion ≠ agent B opinion)
        -> ConflictResolver.detect() (identify conflicts)
        -> ConflictResolver.resolve() (apply resolution strategy)
        -> Resolution (final decision with rationale)

Handles situations where agents disagree, e.g. Research says BUY but
Risk says HALT. Resolution follows configurable strategies: confidence-based,
rule-based, escalation, or coordinator override.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ConflictType(str, Enum):
    """Types of conflicts between agents."""
    OPINION_DIVERGENCE = "opinion_divergence"    # Different analysis conclusions
    RESOURCE_CONTENTION = "resource_contention"  # Competing for same resource
    PRIORITY_CONFLICT = "priority_conflict"      # Different task priorities
    CONSTRAINT_VIOLATION = "constraint_violation" # One agent violates another's constraints
    DATA_DISAGREEMENT = "data_disagreement"      # Different data interpretations


class ResolutionStrategy(str, Enum):
    """Strategies for resolving conflicts."""
    HIGHEST_CONFIDENCE = "highest_confidence"   # Agent with highest confidence wins
    SAFETY_FIRST = "safety_first"               # Most conservative/risk-averse wins
    RULE_BASED = "rule_based"                   # Pre-defined resolution rules
    ESCALATION = "escalation"                   # Escalate to coordinator
    CONSENSUS = "consensus"                     # Require consensus through voting
    TIME_PRIORITY = "time_priority"             # Most recent analysis wins


@dataclass
class Conflict:
    """A conflict between two or more agents.

    Attributes:
        conflict_id: Unique conflict identifier.
        conflict_type: Type of conflict.
        agent_a_id: First agent's ID.
        agent_a_position: First agent's position/opinion.
        agent_b_id: Second agent's ID.
        agent_b_position: Second agent's position/opinion.
        context: Additional context about the conflict.
        severity: Conflict severity (0.0 - 1.0).
    """

    conflict_id: str = field(default_factory=lambda: uuid4().hex)
    conflict_type: ConflictType = ConflictType.OPINION_DIVERGENCE
    agent_a_id: str = ""
    agent_a_position: Any = None
    agent_b_id: str = ""
    agent_b_position: Any = None
    context: Dict[str, Any] = field(default_factory=dict)
    severity: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        """Return conflict as a dictionary."""
        return {
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type.value,
            "agent_a_id": self.agent_a_id,
            "agent_b_id": self.agent_b_id,
            "severity": self.severity,
        }


@dataclass
class Resolution:
    """Resolution of a conflict.

    Attributes:
        resolution_id: Unique resolution identifier.
        conflict_id: The resolved conflict's ID.
        strategy: Strategy used for resolution.
        winning_agent_id: Agent whose position was selected.
        final_decision: The final decision.
        rationale: Human-readable explanation.
        overridden_agent_id: Agent whose position was overridden.
        escalated: Whether the conflict was escalated.
    """

    resolution_id: str = field(default_factory=lambda: uuid4().hex)
    conflict_id: str = ""
    strategy: ResolutionStrategy = ResolutionStrategy.SAFETY_FIRST
    winning_agent_id: str = ""
    final_decision: Any = None
    rationale: str = ""
    overridden_agent_id: str = ""
    escalated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Return resolution as a dictionary."""
        return {
            "resolution_id": self.resolution_id,
            "conflict_id": self.conflict_id,
            "strategy": self.strategy.value,
            "winning_agent_id": self.winning_agent_id,
            "rationale": self.rationale,
            "escalated": self.escalated,
        }


class ConflictResolver:
    """Resolves disagreements between agents in the multi-agent system.

    Detects conflicts between agent positions and resolves them using
    configurable strategies. Prioritizes safety in financial contexts.

    Supports:
        - Conflict detection (opinion, resource, priority, constraint, data)
        - Multiple resolution strategies
        - Safety-first default for risk-sensitive decisions
        - Confidence-based resolution
        - Rule-based resolution with predefined rules
        - Escalation to coordinator
        - Severity assessment

    Usage:
        resolver = ConflictResolver()
        await resolver.initialize()
        conflict = Conflict(
            agent_a_id="research", agent_a_position="BUY",
            agent_b_id="risk", agent_b_position="HALT",
        )
        resolution = await resolver.resolve(conflict)
    """

    def __init__(self) -> None:
        """Initialize the conflict resolver."""
        self._resolutions: Dict[str, Resolution] = {}
        self._rules: List[Dict[str, Any]] = []
        self._initialized: bool = False
        logger.info("ConflictResolver created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the conflict resolver and load default rules."""
        if self._initialized:
            logger.warning("ConflictResolver already initialized")
            return
        self._load_default_rules()
        self._initialized = True
        logger.info("ConflictResolver initialized")

    async def shutdown(self) -> None:
        """Shut down the conflict resolver."""
        if not self._initialized:
            return
        self._resolutions.clear()
        self._rules.clear()
        self._initialized = False
        logger.info("ConflictResolver shutdown complete")

    # ── Default Rules ──

    def _load_default_rules(self) -> None:
        """Load default conflict resolution rules.

        Priority order for financial contexts: Risk > Compliance > Portfolio > Strategy > Research.
        """
        self._rules = [
            {
                "id": "risk_overrides_all",
                "description": "Risk agent veto overrides all trading decisions",
                "condition": lambda c: "risk" in c.agent_b_id.lower() and c.conflict_type == ConflictType.OPINION_DIVERGENCE,
                "winner": "agent_b",  # Risk agent wins
            },
            {
                "id": "safety_first",
                "description": "Most conservative position wins in financial conflicts",
                "condition": lambda c: c.conflict_type == ConflictType.CONSTRAINT_VIOLATION,
                "winner": "agent_b",  # Constraint enforcer wins
            },
            {
                "id": "portfolio_priority",
                "description": "Portfolio constraints override individual strategy decisions",
                "condition": lambda c: "portfolio" in c.agent_b_id.lower(),
                "winner": "agent_b",
            },
        ]
        logger.debug("Loaded %d default conflict resolution rules", len(self._rules))

    # ── Detection ──

    def detect(
        self, agent_a_id: str, position_a: Any,
        agent_b_id: str, position_b: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Conflict]:
        """Detect if a conflict exists between two agent positions.

        Args:
            agent_a_id: First agent's ID.
            position_a: First agent's position.
            agent_b_id: Second agent's ID.
            position_b: Second agent's position.
            context: Additional context.

        Returns:
            Conflict object if conflict detected, None if positions agree.
        """
        if position_a == position_b:
            return None

        # Determine conflict type
        conflict_type = ConflictType.OPINION_DIVERGENCE
        if context:
            if context.get("constraint_violation"):
                conflict_type = ConflictType.CONSTRAINT_VIOLATION
            elif context.get("resource_contention"):
                conflict_type = ConflictType.RESOURCE_CONTENTION

        # Calculate severity
        severity = self._calculate_severity(position_a, position_b, conflict_type)

        conflict = Conflict(
            conflict_type=conflict_type,
            agent_a_id=agent_a_id,
            agent_a_position=position_a,
            agent_b_id=agent_b_id,
            agent_b_position=position_b,
            context=context or {},
            severity=severity,
        )
        logger.info("Conflict detected: %s vs %s (type=%s, severity=%.2f)",
                    agent_a_id, agent_b_id, conflict_type.value, severity)
        return conflict

    # ── Resolution ──

    async def resolve(
        self, conflict: Conflict,
        strategy: ResolutionStrategy = ResolutionStrategy.SAFETY_FIRST,
        agent_confidences: Optional[Dict[str, float]] = None,
    ) -> Resolution:
        """Resolve a conflict between agents.

        Args:
            conflict: The conflict to resolve.
            strategy: Resolution strategy to apply.
            agent_confidences: Optional confidence scores per agent.

        Returns:
            Resolution with final decision.
        """
        if not self._initialized:
            raise RuntimeError("ConflictResolver not initialized")

        if strategy == ResolutionStrategy.HIGHEST_CONFIDENCE:
            return self._resolve_by_confidence(conflict, agent_confidences or {})
        elif strategy == ResolutionStrategy.SAFETY_FIRST:
            return self._resolve_safety_first(conflict)
        elif strategy == ResolutionStrategy.RULE_BASED:
            return self._resolve_by_rules(conflict)
        elif strategy == ResolutionStrategy.ESCALATION:
            return self._resolve_escalation(conflict)
        else:
            return self._resolve_safety_first(conflict)

    def _resolve_by_confidence(
        self, conflict: Conflict, confidences: Dict[str, float],
    ) -> Resolution:
        """Resolve by picking the agent with higher confidence.

        Args:
            conflict: The conflict.
            confidences: Confidence scores per agent.

        Returns:
            Resolution.
        """
        conf_a = confidences.get(conflict.agent_a_id, 0.5)
        conf_b = confidences.get(conflict.agent_b_id, 0.5)

        if conf_a >= conf_b:
            winner = conflict.agent_a_id
            loser = conflict.agent_b_id
            decision = conflict.agent_a_position
        else:
            winner = conflict.agent_b_id
            loser = conflict.agent_a_id
            decision = conflict.agent_b_position

        resolution = Resolution(
            conflict_id=conflict.conflict_id,
            strategy=ResolutionStrategy.HIGHEST_CONFIDENCE,
            winning_agent_id=winner,
            final_decision=decision,
            overridden_agent_id=loser,
            rationale=f"Agent '{winner}' had higher confidence ({max(conf_a, conf_b):.2f}) "
                      f"vs '{loser}' ({min(conf_a, conf_b):.2f})",
        )
        self._resolutions[resolution.resolution_id] = resolution
        return resolution

    def _resolve_safety_first(self, conflict: Conflict) -> Resolution:
        """Resolve by picking the most conservative/safe position.

        For financial decisions, this means: HALT > REDUCE > HOLD > BUY.

        Args:
            conflict: The conflict.

        Returns:
            Resolution.
        """
        # Safety ordering: HALT/REJECT is safest
        safety_order = {
            "HALT": 0, "REJECT": 0, "STOP": 0,
            "REDUCE": 1, "SELL": 1, "DECREASE": 1,
            "HOLD": 2, "WAIT": 2,
            "BUY": 3, "INCREASE": 3, "APPROVE": 3,
        }

        pos_a_str = str(conflict.agent_a_position).upper()
        pos_b_str = str(conflict.agent_b_position).upper()

        rank_a = safety_order.get(pos_a_str, 2)  # Default to HOLD
        rank_b = safety_order.get(pos_b_str, 2)

        if rank_a <= rank_b:
            winner = conflict.agent_a_id
            loser = conflict.agent_b_id
            decision = conflict.agent_a_position
        else:
            winner = conflict.agent_b_id
            loser = conflict.agent_a_id
            decision = conflict.agent_b_position

        resolution = Resolution(
            conflict_id=conflict.conflict_id,
            strategy=ResolutionStrategy.SAFETY_FIRST,
            winning_agent_id=winner,
            final_decision=decision,
            overridden_agent_id=loser,
            rationale=f"Safety-first: '{winner}' position is more conservative than '{loser}'",
        )
        self._resolutions[resolution.resolution_id] = resolution
        return resolution

    def _resolve_by_rules(self, conflict: Conflict) -> Resolution:
        """Resolve using predefined rules.

        Args:
            conflict: The conflict.

        Returns:
            Resolution. Falls back to safety-first if no rule matches.
        """
        for rule in self._rules:
            try:
                if rule["condition"](conflict):
                    winner_field = rule["winner"]
                    if winner_field == "agent_a":
                        winner = conflict.agent_a_id
                        loser = conflict.agent_b_id
                        decision = conflict.agent_a_position
                    else:
                        winner = conflict.agent_b_id
                        loser = conflict.agent_a_id
                        decision = conflict.agent_b_position

                    resolution = Resolution(
                        conflict_id=conflict.conflict_id,
                        strategy=ResolutionStrategy.RULE_BASED,
                        winning_agent_id=winner,
                        final_decision=decision,
                        overridden_agent_id=loser,
                        rationale=f"Rule '{rule['id']}': {rule['description']}",
                    )
                    self._resolutions[resolution.resolution_id] = resolution
                    logger.debug("Conflict resolved by rule: %s", rule["id"])
                    return resolution
            except Exception:
                logger.exception("Rule evaluation failed: %s", rule.get("id"))
                continue

        # Fall back to safety-first
        logger.debug("No rule matched, falling back to safety-first")
        return self._resolve_safety_first(conflict)

    def _resolve_escalation(self, conflict: Conflict) -> Resolution:
        """Escalate the conflict for coordinator decision.

        Args:
            conflict: The conflict.

        Returns:
            Resolution with escalation flag.
        """
        resolution = Resolution(
            conflict_id=conflict.conflict_id,
            strategy=ResolutionStrategy.ESCALATION,
            winning_agent_id="",
            final_decision=None,
            rationale="Conflict escalated to coordinator for manual resolution",
            escalated=True,
        )
        self._resolutions[resolution.resolution_id] = resolution
        logger.warning("Conflict escalated: %s", conflict.conflict_id)
        return resolution

    # ── Severity ──

    def _calculate_severity(
        self, position_a: Any, position_b: Any, conflict_type: ConflictType,
    ) -> float:
        """Calculate the severity of a conflict.

        Args:
            position_a: First position.
            position_b: Second position.
            conflict_type: Type of conflict.

        Returns:
            Severity score (0.0 - 1.0).
        """
        base_severity = 0.5

        # Constraint violations are severe
        if conflict_type == ConflictType.CONSTRAINT_VIOLATION:
            base_severity = 0.9
        elif conflict_type == ConflictType.OPINION_DIVERGENCE:
            # Opposite positions (BUY vs SELL) are more severe
            pos_a_str = str(position_a).upper()
            pos_b_str = str(position_b).upper()
            opposites = [
                {"BUY", "SELL"},
                {"BUY", "HALT"},
                {"APPROVE", "REJECT"},
            ]
            if {pos_a_str, pos_b_str} in opposites:
                base_severity = 0.8

        return min(max(base_severity, 0.0), 1.0)

    # ── Query ──

    def get_resolution(self, resolution_id: str) -> Optional[Resolution]:
        """Get a resolution by ID.

        Args:
            resolution_id: The resolution identifier.

        Returns:
            The resolution, or None if not found.
        """
        return self._resolutions.get(resolution_id)

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the conflict resolver state.

        Returns:
            Dict with resolution count and rules.
        """
        return {
            "initialized": self._initialized,
            "total_resolutions": len(self._resolutions),
            "rules_loaded": len(self._rules),
        }
