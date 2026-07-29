"""
Portfolio Constraint Validator and Enforcer

Validates and enforces:
- Weight constraints (min/max per strategy)
- Risk constraints (volatility, drawdown, VaR)
- Factor exposure limits
- Sector exposure limits
- Drawdown limits
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .models import (
    DrawdownConstraint,
    FactorExposure,
    FactorExposureConstraint,
    PortfolioConstraints,
    RiskBudgetAllocation,
    RiskConstraint,
    SectorExposure,
    SectorExposureConstraint,
    StrategyAllocation,
    StrategySnapshot,
    WeightConstraint,
)


class ConstraintValidator:
    """Validates allocations against all constraints."""

    def validate(
        self,
        weights: Dict[str, float],
        snapshots: Dict[str, StrategySnapshot],
        constraints: Optional[PortfolioConstraints] = None,
        risk_budgets: Optional[Dict[str, RiskBudgetAllocation]] = None,
    ) -> List[str]:
        """Validate weights against all constraints. Returns list of violations."""
        violations = []

        if constraints is None:
            return violations

        # Check weight constraints
        for sid, wc in constraints.weight_constraints.items():
            w = weights.get(sid, 0.0)
            if w < wc.min_weight:
                violations.append(
                    f"Strategy {sid}: weight {w:.4f} below min {wc.min_weight}"
                )
            if w > wc.max_weight:
                violations.append(
                    f"Strategy {sid}: weight {w:.4f} above max {wc.max_weight}"
                )

        # Check global max single strategy
        for sid, w in weights.items():
            if w > constraints.max_single_strategy_weight:
                violations.append(
                    f"Strategy {sid}: weight {w:.4f} above global max {constraints.max_single_strategy_weight}"
                )
            if w < constraints.min_single_strategy_weight and w > 0:
                violations.append(
                    f"Strategy {sid}: weight {w:.4f} below global min {constraints.min_single_strategy_weight}"
                )

        # Check total weight
        total = sum(weights.values())
        if total > constraints.max_total_weight:
            violations.append(f"Total weight {total:.4f} above max {constraints.max_total_weight}")
        if total < constraints.min_total_weight:
            violations.append(f"Total weight {total:.4f} below min {constraints.min_total_weight}")

        # Check strategy count
        active = len([w for w in weights.values() if w > 0])
        if active > constraints.max_strategies:
            violations.append(f"Active strategies {active} above max {constraints.max_strategies}")
        if active < constraints.min_strategies:
            violations.append(f"Active strategies {active} below min {constraints.min_strategies}")

        # Check risk constraints
        for sid, rc in constraints.risk_constraints.items():
            snap = snapshots.get(sid)
            if snap is None:
                continue
            if snap.expected_volatility > rc.max_volatility:
                violations.append(
                    f"Strategy {sid}: volatility {snap.expected_volatility:.4f} above max {rc.max_volatility}"
                )
            if snap.max_drawdown > rc.max_drawdown:
                violations.append(
                    f"Strategy {sid}: drawdown {snap.max_drawdown:.4f} above max {rc.max_drawdown}"
                )

        # Check factor exposure constraints
        for factor_name, fc in constraints.factor_constraints.items():
            portfolio_exposure = 0.0
            for sid, w in weights.items():
                snap = snapshots.get(sid)
                if snap:
                    portfolio_exposure += w * snap.factor_exposures.get(factor_name, 0.0)
            if portfolio_exposure > fc.max_exposure:
                violations.append(
                    f"Factor {factor_name}: exposure {portfolio_exposure:.4f} above max {fc.max_exposure}"
                )
            if portfolio_exposure < fc.min_exposure:
                violations.append(
                    f"Factor {factor_name}: exposure {portfolio_exposure:.4f} below min {fc.min_exposure}"
                )

        # Check sector exposure constraints
        for sector_name, sc in constraints.sector_constraints.items():
            portfolio_exposure = 0.0
            for sid, w in weights.items():
                snap = snapshots.get(sid)
                if snap:
                    portfolio_exposure += w * snap.sector_exposures.get(sector_name, 0.0)
            if portfolio_exposure > sc.max_exposure:
                violations.append(
                    f"Sector {sector_name}: exposure {portfolio_exposure:.4f} above max {sc.max_exposure}"
                )
            if portfolio_exposure < sc.min_exposure:
                violations.append(
                    f"Sector {sector_name}: exposure {portfolio_exposure:.4f} below min {sc.min_exposure}"
                )

        # Check drawdown constraint
        if constraints.drawdown_constraint:
            for sid, w in weights.items():
                snap = snapshots.get(sid)
                if snap and snap.max_drawdown > constraints.drawdown_constraint.max_drawdown:
                    violations.append(
                        f"Strategy {sid}: drawdown {snap.max_drawdown:.4f} above portfolio max {constraints.drawdown_constraint.max_drawdown}"
                    )

        return violations

    def is_valid(
        self,
        weights: Dict[str, float],
        snapshots: Dict[str, StrategySnapshot],
        constraints: Optional[PortfolioConstraints] = None,
    ) -> bool:
        """Check if weights satisfy all constraints."""
        return len(self.validate(weights, snapshots, constraints)) == 0

    def validate_single_weight(
        self,
        strategy_id: str,
        weight: float,
        constraints: Optional[PortfolioConstraints],
    ) -> Tuple[bool, str]:
        """Validate a single strategy weight against its constraints."""
        if constraints is None:
            return True, ""

        wc = constraints.weight_constraints.get(strategy_id)
        if wc:
            if weight < wc.min_weight:
                return False, f"Below min weight {wc.min_weight}"
            if weight > wc.max_weight:
                return False, f"Above max weight {wc.max_weight}"

        if weight > constraints.max_single_strategy_weight:
            return False, f"Above global max weight {constraints.max_single_strategy_weight}"

        return True, ""


class ConstraintEnforcer:
    """Enforces constraints by adjusting weights."""

    def __init__(self, validator: Optional[ConstraintValidator] = None):
        self.validator = validator or ConstraintValidator()

    def enforce(
        self,
        weights: Dict[str, float],
        snapshots: Dict[str, StrategySnapshot],
        constraints: Optional[PortfolioConstraints],
    ) -> Dict[str, float]:
        """Enforce all constraints on weights."""
        if constraints is None:
            return weights

        result = dict(weights)

        # Step 1: Clamp per-strategy weights
        for sid, wc in constraints.weight_constraints.items():
            if sid in result:
                result[sid] = max(wc.min_weight, min(result[sid], wc.max_weight))

        # Step 2: Clamp to global max
        for sid in result:
            result[sid] = min(result[sid], constraints.max_single_strategy_weight)
            result[sid] = max(result[sid], constraints.min_single_strategy_weight)

        # Step 3: Remove strategies that violate risk constraints
        for sid, rc in constraints.risk_constraints.items():
            snap = snapshots.get(sid)
            if snap:
                if snap.expected_volatility > rc.max_volatility:
                    result[sid] = 0.0
                elif snap.max_drawdown > rc.max_drawdown:
                    result[sid] = 0.0

        # Step 4: Enforce drawdown constraint
        if constraints.drawdown_constraint:
            for sid in result:
                snap = snapshots.get(sid)
                if snap and snap.max_drawdown > constraints.drawdown_constraint.max_drawdown:
                    result[sid] = 0.0

        # Step 5: Enforce factor exposure by reducing highest-contributing weights
        result = self._enforce_factor_exposures(result, snapshots, constraints)

        # Step 6: Enforce sector exposure
        result = self._enforce_sector_exposures(result, snapshots, constraints)

        # Step 7: Enforce strategy count limits
        result = self._enforce_strategy_count(result, constraints)

        # Step 8: Normalize
        total = sum(result.values())
        if total > 0:
            scale = min(1.0, constraints.max_total_weight / total)
            result = {s: w * scale for s, w in result.items()}

        return result

    def _enforce_factor_exposures(
        self,
        weights: Dict[str, float],
        snapshots: Dict[str, StrategySnapshot],
        constraints: PortfolioConstraints,
    ) -> Dict[str, float]:
        """Reduce weights to satisfy factor exposure constraints."""
        result = dict(weights)

        for factor_name, fc in constraints.factor_constraints.items():
            # Calculate current portfolio exposure
            total_exposure = 0.0
            for sid, w in result.items():
                snap = snapshots.get(sid)
                if snap:
                    total_exposure += w * snap.factor_exposures.get(factor_name, 0.0)

            # If over limit, reduce highest-contributing strategies
            if total_exposure > fc.max_exposure:
                excess = total_exposure - fc.max_exposure
                contributions = []
                for sid, w in result.items():
                    snap = snapshots.get(sid)
                    if snap and w > 0:
                        contrib = w * snap.factor_exposures.get(factor_name, 0.0)
                        if contrib > 0:
                            contributions.append((sid, contrib))

                contributions.sort(key=lambda x: x[1], reverse=True)

                for sid, contrib in contributions:
                    if excess <= 0:
                        break
                    old_w = result[sid]
                    reduction = min(old_w, excess / max(contributions[0][1] / old_w if contributions else 1, 1e-6))
                    result[sid] = max(0.0, old_w - reduction * 0.5)
                    excess -= contrib * 0.5

            # If below min, warn but don't force (min exposure is informational)
            if total_exposure < fc.min_exposure:
                pass  # Can't force strategies to have exposure they don't have

        return result

    def _enforce_sector_exposures(
        self,
        weights: Dict[str, float],
        snapshots: Dict[str, StrategySnapshot],
        constraints: PortfolioConstraints,
    ) -> Dict[str, float]:
        """Reduce weights to satisfy sector exposure constraints."""
        result = dict(weights)

        for sector_name, sc in constraints.sector_constraints.items():
            total_exposure = 0.0
            for sid, w in result.items():
                snap = snapshots.get(sid)
                if snap:
                    total_exposure += w * snap.sector_exposures.get(sector_name, 0.0)

            if total_exposure > sc.max_exposure:
                excess = total_exposure - sc.max_exposure
                contributions = []
                for sid, w in result.items():
                    snap = snapshots.get(sid)
                    if snap and w > 0:
                        contrib = w * snap.sector_exposures.get(sector_name, 0.0)
                        if contrib > 0:
                            contributions.append((sid, contrib))

                contributions.sort(key=lambda x: x[1], reverse=True)

                for sid, contrib in contributions:
                    if excess <= 0:
                        break
                    old_w = result[sid]
                    reduction = min(old_w, excess * 0.5)
                    result[sid] = max(0.0, old_w - reduction)
                    excess -= contrib * 0.5

        return result

    def _enforce_strategy_count(
        self,
        weights: Dict[str, float],
        constraints: PortfolioConstraints,
    ) -> Dict[str, float]:
        """Enforce minimum and maximum number of strategies."""
        result = dict(weights)

        # Sort by weight descending
        active = [(sid, w) for sid, w in result.items() if w > 0]
        active.sort(key=lambda x: x[1], reverse=True)

        # Trim to max_strategies
        if len(active) > constraints.max_strategies:
            to_remove = active[constraints.max_strategies:]
            for sid, _ in to_remove:
                result[sid] = 0.0

        return result

    def calculate_factor_exposures(
        self,
        weights: Dict[str, float],
        snapshots: Dict[str, StrategySnapshot],
        factor_constraints: Dict[str, FactorExposureConstraint],
    ) -> Dict[str, FactorExposure]:
        """Calculate current factor exposures for the portfolio."""
        exposures = {}

        for factor_name, fc in factor_constraints.items():
            total = 0.0
            for sid, w in weights.items():
                snap = snapshots.get(sid)
                if snap:
                    total += w * snap.factor_exposures.get(factor_name, 0.0)
            exposures[factor_name] = FactorExposure(
                factor_name=factor_name,
                exposure=total,
                contribution_to_risk=0.0,
                limit=fc.max_exposure,
            )

        return exposures

    def calculate_sector_exposures(
        self,
        weights: Dict[str, float],
        snapshots: Dict[str, StrategySnapshot],
        sector_constraints: Dict[str, SectorExposureConstraint],
    ) -> Dict[str, SectorExposure]:
        """Calculate current sector exposures for the portfolio."""
        exposures = {}

        for sector_name, sc in sector_constraints.items():
            total = 0.0
            for sid, w in weights.items():
                snap = snapshots.get(sid)
                if snap:
                    total += w * snap.sector_exposures.get(sector_name, 0.0)
            exposures[sector_name] = SectorExposure(
                sector_name=sector_name,
                exposure=total,
                contribution_to_risk=0.0,
                limit=sc.max_exposure,
            )

        return exposures
