"""SurvivalGuard — capital survival gate before any major action.

The most important guard: if an action reduces survival below
the minimum threshold, it is REJECTED regardless of returns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SurvivalGuardCheck:
    """A single survival check."""

    check_type: str
    pre_action_score: float
    post_action_score: float
    change: float
    passed: bool
    threshold: float
    reason: str


@dataclass
class SurvivalGuardResult:
    """Survival guard check result."""

    allowed: bool = True
    checks: List[SurvivalGuardCheck] = field(default_factory=list)
    min_post_score: float = 100.0
    survival_drop: float = 0.0
    reason: str = ""


class SurvivalGuard:
    """Pre-action survival check.

    Before any major capital action, check:
    1. Current survival score
    2. Post-trade survival score
    3. Stress survival score
    4. Liquidity survival
    5. Recovery capacity

    Rule: Post-trade survival < minimum → REJECT

    Usage::

        guard = SurvivalGuard()
        result = guard.check(
            pre_action={"score": 78, "stress": 65},
            post_action_estimate={"score": 72, "stress": 60},
        )
        if not result.allowed:
            print(f"REJECTED: {result.reason}")
    """

    def __init__(
        self,
        min_survival_threshold: float = 70.0,
        max_survival_drop: float = 15.0,
        min_stress_survival: float = 50.0,
    ):
        self._min_survival = min_survival_threshold
        self._max_drop = max_survival_drop
        self._min_stress = min_stress_survival

    def check(
        self,
        pre_action: Dict[str, float],
        post_action_estimate: Dict[str, float],
        action_description: str = "",
    ) -> SurvivalGuardResult:
        """Check if action passes survival guard.

        Args:
            pre_action: {"score": float, "stress": float, "liquidity": float, "recovery": float}
            post_action_estimate: same format, estimated after action
            action_description: what action is being checked
        """
        checks: List[SurvivalGuardCheck] = []

        pre_score = pre_action.get("score", 100.0)
        post_score = post_action_estimate.get("score", 100.0)
        drop = pre_score - post_score

        # Check 1: absolute minimum
        checks.append(SurvivalGuardCheck(
            check_type="absolute_minimum",
            pre_action_score=pre_score,
            post_action_score=post_score,
            change=-drop,
            passed=post_score >= self._min_survival,
            threshold=self._min_survival,
            reason=(
                f"Post-trade survival {post_score:.0f} >= {self._min_survival}"
                if post_score >= self._min_survival
                else f"Post-trade survival {post_score:.0f} < minimum {self._min_survival}"
            ),
        ))

        # Check 2: maximum drop
        checks.append(SurvivalGuardCheck(
            check_type="max_drop",
            pre_action_score=pre_score,
            post_action_score=post_score,
            change=-drop,
            passed=drop <= self._max_drop,
            threshold=self._max_drop,
            reason=(
                f"Survival drop {drop:.0f} <= max {self._max_drop}"
                if drop <= self._max_drop
                else f"Survival drop {drop:.0f} exceeds max {self._max_drop}"
            ),
        ))

        # Check 3: stress survival
        pre_stress = pre_action.get("stress", pre_score)
        post_stress = post_action_estimate.get("stress", post_score)
        checks.append(SurvivalGuardCheck(
            check_type="stress_survival",
            pre_action_score=pre_stress,
            post_action_score=post_stress,
            change=post_stress - pre_stress,
            passed=post_stress >= self._min_stress,
            threshold=self._min_stress,
            reason=(
                f"Stress survival {post_stress:.0f} >= {self._min_stress}"
                if post_stress >= self._min_stress
                else f"Stress survival {post_stress:.0f} < minimum {self._min_stress}"
            ),
        ))

        # Check 4: liquidity survival
        pre_liq = pre_action.get("liquidity", 100.0)
        post_liq = post_action_estimate.get("liquidity", 100.0)
        checks.append(SurvivalGuardCheck(
            check_type="liquidity_survival",
            pre_action_score=pre_liq,
            post_action_score=post_liq,
            change=post_liq - pre_liq,
            passed=post_liq >= 40.0,
            threshold=40.0,
            reason="OK" if post_liq >= 40 else f"Liquidity survival {post_liq:.0f} too low",
        ))

        # Check 5: recovery capacity
        pre_rec = pre_action.get("recovery", 1.0)
        post_rec = post_action_estimate.get("recovery", 1.0)
        checks.append(SurvivalGuardCheck(
            check_type="recovery_capacity",
            pre_action_score=pre_rec,
            post_action_score=post_rec,
            change=post_rec - pre_rec,
            passed=post_rec >= 0.3,
            threshold=0.3,
            reason="OK" if post_rec >= 0.3 else f"Recovery capacity {post_rec:.2f} too low",
        ))

        # overall decision
        all_passed = all(c.passed for c in checks)
        min_post = min(c.post_action_score for c in checks)

        reason = "All survival checks passed"
        if not all_passed:
            failed = [c.check_type for c in checks if not c.passed]
            reason = f"Failed: {', '.join(failed)}"

        return SurvivalGuardResult(
            allowed=all_passed,
            checks=checks,
            min_post_score=min_post,
            survival_drop=drop,
            reason=reason,
        )
