"""
Policy Evaluator — Evaluates individual policy rules against decisions.

Each policy rule is a callable that evaluates a context and returns
an allowed/denied result with optional constraints.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Callable

logger = logging.getLogger(__name__)


class Rule:
    """A named rule used within a policy."""

    def __init__(
        self,
        rule_id: str,
        name: str,
        evaluator: Callable,
        description: str = "",
        severity: str = "hard",  # hard, soft, advisory
    ):
        self.rule_id = rule_id
        self.name = name
        self.evaluator = evaluator
        self.description = description
        self.severity = severity

    def evaluate(self, context) -> bool:
        """Evaluate the rule against a context. Returns True if compliant."""
        try:
            return self.evaluator(context)
        except Exception as e:
            logger.warning("Rule %s evaluation error: %s", self.rule_id, e)
            # On error, fail closed for hard rules, pass for advisory
            return self.severity != "hard"


class PolicyEvaluator:
    """
    Evaluates policy rules against a decision context.

    Supports:
    - Hard limits: fail-closed, evaluation error = violation
    - Soft limits: warnings logged but allowed
    - Advisory rules: informational only
    """

    def __init__(self):
        self._rules: dict[str, Rule] = {}

    def register(self, rule: Rule) -> None:
        self._rules[rule.rule_id] = rule

    def unregister(self, rule_id: str) -> None:
        self._rules.pop(rule_id, None)

    def evaluate_all(self, context) -> dict:
        """Evaluate all registered rules against a context."""
        results = {
            "passed": [],
            "warnings": [],
            "violations": [],
        }

        for rule in self._rules.values():
            try:
                ok = rule.evaluate(context)
                if ok:
                    results["passed"].append(rule.rule_id)
                elif rule.severity == "advisory":
                    results["warnings"].append({
                        "rule_id": rule.rule_id,
                        "name": rule.name,
                        "severity": rule.severity,
                    })
                elif rule.severity == "soft":
                    results["warnings"].append({
                        "rule_id": rule.rule_id,
                        "name": rule.name,
                        "severity": rule.severity,
                    })
                else:  # hard
                    results["violations"].append({
                        "rule_id": rule.rule_id,
                        "name": rule.name,
                        "description": rule.description,
                    })
            except Exception:
                if rule.severity == "hard":
                    results["violations"].append({
                        "rule_id": rule.rule_id,
                        "name": rule.name,
                        "error": "evaluation_failure",
                    })

        return results

    def is_compliant(self, context) -> tuple[bool, list]:
        """Quick check: is the context compliant with all hard rules?"""
        results = self.evaluate_all(context)
        return len(results["violations"]) == 0, results["violations"]


# ---------------------------------------------------------------------------
# Common Policy Rules
# ---------------------------------------------------------------------------

def max_exposure_rule(max_pct: float) -> Rule:
    """Create a maximum exposure rule."""
    return Rule(
        rule_id=f"max_exposure_{max_pct}",
        name=f"Max Exposure {max_pct*100}%",
        evaluator=lambda ctx: (
            getattr(ctx, "requested_capital", 0) / max(
                getattr(ctx, "portfolio_context", {}).get("nav", 1) if isinstance(ctx.portfolio_context, dict) else 1,
                1,
            )
        ) <= max_pct,
        description=f"Exposure must not exceed {max_pct*100}%",
        severity="hard",
    )


def max_drawdown_rule(max_dd: float) -> Rule:
    """Create a maximum drawdown rule."""
    return Rule(
        rule_id=f"max_drawdown_{max_dd}",
        name=f"Max Drawdown {max_dd*100}%",
        evaluator=lambda ctx: (
            getattr(ctx, "portfolio_context", {}).get("drawdown", 0) if isinstance(ctx.portfolio_context, dict) else 0
        ) <= max_dd,
        description=f"Drawdown must not exceed {max_dd*100}%",
        severity="hard",
    )


def max_leverage_rule(max_lev: float) -> Rule:
    """Create a maximum leverage rule."""
    return Rule(
        rule_id=f"max_leverage_{max_lev}",
        name=f"Max Leverage {max_lev}x",
        evaluator=lambda ctx: (
            getattr(ctx, "portfolio_context", {}).get("leverage", 0) if isinstance(ctx.portfolio_context, dict) else 0
        ) <= max_lev,
        description=f"Leverage must not exceed {max_lev}x",
        severity="hard",
    )
