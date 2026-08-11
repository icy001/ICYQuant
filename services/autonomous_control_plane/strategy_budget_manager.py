"""
Strategy Budget Manager — Controls strategy evolution resource limits.

Prevents strategy explosion by limiting population size, generation
count, mutation/crossover operations, and total compute cost.
"""

from __future__ import annotations

import time
import logging

logger = logging.getLogger(__name__)


class StrategyBudgetManager:
    """
    Enforces limits on strategy generation and evolution.

    Controls:
    - Population size limits
    - Generation count per day
    - Mutation and crossover operations
    - Total compute cost for strategy evolution
    """

    def __init__(
        self,
        max_population: int = 200,
        max_generations_per_day: int = 100,
        max_mutations_per_day: int = 500,
        max_crossovers_per_day: int = 500,
        max_compute_cost: float = 50.0,
    ):
        self._max_population = max_population
        self._max_generations = max_generations_per_day
        self._max_mutations = max_mutations_per_day
        self._max_crossovers = max_crossovers_per_day
        self._max_cost = max_compute_cost

        self._generations_used = 0
        self._mutations_used = 0
        self._crossovers_used = 0
        self._cost_used = 0.0

        self._last_reset = time.time()
        self._reset_interval = 86400

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------

    def check_population(self, current_size: int) -> tuple[bool, str]:
        if current_size >= self._max_population:
            return False, f"Population at capacity ({current_size}/{self._max_population})"
        return True, ""

    def can_generate(self) -> tuple[bool, str]:
        self._maybe_reset()
        if self._generations_used >= self._max_generations:
            return False, "Generation limit reached"
        if self._cost_used >= self._max_cost:
            return False, "Compute cost limit reached"
        return True, ""

    def can_mutate(self) -> tuple[bool, str]:
        self._maybe_reset()
        if self._mutations_used >= self._max_mutations:
            return False, "Mutation limit reached"
        return True, ""

    def can_crossover(self) -> tuple[bool, str]:
        self._maybe_reset()
        if self._crossovers_used >= self._max_crossovers:
            return False, "Crossover limit reached"
        return True, ""

    # ------------------------------------------------------------------
    # Consumption
    # ------------------------------------------------------------------

    def consume_generation(self, cost: float = 0.5):
        self._maybe_reset()
        self._generations_used += 1
        self._cost_used += cost

    def consume_mutation(self, cost: float = 0.1):
        self._maybe_reset()
        self._mutations_used += 1
        self._cost_used += cost

    def consume_crossover(self, cost: float = 0.1):
        self._maybe_reset()
        self._crossovers_used += 1
        self._cost_used += cost

    def _maybe_reset(self):
        if time.time() - self._last_reset >= self._reset_interval:
            self._generations_used = 0
            self._mutations_used = 0
            self._crossovers_used = 0
            self._cost_used = 0.0
            self._last_reset = time.time()

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        self._maybe_reset()
        return {
            "population_limit": self._max_population,
            "generations": {"used": self._generations_used, "limit": self._max_generations},
            "mutations": {"used": self._mutations_used, "limit": self._max_mutations},
            "crossovers": {"used": self._crossovers_used, "limit": self._max_crossovers},
            "compute_cost": {"used": self._cost_used, "limit": self._max_cost},
        }
