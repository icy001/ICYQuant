"""Hypothesis Validator — Validates hypotheses before they enter research.

Screens hypotheses for logical coherence, data availability, novelty,
and potential look-ahead bias. Prevents the system from endlessly
testing meaningless hypotheses.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HypothesisValidator:
    """Hypothesis Validator — gates research entry.

    Validation checks:
        1. Logical validation — does the hypothesis make logical sense?
        2. Data availability — can we get the required data?
        3. Novelty check — has this been tested before?
        4. Leakage check — is there look-ahead bias risk?
        5. Falsifiability — can it be proven wrong?
    """

    def __init__(self) -> None:
        self._validated_count: int = 0
        self._rejected_count: int = 0
        self._rejected_reasons: Dict[str, int] = {}

    async def validate(
        self,
        hypothesis: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Validate a hypothesis.

        Args:
            hypothesis: The hypothesis to validate.
            history: Optional historical hypotheses for novelty check.

        Returns:
            Dict with validation result and details.
        """
        hyp_id = hypothesis.get("hypothesis_id", "unknown")
        checks: List[Dict[str, Any]] = []
        all_passed = True

        # Check 1: Logical validation
        logic_result = self._check_logic(hypothesis)
        checks.append(logic_result)
        if not logic_result["passed"]:
            all_passed = False

        # Check 2: Data availability
        data_result = self._check_data_availability(hypothesis)
        checks.append(data_result)
        if not data_result["passed"]:
            all_passed = False

        # Check 3: Novelty check
        novelty_result = self._check_novelty(hypothesis, history or [])
        checks.append(novelty_result)
        if not novelty_result["passed"]:
            all_passed = False

        # Check 4: Leakage check
        leakage_result = self._check_leakage(hypothesis)
        checks.append(leakage_result)
        if not leakage_result["passed"]:
            all_passed = False

        # Check 5: Falsifiability
        falsifiability_result = self._check_falsifiability(hypothesis)
        checks.append(falsifiability_result)

        result = {
            "hypothesis_id": hyp_id,
            "valid": all_passed,
            "checks": checks,
            "checks_passed": sum(1 for c in checks if c["passed"]),
            "checks_total": len(checks),
            "validated_at": datetime.now(timezone.utc).isoformat(),
        }

        if all_passed:
            self._validated_count += 1
        else:
            self._rejected_count += 1
            for check in checks:
                if not check["passed"]:
                    reason = check.get("reason", "unknown")
                    self._rejected_reasons[reason] = (
                        self._rejected_reasons.get(reason, 0) + 1
                    )

        logger.info(
            "Hypothesis %s validation: %s (%d/%d checks passed)",
            hyp_id,
            "PASSED" if all_passed else "REJECTED",
            sum(1 for c in checks if c["passed"]),
            len(checks),
        )

        return result

    # ------------------------------------------------------------------
    # Validation Checks
    # ------------------------------------------------------------------

    def _check_logic(self, hyp: Dict[str, Any]) -> Dict[str, Any]:
        """Check logical coherence of the hypothesis."""
        statement = hyp.get("statement", "")
        mechanism = hyp.get("expected_mechanism", "")
        direction = hyp.get("expected_direction", "")

        issues = []

        if not statement or len(statement) < 20:
            issues.append("Statement too short or missing")

        if not mechanism:
            issues.append("No expected mechanism provided")

        if direction not in ("positive", "negative", "directional", "both", "conditional", "unknown"):
            issues.append(f"Invalid expected direction: {direction}")

        return {
            "check": "logical_validation",
            "passed": len(issues) == 0,
            "issues": issues,
            "reason": "; ".join(issues) if issues else "Logic check passed",
        }

    def _check_data_availability(self, hyp: Dict[str, Any]) -> Dict[str, Any]:
        """Check if required data is available."""
        required_features = hyp.get("required_features", [])
        required_data = hyp.get("required_data", [])

        if not required_features and not required_data:
            return {
                "check": "data_availability",
                "passed": False,
                "reason": "No data requirements specified",
            }

        # In production, check against data catalog
        return {
            "check": "data_availability",
            "passed": True,
            "reason": f"Data requirements appear available ({len(required_features)} features, {len(required_data)} datasets)",
        }

    def _check_novelty(
        self,
        hyp: Dict[str, Any],
        history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Check if this hypothesis has been tested before."""
        # In production, compare against discovery memory
        # For now, check for exact duplicates in history
        statement = hyp.get("statement", "")
        for h in history:
            if h.get("statement") == statement:
                return {
                    "check": "novelty",
                    "passed": False,
                    "reason": f"Duplicate of previously tested hypothesis: {h.get('hypothesis_id')}",
                    "similar_hypothesis": h.get("hypothesis_id"),
                }

        return {
            "check": "novelty",
            "passed": True,
            "reason": "Hypothesis appears novel",
        }

    def _check_leakage(self, hyp: Dict[str, Any]) -> Dict[str, Any]:
        """Check for potential look-ahead bias."""
        features = hyp.get("required_features", [])
        risky_features = [
            "future_", "next_day_", "next_", "forward_",
            "target_", "label_", "y_",
        ]

        issues = []
        for feature in features:
            for risky in risky_features:
                if feature.lower().startswith(risky):
                    issues.append(f"Feature '{feature}' may contain forward-looking data")

        return {
            "check": "leakage_check",
            "passed": len(issues) == 0,
            "issues": issues,
            "reason": "No leakage detected" if not issues else "; ".join(issues),
        }

    def _check_falsifiability(self, hyp: Dict[str, Any]) -> Dict[str, Any]:
        """Check if the hypothesis is falsifiable."""
        criteria = hyp.get("falsification_criteria", "")

        if not criteria or len(criteria) < 20:
            return {
                "check": "falsifiability",
                "passed": True,  # Warning, not blocking
                "reason": "Falsification criteria could be more specific",
            }

        return {
            "check": "falsifiability",
            "passed": True,
            "reason": "Falsification criteria specified",
        }
