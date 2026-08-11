"""
Evolution Controller — Boundary and governance controller for autonomous evolution.

Enforces autonomy levels, safety constraints, and operational boundaries:
    - Max generations / population limits
    - Compute budget enforcement
    - Risk guard integration
    - Promotion gate control
    - Evolution policy validation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class AutonomyLevel(Enum):
    """Autonomy level for evolution operations."""

    LEVEL_0 = 0  # Manual — human approves every generation
    LEVEL_1 = 1  # Supervised — auto-evolve but human reviews
    LEVEL_2 = 2  # Guided — auto with policy constraints
    LEVEL_3 = 3  # Autonomous — full auto within budget
    LEVEL_4 = 4  # Unrestricted — no limits (dangerous, not recommended)


class ControllerAction(Enum):
    ALLOW = "allow"
    BLOCK = "block"
    FLAG = "flag"
    THROTTLE = "throttle"
    REQUIRE_APPROVAL = "require_approval"


@dataclass
class ControllerRule:
    """A single boundary rule."""

    rule_id: str
    description: str
    action: ControllerAction
    condition: Dict[str, Any] = field(default_factory=dict)
    min_autonomy_level: AutonomyLevel = AutonomyLevel.LEVEL_1
    enabled: bool = True


@dataclass
class ControllerConfig:
    """Configuration for the evolution controller."""

    autonomy_level: AutonomyLevel = AutonomyLevel.LEVEL_2
    max_population: int = 10000
    max_generations: int = 500
    max_mutation_rate: float = 0.50
    max_crossover_rate: float = 0.50
    max_backtests_per_run: int = 50000
    max_compute_hours_per_run: float = 72.0
    min_fitness_for_promotion: float = 0.25
    max_correlation_for_promotion: float = 0.80
    require_human_approval_for_promotion: bool = True
    block_high_leverage_alphas: bool = True
    max_leverage: float = 2.0


class EvolutionController:
    """
    Governance boundary for autonomous evolution.

    Enforces:
        - Autonomy level permissions
        - Resource limits (population, generations, compute)
        - Safety constraints (leverage, correlation)
        - Human-in-the-loop gates
        - Audit logging of all control decisions
    """

    def __init__(self, config: Optional[ControllerConfig] = None):
        self._config = config or ControllerConfig()
        self._rules: List[ControllerRule] = []
        self._action_log: List[Dict[str, Any]] = []
        self._register_default_rules()

    def _register_default_rules(self) -> None:
        """Register default safety and boundary rules."""
        self._rules = [
            ControllerRule(
                rule_id="max_population",
                description="Enforce maximum population size",
                action=ControllerAction.THROTTLE,
                min_autonomy_level=AutonomyLevel.LEVEL_0,
            ),
            ControllerRule(
                rule_id="max_generations",
                description="Enforce maximum generation count",
                action=ControllerAction.BLOCK,
                min_autonomy_level=AutonomyLevel.LEVEL_0,
            ),
            ControllerRule(
                rule_id="max_compute_hours",
                description="Enforce maximum compute hours per run",
                action=ControllerAction.BLOCK,
                min_autonomy_level=AutonomyLevel.LEVEL_0,
            ),
            ControllerRule(
                rule_id="high_leverage_alpha",
                description="Block alphas with excessive leverage",
                action=ControllerAction.BLOCK,
                min_autonomy_level=AutonomyLevel.LEVEL_3,
            ),
            ControllerRule(
                rule_id="promotion_approval",
                description="Require human approval for production promotion",
                action=ControllerAction.REQUIRE_APPROVAL,
                min_autonomy_level=AutonomyLevel.LEVEL_4,
            ),
            ControllerRule(
                rule_id="max_mutation_rate",
                description="Cap mutation rate to prevent excessive drift",
                action=ControllerAction.THROTTLE,
                min_autonomy_level=AutonomyLevel.LEVEL_0,
            ),
            ControllerRule(
                rule_id="max_crossover_rate",
                description="Cap crossover rate",
                action=ControllerAction.THROTTLE,
                min_autonomy_level=AutonomyLevel.LEVEL_0,
            ),
            ControllerRule(
                rule_id="fitness_threshold",
                description="Reject candidates below minimum fitness",
                action=ControllerAction.BLOCK,
                min_autonomy_level=AutonomyLevel.LEVEL_0,
            ),
            ControllerRule(
                rule_id="correlation_cap",
                description="Reject candidates with excessive correlation to existing",
                action=ControllerAction.FLAG,
                min_autonomy_level=AutonomyLevel.LEVEL_1,
            ),
        ]

    # ── Control Methods ────────────────────────────────────

    async def check_population_limit(
        self, current_size: int, proposed_addition: int
    ) -> ControllerAction:
        """Check if population can be expanded."""
        if current_size + proposed_addition > self._config.max_population:
            self._log_action("max_population", ControllerAction.THROTTLE,
                             f"Population {current_size + proposed_addition} exceeds max {self._config.max_population}")
            return ControllerAction.THROTTLE
        return ControllerAction.ALLOW

    async def check_generation_limit(self, current_gen: int) -> ControllerAction:
        """Check if generation limit has been reached."""
        if current_gen >= self._config.max_generations:
            self._log_action("max_generations", ControllerAction.BLOCK,
                             f"Generation {current_gen} >= max {self._config.max_generations}")
            return ControllerAction.BLOCK
        return ControllerAction.ALLOW

    async def check_compute_budget(self, hours_used: float) -> ControllerAction:
        """Check compute budget."""
        if hours_used >= self._config.max_compute_hours_per_run:
            self._log_action("max_compute_hours", ControllerAction.BLOCK,
                             f"Compute {hours_used:.1f}h >= max {self._config.max_compute_hours_per_run}h")
            return ControllerAction.BLOCK
        return ControllerAction.ALLOW

    async def check_mutation_rate(self, rate: float) -> ControllerAction:
        """Cap mutation rate."""
        if rate > self._config.max_mutation_rate:
            self._log_action("max_mutation_rate", ControllerAction.THROTTLE,
                             f"Mutation rate {rate} > max {self._config.max_mutation_rate}")
            return ControllerAction.THROTTLE
        return ControllerAction.ALLOW

    async def check_crossover_rate(self, rate: float) -> ControllerAction:
        """Cap crossover rate."""
        if rate > self._config.max_crossover_rate:
            self._log_action("max_crossover_rate", ControllerAction.THROTTLE,
                             f"Crossover rate {rate} > max {self._config.max_crossover_rate}")
            return ControllerAction.THROTTLE
        return ControllerAction.ALLOW

    async def check_fitness_for_promotion(self, fitness: float) -> ControllerAction:
        """Check if candidate meets minimum fitness for promotion."""
        if fitness < self._config.min_fitness_for_promotion:
            self._log_action("fitness_threshold", ControllerAction.BLOCK,
                             f"Fitness {fitness} < min {self._config.min_fitness_for_promotion}")
            return ControllerAction.BLOCK
        return ControllerAction.ALLOW

    async def check_correlation_for_promotion(
        self, correlation: float, existing_ids: List[str]
    ) -> ControllerAction:
        """Check if candidate is too correlated with existing."""
        if correlation > self._config.max_correlation_for_promotion:
            self._log_action("correlation_cap", ControllerAction.FLAG,
                             f"Correlation {correlation} > max {self._config.max_correlation_for_promotion}")
            return ControllerAction.FLAG
        return ControllerAction.ALLOW

    async def check_leverage(
        self, leverage: float, autonomy: AutonomyLevel
    ) -> ControllerAction:
        """Check leverage constraints."""
        if (
            self._config.block_high_leverage_alphas
            and leverage > self._config.max_leverage
            and autonomy.value < AutonomyLevel.LEVEL_4.value
        ):
            self._log_action("high_leverage_alpha", ControllerAction.BLOCK,
                             f"Leverage {leverage} > max {self._config.max_leverage}")
            return ControllerAction.BLOCK
        return ControllerAction.ALLOW

    async def check_promotion_needs_approval(self) -> ControllerAction:
        """Check if human approval is required for promotion."""
        if self._config.require_human_approval_for_promotion:
            return ControllerAction.REQUIRE_APPROVAL
        return ControllerAction.ALLOW

    async def validate_operation(
        self,
        operation: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Comprehensive validation of an evolution operation."""
        results: Dict[str, ControllerAction] = {}

        if operation == "start_generation":
            results["generation_limit"] = await self.check_generation_limit(
                params.get("current_generation", 0)
            )
            results["compute_budget"] = await self.check_compute_budget(
                params.get("compute_hours_used", 0)
            )
        elif operation == "mutate":
            results["mutation_rate"] = await self.check_mutation_rate(
                params.get("mutation_rate", self._config.max_mutation_rate)
            )
        elif operation == "crossover":
            results["crossover_rate"] = await self.check_crossover_rate(
                params.get("crossover_rate", self._config.max_crossover_rate)
            )
        elif operation == "promote":
            results["fitness"] = await self.check_fitness_for_promotion(
                params.get("fitness", 0)
            )
            results["correlation"] = await self.check_correlation_for_promotion(
                params.get("correlation", 0),
                params.get("existing_ids", []),
            )
            results["approval"] = await self.check_promotion_needs_approval()

        blocked = any(a == ControllerAction.BLOCK for a in results.values())
        return {
            "allowed": not blocked,
            "actions": {k: v.value for k, v in results.items()},
            "blocked": blocked,
        }

    # ── Logging ────────────────────────────────────────────

    def _log_action(
        self, rule_id: str, action: ControllerAction, reason: str
    ) -> None:
        entry = {"rule_id": rule_id, "action": action.value, "reason": reason}
        self._action_log.append(entry)
        logger.info("Controller %s → %s: %s", rule_id, action.value, reason)

    def get_action_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._action_log[-limit:]

    # ── Accessors ──────────────────────────────────────────

    @property
    def autonomy_level(self) -> AutonomyLevel:
        return self._config.autonomy_level

    async def set_autonomy_level(self, level: AutonomyLevel) -> None:
        old = self._config.autonomy_level
        self._config.autonomy_level = level
        logger.warning("Autonomy level changed %s → %s", old.value, level.value)

    def get_config(self) -> Dict[str, Any]:
        return {
            "autonomy_level": self._config.autonomy_level.value,
            "max_population": self._config.max_population,
            "max_generations": self._config.max_generations,
            "max_mutation_rate": self._config.max_mutation_rate,
            "max_crossover_rate": self._config.max_crossover_rate,
            "max_compute_hours": self._config.max_compute_hours_per_run,
            "min_fitness_promotion": self._config.min_fitness_for_promotion,
            "require_approval": self._config.require_human_approval_for_promotion,
        }
