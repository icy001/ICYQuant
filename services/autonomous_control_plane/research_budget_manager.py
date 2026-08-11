"""
Research Budget Manager — Resource budget enforcement for autonomous research.

Prevents infinite research loops by enforcing compute, experiment,
strategy, and execution budgets.
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class BudgetStatus:
    """Result of a budget check."""
    allowed: bool
    remaining: float
    limit: float
    used: float
    reason: str = ""


class ResearchBudgetManager:
    """
    Central budget manager for all autonomous operations.

    Enforces resource budgets for:
    - Compute: CPU/GPU usage per day
    - Experiments: number of experiments per day
    - Strategy: strategy generation activity
    - Execution: capital/turnover limits
    """

    def __init__(
        self,
        compute_budget: float = 100.0,
        experiment_budget: int = 500,
        strategy_budget: int = 200,
        execution_budget: float = 1_000_000.0,
    ):
        self._compute_budget = compute_budget
        self._experiment_budget = experiment_budget
        self._strategy_budget = strategy_budget
        self._execution_budget = execution_budget

        self._compute_used = 0.0
        self._experiment_used = 0
        self._strategy_used = 0
        self._execution_used = 0.0

        self._last_reset = time.time()
        self._reset_interval = 86400  # Daily reset

    # ------------------------------------------------------------------
    # Budget Check
    # ------------------------------------------------------------------

    async def check(self, context) -> BudgetStatus:
        """Check all relevant budgets for a context."""
        self._maybe_reset()

        scope = getattr(context, "requested_scope", "default")
        action = getattr(context, "action", "")

        if scope == "research" or action == "run_research":
            return self._check_compute()
        if scope == "strategy" or action == "generate_strategy":
            return self._check_strategy()
        if scope == "execution" or action.startswith("exec"):
            return self._check_execution(context)

        # Composite check
        compute = self._check_compute()
        strategy = self._check_strategy()
        execution = self._check_execution(context)

        if not compute.allowed:
            return compute
        if not strategy.allowed:
            return strategy
        return execution

    def _check_compute(self) -> BudgetStatus:
        remaining = self._compute_budget - self._compute_used
        return BudgetStatus(
            allowed=remaining > 0,
            remaining=remaining,
            limit=self._compute_budget,
            used=self._compute_used,
            reason="compute budget exceeded" if remaining <= 0 else "",
        )

    def _check_strategy(self) -> BudgetStatus:
        remaining = self._strategy_budget - self._strategy_used
        return BudgetStatus(
            allowed=remaining > 0,
            remaining=remaining,
            limit=self._strategy_budget,
            used=self._strategy_used,
            reason="strategy budget exceeded" if remaining <= 0 else "",
        )

    def _check_execution(self, context) -> BudgetStatus:
        requested = getattr(context, "requested_capital", 0)
        remaining = self._execution_budget - self._execution_used
        return BudgetStatus(
            allowed=remaining >= requested,
            remaining=remaining,
            limit=self._execution_budget,
            used=self._execution_used,
            reason=f"execution budget exceeded (requested {requested}, remaining {remaining})" if remaining < requested else "",
        )

    # ------------------------------------------------------------------
    # Consumption
    # ------------------------------------------------------------------

    def consume_compute(self, units: float) -> bool:
        self._maybe_reset()
        if self._compute_used + units > self._compute_budget:
            return False
        self._compute_used += units
        return True

    def consume_experiment(self, count: int = 1) -> bool:
        self._maybe_reset()
        if self._experiment_used + count > self._experiment_budget:
            return False
        self._experiment_used += count
        return True

    def consume_strategy_generation(self, count: int = 1) -> bool:
        self._maybe_reset()
        if self._strategy_used + count > self._strategy_budget:
            return False
        self._strategy_used += count
        return True

    def consume_execution(self, amount: float) -> bool:
        self._maybe_reset()
        if self._execution_used + amount > self._execution_budget:
            return False
        self._execution_used += amount
        return True

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _maybe_reset(self):
        now = time.time()
        if now - self._last_reset >= self._reset_interval:
            self._compute_used = 0.0
            self._experiment_used = 0
            self._strategy_used = 0
            self._execution_used = 0.0
            self._last_reset = now
            logger.info("Budget reset")

    # ------------------------------------------------------------------
    # Dynamic Allocation
    # ------------------------------------------------------------------

    def allocate_by_value(self, scores: dict[str, float]) -> dict[str, float]:
        """Dynamically allocate budget based on research value scores."""
        total_score = sum(scores.values())
        if total_score == 0:
            return {k: 0 for k in scores}

        allocations = {}
        for domain, score in scores.items():
            weight = score / total_score
            if domain == "compute":
                allocations[domain] = weight * self._compute_budget
            elif domain == "strategy":
                allocations[domain] = weight * self._strategy_budget

        return allocations

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        self._maybe_reset()
        return {
            "compute": {"used": self._compute_used, "limit": self._compute_budget, "pct": self._compute_used / max(self._compute_budget, 1)},
            "experiment": {"used": self._experiment_used, "limit": self._experiment_budget, "pct": self._experiment_used / max(self._experiment_budget, 1)},
            "strategy": {"used": self._strategy_used, "limit": self._strategy_budget, "pct": self._strategy_used / max(self._strategy_budget, 1)},
            "execution": {"used": self._execution_used, "limit": self._execution_budget, "pct": self._execution_used / max(self._execution_budget, 1)},
        }
