"""StressGuard — stress-based pre-execution gate.

If a proposed allocation fails stress tests, the allocation
must be adjusted before execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.institutional_risk.stress_engine import StressResult, StressScenario


@dataclass
class StressGuardCheck:
    """A single stress scenario check."""

    scenario_name: str
    loss_pct: float
    survival_under_stress: float
    passed: bool
    limit: float
    reason: str


@dataclass
class StressGuardResult:
    """Stress guard result."""

    allowed: bool = True
    checks: List[StressGuardCheck] = field(default_factory=list)
    failed_scenarios: List[str] = field(default_factory=list)
    worst_loss_pct: float = 0.0
    worst_survival: float = 100.0
    required_adjustment: str = ""


class StressGuard:
    """Pre-execution stress guard.

    Usage::

        guard = StressGuard(stress_loss_limit=20.0)
        result = guard.check(stress_results)
        if not result.allowed:
            print(f"FAILED: {result.failed_scenarios}")
    """

    def __init__(
        self,
        stress_loss_limit_pct: float = 25.0,
        stress_survival_limit: float = 50.0,
    ):
        self._loss_limit = stress_loss_limit_pct
        self._survival_limit = stress_survival_limit

    def check(
        self,
        stress_results: List[StressResult],
    ) -> StressGuardResult:
        """Check stress test results against limits.

        Args:
            stress_results: results from running stress scenarios
        """
        checks: List[StressGuardCheck] = []
        failed: List[str] = []
        worst_loss = 0.0
        worst_survival = 100.0

        for result in stress_results:
            loss_pct = abs(result.portfolio_loss_pct)
            survival = result.survival_score_under_stress

            passed = loss_pct <= self._loss_limit and survival >= self._survival_limit

            check = StressGuardCheck(
                scenario_name=result.scenario_name,
                loss_pct=loss_pct,
                survival_under_stress=survival,
                passed=passed,
                limit=self._loss_limit,
                reason=(
                    "OK" if passed
                    else (
                        f"Loss {loss_pct:.1f}% > {self._loss_limit}% or "
                        f"Survival {survival:.0f} < {self._survival_limit}"
                    )
                ),
            )
            checks.append(check)

            if not passed:
                failed.append(result.scenario_name)

            if loss_pct > worst_loss:
                worst_loss = loss_pct
            if survival < worst_survival:
                worst_survival = survival

        allowed = len(failed) == 0

        adjustment = ""
        if not allowed:
            adjustment = (
                f"Reduce risk exposure: {len(failed)}/{len(stress_results)} "
                f"scenarios fail. Worst loss: {worst_loss:.1f}%"
            )

        return StressGuardResult(
            allowed=allowed,
            checks=checks,
            failed_scenarios=failed,
            worst_loss_pct=worst_loss,
            worst_survival=worst_survival,
            required_adjustment=adjustment,
        )
