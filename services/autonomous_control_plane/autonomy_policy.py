"""
Autonomy Policy — Policy rules specifically for autonomy governance.

Defines conditions under which autonomy levels can be granted,
maintained, or revoked.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AutonomyPolicyRule:
    """A rule governing autonomy transitions."""

    def __init__(
        self,
        rule_id: str,
        description: str,
        check_fn,
        severity: str = "hard",
    ):
        self.rule_id = rule_id
        self.description = description
        self.check_fn = check_fn
        self.severity = severity

    def evaluate(self, context: dict) -> tuple[bool, str]:
        """Evaluate the rule. Returns (passed, reason)."""
        try:
            return self.check_fn(context)
        except Exception as e:
            return False, f"Evaluation error: {e}"


class AutonomyPolicy:
    """
    Defines the policy rules for autonomy level governance.

    Rules for promotion, demotion, and maintaining autonomy levels.
    """

    def __init__(self):
        self._promotion_rules: list[AutonomyPolicyRule] = []
        self._demotion_rules: list[AutonomyPolicyRule] = []
        self._maintenance_rules: list[AutonomyPolicyRule] = []
        self._init_default_rules()

    def _init_default_rules(self):
        """Initialize default autonomy policy rules."""
        # Promotion requirements
        self._promotion_rules.append(AutonomyPolicyRule(
            "promo_performance",
            "Must meet performance threshold",
            lambda ctx: (
                ctx.get("performance_sharpe", 0) >= 0.5,
                f"Sharpe {ctx.get('performance_sharpe', 0)} below 0.5",
            ),
        ))

        self._promotion_rules.append(AutonomyPolicyRule(
            "promo_robustness",
            "Must demonstrate robustness period",
            lambda ctx: (
                ctx.get("days_stable", 0) >= 30,
                f"Only {ctx.get('days_stable', 0)} days stable, need 30",
            ),
        ))

        self._promotion_rules.append(AutonomyPolicyRule(
            "promo_risk",
            "Risk metrics within bounds",
            lambda ctx: (
                ctx.get("max_drawdown", 1.0) <= 0.25,
                f"Drawdown {ctx.get('max_drawdown', 1.0)} exceeds 25%",
            ),
        ))

        # Demotion triggers
        self._demotion_rules.append(AutonomyPolicyRule(
            "demo_performance_decay",
            "Performance decay detected",
            lambda ctx: (
                ctx.get("sharpe_decay", 0) <= 0.3,
                f"Sharpe decay {ctx.get('sharpe_decay', 0)} > 30%",
            ),
        ))

        self._demotion_rules.append(AutonomyPolicyRule(
            "demo_risk_breach",
            "Risk limits breached",
            lambda ctx: (
                not ctx.get("risk_breach", False),
                "Risk limit breached",
            ),
        ))

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate_promotion(self, context: dict) -> tuple[bool, list[str]]:
        """Check if promotion rules are satisfied."""
        failures = []
        for rule in self._promotion_rules:
            ok, reason = rule.evaluate(context)
            if not ok:
                failures.append(f"{rule.rule_id}: {reason}")
        return len(failures) == 0, failures

    def evaluate_demotion(self, context: dict) -> tuple[bool, list[str]]:
        """Check if any demotion rules are triggered."""
        triggers = []
        for rule in self._demotion_rules:
            ok, reason = rule.evaluate(context)
            if not ok:
                triggers.append(f"{rule.rule_id}: {reason}")
        return len(triggers) > 0, triggers

    # ------------------------------------------------------------------
    # Rule Management
    # ------------------------------------------------------------------

    def add_promotion_rule(self, rule: AutonomyPolicyRule):
        self._promotion_rules.append(rule)

    def add_demotion_rule(self, rule: AutonomyPolicyRule):
        self._demotion_rules.append(rule)

    def add_maintenance_rule(self, rule: AutonomyPolicyRule):
        self._maintenance_rules.append(rule)

    def stats(self) -> dict:
        return {
            "promotion_rules": len(self._promotion_rules),
            "demotion_rules": len(self._demotion_rules),
            "maintenance_rules": len(self._maintenance_rules),
        }
