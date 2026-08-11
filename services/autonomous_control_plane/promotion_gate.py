"""
Promotion Gate — Stage-gate check before each promotion level.

Evaluates all mandatory checks before a model can advance to the next
lifecycle stage.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PromotionGate:
    """
    Stage gate for model promotions.

    Each promotion must pass through this gate, which evaluates
    performance, robustness, risk, execution, and operational criteria.
    """

    def __init__(self):
        self._checks_passed = 0
        self._checks_failed = 0

    # Gate checks per stage
    GATE_CHECKS = {
        "research": ["performance_baseline"],
        "validating": ["performance_baseline", "risk_basic"],
        "candidate": ["performance_baseline", "risk_stable", "robustness"],
        "shadow": ["performance_baseline", "risk_stable", "robustness", "capacity"],
        "paper": ["performance_baseline", "risk_stable", "robustness", "capacity", "execution"],
        "production": [
            "performance",
            "robustness",
            "capacity",
            "risk",
            "execution",
            "operational_health",
            "policy_compliance",
            "approval",
        ],
    }

    async def evaluate(
        self, model_id: str, target_state: Any, context: dict
    ) -> dict:
        """Evaluate if a model passes the gate for the target state."""
        target_str = target_state.value if hasattr(target_state, "value") else str(target_state)
        checks = self.GATE_CHECKS.get(target_str, [])

        passed = []
        failed = []

        for check in checks:
            handler = getattr(self, f"_check_{check}", None)
            if handler:
                result = await handler(model_id, context)
                if result:
                    passed.append(check)
                else:
                    failed.append(check)
            else:
                passed.append(check)  # Unknown check defaults to pass

        self._checks_passed += len(passed)
        self._checks_failed += len(failed)

        return {
            "passed": len(failed) == 0,
            "checks_total": len(checks),
            "passed_checks": passed,
            "failed_checks": failed,
            "failures": [f"Gate check '{f}' failed" for f in failed],
        }

    async def _check_performance(self, model_id: str, context: dict) -> bool:
        return context.get("performance_sharpe", 0) >= 0.5

    async def _check_performance_baseline(self, model_id: str, context: dict) -> bool:
        return context.get("performance_sharpe", 0) >= 0.0

    async def _check_risk_basic(self, model_id: str, context: dict) -> bool:
        return context.get("max_drawdown", 1.0) <= 0.5

    async def _check_risk_stable(self, model_id: str, context: dict) -> bool:
        return context.get("max_drawdown", 1.0) <= 0.3

    async def _check_risk(self, model_id: str, context: dict) -> bool:
        return context.get("max_drawdown", 1.0) <= 0.25

    async def _check_robustness(self, model_id: str, context: dict) -> bool:
        return context.get("days_stable", 0) >= 30

    async def _check_capacity(self, model_id: str, context: dict) -> bool:
        return context.get("capacity_ok", True)

    async def _check_execution(self, model_id: str, context: dict) -> bool:
        return context.get("execution_ok", True)

    async def _check_operational_health(self, model_id: str, context: dict) -> bool:
        return context.get("operational_ok", True)

    async def _check_policy_compliance(self, model_id: str, context: dict) -> bool:
        return context.get("policy_compliant", True)

    async def _check_approval(self, model_id: str, context: dict) -> bool:
        return context.get("approved", False)

    def stats(self) -> dict:
        return {
            "checks_passed": self._checks_passed,
            "checks_failed": self._checks_failed,
        }
