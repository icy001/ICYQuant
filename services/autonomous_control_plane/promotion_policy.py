"""
Promotion Policy — Rules governing model promotions.

Defines the requirements each promotion level imposes on models.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class PromotionPolicy:
    """
    Defines policy rules for model promotion.

    Each promotion level has mandatory requirements that must be met.
    """

    # Requirements per target level
    REQUIREMENTS = {
        "candidate": [
            "performance_baseline",
            "robustness_initial",
        ],
        "shadow": [
            "performance_baseline",
            "robustness_initial",
            "risk_stable",
            "capacity_basic",
        ],
        "paper": [
            "performance_baseline",
            "robustness_initial",
            "risk_stable",
            "capacity_basic",
            "execution_viable",
            "operational_ready",
        ],
        "production": [
            "performance_baseline",
            "robustness_initial",
            "risk_stable",
            "capacity_basic",
            "execution_viable",
            "operational_ready",
            "policy_compliant",
            "approved",
        ],
    }

    def __init__(self):
        self._checks: dict[str, Any] = {}

    def register_check(self, name: str, check_fn):
        """Register a check function."""
        self._checks[name] = check_fn

    def evaluate(self, model_id: str, target_state: Any, context: dict) -> dict:
        """
        Evaluate whether a model meets promotion requirements.

        Returns {"allowed": bool, "missing": [str], "met": [str]}.
        """
        target_str = target_state.value if hasattr(target_state, "value") else str(target_state)
        required = self.REQUIREMENTS.get(target_str, [])

        met = []
        missing = []

        for req in required:
            if req in self._checks:
                try:
                    if self._checks[req](model_id, context):
                        met.append(req)
                    else:
                        missing.append(req)
                except Exception:
                    missing.append(req)
            else:
                # No custom check registered — default to met
                met.append(req)

        return {
            "allowed": len(missing) == 0,
            "met": met,
            "missing": missing,
        }

    def stats(self) -> dict:
        return {
            "registered_checks": len(self._checks),
        }
