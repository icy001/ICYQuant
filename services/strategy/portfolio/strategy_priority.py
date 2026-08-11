"""
Strategy Priority Manager
=========================
Manages strategy priority levels and resolution rules for
cross-strategy decision ordering.

Supports:
- Priority level assignment (CRITICAL > HIGH > MEDIUM > LOW)
- Dynamic priority rules based on performance
- Priority-based execution ordering
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class PriorityLevel(IntEnum):
    """Priority levels for strategies (higher = more important)."""

    CRITICAL = 100
    HIGH = 75
    MEDIUM_HIGH = 60
    MEDIUM = 50
    MEDIUM_LOW = 40
    LOW = 25
    BACKGROUND = 10
    DEPRECATED = 0


@dataclass
class PriorityRule:
    """A rule for dynamically adjusting strategy priority."""

    rule_id: str = ""
    description: str = ""

    # Conditions
    min_confidence: Optional[float] = None
    min_win_rate: Optional[float] = None
    min_sharpe: Optional[float] = None
    min_track_record_days: Optional[int] = None
    strategy_type_filter: Optional[List[str]] = None

    # Effect
    priority_boost: int = 0
    priority_penalty: int = 0

    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class StrategyPriorityManager:
    """
    Strategy Priority Manager.

    Assigns and manages priority levels for strategies, influencing
    execution order and conflict resolution.

    Priority determines:
    - Which strategy's signal wins in conflicts
    - Order of capital allocation
    - Execution priority in OMS
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._initialized = False

        # Base priority assignments: strategy_id → PriorityLevel
        self._base_priorities: Dict[str, PriorityLevel] = {}

        # Dynamic rules
        self._rules: List[PriorityRule] = []

        # Strategy performance metrics for dynamic evaluation
        self._strategy_performance: Dict[str, Dict[str, Any]] = {}

        # Metrics
        self._metrics: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return

        # Load base priorities
        priorities_config = self._config.get("priorities", {})
        for sid, level in priorities_config.items():
            try:
                if isinstance(level, int):
                    self._base_priorities[sid] = PriorityLevel(level)
                elif isinstance(level, str):
                    self._base_priorities[sid] = PriorityLevel[level.upper()]
            except (ValueError, KeyError):
                logger.warning("Invalid priority for %s: %s", sid, level)

        # Load dynamic rules
        rules_config = self._config.get("rules", [])
        for rconfig in rules_config:
            rule = PriorityRule(
                rule_id=rconfig.get("rule_id", ""),
                description=rconfig.get("description", ""),
                min_confidence=rconfig.get("min_confidence"),
                min_win_rate=rconfig.get("min_win_rate"),
                min_sharpe=rconfig.get("min_sharpe"),
                min_track_record_days=rconfig.get("min_track_record_days"),
                strategy_type_filter=rconfig.get("strategy_type_filter"),
                priority_boost=rconfig.get("priority_boost", 0),
                priority_penalty=rconfig.get("priority_penalty", 0),
                enabled=rconfig.get("enabled", True),
            )
            self._rules.append(rule)

        self._initialized = True
        logger.info(
            "StrategyPriorityManager initialized (%d base priorities, %d rules)",
            len(self._base_priorities),
            len(self._rules),
        )

    async def shutdown(self) -> None:
        self._base_priorities.clear()
        self._rules.clear()
        self._strategy_performance.clear()
        self._initialized = False
        logger.info("StrategyPriorityManager shut down")

    # ------------------------------------------------------------------
    # Priority Management
    # ------------------------------------------------------------------

    def set_priority(self, strategy_id: str, level: PriorityLevel) -> None:
        """Set the base priority for a strategy."""
        self._base_priorities[strategy_id] = level
        logger.debug("Priority set: %s → %s", strategy_id, level.name)

    def get_base_priority(self, strategy_id: str) -> PriorityLevel:
        """Get the base priority for a strategy (defaults to MEDIUM)."""
        return self._base_priorities.get(strategy_id, PriorityLevel.MEDIUM)

    def update_performance(
        self,
        strategy_id: str,
        metrics: Dict[str, Any],
    ) -> None:
        """Update strategy performance metrics for dynamic priority evaluation."""
        self._strategy_performance[strategy_id] = {
            **(self._strategy_performance.get(strategy_id, {})),
            **metrics,
        }

    def _evaluate_rules(
        self,
        strategy_id: str,
        strategy_type: str = "",
    ) -> int:
        """Evaluate dynamic rules and return priority adjustment."""
        perf = self._strategy_performance.get(strategy_id, {})
        adjustment = 0

        for rule in self._rules:
            if not rule.enabled:
                continue

            # Check type filter
            if rule.strategy_type_filter and strategy_type not in rule.strategy_type_filter:
                continue

            # Check conditions
            conditions_met = True

            if rule.min_confidence is not None:
                if perf.get("confidence", 0) < rule.min_confidence:
                    conditions_met = False

            if rule.min_win_rate is not None:
                if perf.get("win_rate", 0) < rule.min_win_rate:
                    conditions_met = False

            if rule.min_sharpe is not None:
                if perf.get("sharpe", 0) < rule.min_sharpe:
                    conditions_met = False

            if rule.min_track_record_days is not None:
                if perf.get("track_record_days", 0) < rule.min_track_record_days:
                    conditions_met = False

            if conditions_met:
                adjustment += rule.priority_boost
            elif rule.priority_penalty > 0:
                adjustment -= rule.priority_penalty

        return adjustment

    def get_effective_priority(
        self,
        strategy_id: str,
        strategy_type: str = "",
    ) -> PriorityLevel:
        """
        Get the effective priority after applying dynamic rules.

        Priority is clamped to [DEPRECATED, CRITICAL] range.
        """
        base = self.get_base_priority(strategy_id).value
        adjustment = self._evaluate_rules(strategy_id, strategy_type)
        effective = max(
            PriorityLevel.DEPRECATED.value,
            min(PriorityLevel.CRITICAL.value, base + adjustment),
        )
        return PriorityLevel(effective)

    # ------------------------------------------------------------------
    # Prioritization
    # ------------------------------------------------------------------

    async def prioritize(
        self,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Sort candidates by effective priority (highest first).

        Args:
            candidates: List of position/allocation dicts with strategy_id.

        Returns:
            Priority-sorted list of candidates.
        """
        if not self._initialized:
            await self.initialize()

        # Compute effective priorities
        for c in candidates:
            sid = c.get("strategy_id", "")
            stype = c.get("strategy_type", c.get("metadata", {}).get("strategy_type", ""))
            effective = self.get_effective_priority(sid, stype)
            c["priority"] = effective.value
            c["priority_level"] = effective.name

        # Sort by priority (descending), then confidence (descending)
        candidates.sort(
            key=lambda c: (
                -c.get("priority", PriorityLevel.MEDIUM.value),
                -c.get("confidence", 0.0),
            )
        )

        self._metrics["prioritized_total"] = self._metrics.get("prioritized_total", 0) + len(candidates)

        return candidates

    # ------------------------------------------------------------------
    # Rule Management
    # ------------------------------------------------------------------

    def add_rule(self, rule: PriorityRule) -> None:
        self._rules.append(rule)
        logger.debug("Priority rule added: %s", rule.rule_id)

    def remove_rule(self, rule_id: str) -> bool:
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.rule_id != rule_id]
        return len(self._rules) < before

    def list_rules(self) -> List[PriorityRule]:
        return list(self._rules)

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, Any]:
        return dict(self._metrics)

    @property
    def is_initialized(self) -> bool:
        return self._initialized
