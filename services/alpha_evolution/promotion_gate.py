"""Promotion Gate — Controlled gate for promoting candidates to production."""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PromotionGate:
    """Controls which candidates are promoted to production-ready state."""

    def __init__(
        self,
        require_human_approval: bool = True,
        min_fitness: float = 0.30,
        require_all_validations: bool = True,
        max_promotions_per_run: int = 50,
    ):
        self._require_approval = require_human_approval
        self._min_fitness = min_fitness
        self._require_all_validations = require_all_validations
        self._max_promotions = max_promotions_per_run
        self._promoted_count = 0

    async def evaluate(
        self,
        candidate_id: str,
        fitness: float,
        validation_results: Dict[str, bool],
        risk_check: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Evaluate a candidate for promotion."""
        checks = {}

        # Fitness check
        checks["fitness"] = {
            "passed": fitness >= self._min_fitness,
            "value": fitness,
            "threshold": self._min_fitness,
        }

        # Validation check
        if self._require_all_validations:
            all_val_passed = all(validation_results.values())
            checks["validations"] = {
                "passed": all_val_passed,
                "details": validation_results,
            }

        # Risk check
        checks["risk"] = {
            "passed": risk_check.get("passed", False),
            "details": risk_check,
        }

        # Capacity check
        checks["capacity"] = {
            "passed": self._promoted_count < self._max_promotions,
            "promoted_so_far": self._promoted_count,
            "max": self._max_promotions,
        }

        all_passed = all(c.get("passed", False) for c in checks.values())

        result = {
            "candidate_id": candidate_id,
            "eligible": all_passed,
            "requires_approval": self._require_approval,
            "checks": checks,
            "status": "pending_approval" if (all_passed and self._require_approval) else (
                "promoted" if all_passed else "rejected"
            ),
        }

        if all_passed and not self._require_approval:
            self._promoted_count += 1

        return result

    def reset(self) -> None:
        self._promoted_count = 0

    def get_stats(self) -> Dict[str, Any]:
        return {
            "promoted_count": self._promoted_count,
            "max_promotions": self._max_promotions,
            "require_approval": self._require_approval,
            "min_fitness": self._min_fitness,
        }
