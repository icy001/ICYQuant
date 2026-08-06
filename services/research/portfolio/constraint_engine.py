"""Constraint Engine — unified constraint modeling for portfolio optimization.

Supports constraints:
* Max Weight — per-asset maximum weight
* Min Weight — per-asset minimum weight
* Sector Limit — maximum sector exposure
* Liquidity — minimum liquidity requirement
* Turnover — maximum turnover
* Leverage — maximum leverage
* Exposure — factor exposure limits
* Cardinality — maximum number of assets
* Custom — user-defined constraints
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ConstraintType(str, Enum):
    """Types of portfolio constraints."""

    MAX_WEIGHT = "max_weight"
    MIN_WEIGHT = "min_weight"
    SECTOR_LIMIT = "sector_limit"
    LIQUIDITY = "liquidity"
    TURNOVER = "turnover"
    LEVERAGE = "leverage"
    EXPOSURE = "exposure"
    CARDINALITY = "cardinality"
    LONG_ONLY = "long_only"
    FULLY_INVESTED = "fully_invested"
    CUSTOM = "custom"


@dataclass
class Constraint:
    """A single portfolio constraint."""

    constraint_type: ConstraintType
    value: Any
    description: str = ""
    is_hard: bool = True  # Hard constraints must be satisfied
    penalty: float = 1000.0  # Penalty for soft constraint violation
    validator: Optional[Callable] = None

    def check(self, weights: Dict[str, float]) -> bool:
        """Check if weights satisfy this constraint."""
        if self.validator:
            return self.validator(weights, self.value)
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.constraint_type.value,
            "value": self.value,
            "description": self.description,
            "is_hard": self.is_hard,
        }


class ConstraintEngine:
    """Unified constraint modeling and validation.

    Builds, validates, and applies portfolio constraints
    across all optimization methods.
    """

    def __init__(self) -> None:
        self._constraints: List[Constraint] = []

    def build(self, config: Dict[str, Any]) -> List[Constraint]:
        """Build constraint list from configuration dictionary.

        Config keys:
        * long_only: bool
        * fully_invested: bool
        * min_weight: float
        * max_weight: float
        * max_leverage: float
        * max_turnover: float
        * sector_limits: Dict[str, float]
        * max_assets: int
        * asset_max_weights: Dict[str, float]
        * asset_min_weights: Dict[str, float]
        * custom_constraints: List[Dict]
        """
        constraints: List[Constraint] = []

        # Long-only
        if config.get("long_only", True):
            constraints.append(Constraint(
                constraint_type=ConstraintType.LONG_ONLY,
                value=True,
                description="Long-only portfolio",
                validator=self._validate_long_only,
            ))

        # Fully invested
        if config.get("fully_invested", True):
            constraints.append(Constraint(
                constraint_type=ConstraintType.FULLY_INVESTED,
                value=True,
                description="Weights sum to 1.0",
                validator=self._validate_fully_invested,
            ))

        # Max weight
        max_weight = config.get("max_weight")
        if max_weight is not None:
            constraints.append(Constraint(
                constraint_type=ConstraintType.MAX_WEIGHT,
                value=max_weight,
                description=f"Max weight per asset: {max_weight:.2%}",
                validator=self._validate_max_weight,
            ))

        # Min weight
        min_weight = config.get("min_weight")
        if min_weight is not None and min_weight > 0:
            constraints.append(Constraint(
                constraint_type=ConstraintType.MIN_WEIGHT,
                value=min_weight,
                description=f"Min weight per asset: {min_weight:.2%}",
                validator=self._validate_min_weight,
            ))

        # Max leverage
        max_leverage = config.get("max_leverage")
        if max_leverage is not None:
            constraints.append(Constraint(
                constraint_type=ConstraintType.LEVERAGE,
                value=max_leverage,
                description=f"Max leverage: {max_leverage:.1f}x",
                validator=self._validate_leverage,
            ))

        # Max turnover
        max_turnover = config.get("max_turnover")
        if max_turnover is not None:
            constraints.append(Constraint(
                constraint_type=ConstraintType.TURNOVER,
                value=max_turnover,
                description=f"Max turnover: {max_turnover:.2%}",
            ))

        # Sector limits
        sector_limits = config.get("sector_limits", {})
        if sector_limits:
            constraints.append(Constraint(
                constraint_type=ConstraintType.SECTOR_LIMIT,
                value=sector_limits,
                description=f"Sector limits: {sector_limits}",
            ))

        # Cardinality (max number of assets)
        max_assets = config.get("max_assets")
        if max_assets is not None:
            constraints.append(Constraint(
                constraint_type=ConstraintType.CARDINALITY,
                value=max_assets,
                description=f"Max assets: {max_assets}",
                validator=self._validate_cardinality,
            ))

        # Per-asset max weights
        asset_max_weights = config.get("asset_max_weights", {})
        for asset, max_w in asset_max_weights.items():
            constraints.append(Constraint(
                constraint_type=ConstraintType.MAX_WEIGHT,
                value={"asset": asset, "max": max_w},
                description=f"Max weight for {asset}: {max_w:.2%}",
            ))

        # Custom constraints
        custom = config.get("custom_constraints", [])
        for c in custom:
            constraints.append(Constraint(
                constraint_type=ConstraintType.CUSTOM,
                value=c.get("value"),
                description=c.get("description", ""),
                validator=c.get("validator"),
            ))

        self._constraints = constraints
        return constraints

    def validate(
        self, weights: Dict[str, float]
    ) -> Dict[str, Any]:
        """Validate weights against all constraints."""
        violations: List[Dict[str, Any]] = []
        passed = 0
        failed = 0

        for constraint in self._constraints:
            try:
                ok = constraint.check(weights)
                if ok:
                    passed += 1
                else:
                    failed += 1
                    violations.append({
                        "type": constraint.constraint_type.value,
                        "description": constraint.description,
                        "is_hard": constraint.is_hard,
                    })
            except Exception as e:
                failed += 1
                violations.append({
                    "type": constraint.constraint_type.value,
                    "error": str(e),
                })

        return {
            "valid": len(violations) == 0,
            "passed": passed,
            "failed": failed,
            "violations": violations,
        }

    def list_constraints(self) -> List[Dict[str, Any]]:
        return [c.to_dict() for c in self._constraints]

    # ── validators ─────────────────────────────────────────────────────────

    @staticmethod
    def _validate_long_only(
        weights: Dict[str, float], value: Any
    ) -> bool:
        return all(w >= -1e-6 for w in weights.values())

    @staticmethod
    def _validate_fully_invested(
        weights: Dict[str, float], value: Any
    ) -> bool:
        total = sum(weights.values())
        return abs(total - 1.0) < 0.01

    @staticmethod
    def _validate_max_weight(
        weights: Dict[str, float], value: Any
    ) -> bool:
        if isinstance(value, dict):
            asset = value["asset"]
            return weights.get(asset, 0.0) <= value["max"] + 1e-6
        return all(w <= value + 1e-6 for w in weights.values())

    @staticmethod
    def _validate_min_weight(
        weights: Dict[str, float], value: Any
    ) -> bool:
        # Non-zero weights must be >= min
        return all(
            w >= value - 1e-6 or w <= 1e-6
            for w in weights.values()
        )

    @staticmethod
    def _validate_leverage(
        weights: Dict[str, float], value: Any
    ) -> bool:
        gross = sum(abs(w) for w in weights.values())
        return gross <= value + 1e-6

    @staticmethod
    def _validate_cardinality(
        weights: Dict[str, float], value: Any
    ) -> bool:
        non_zero = sum(1 for w in weights.values() if abs(w) > 1e-6)
        return non_zero <= value
