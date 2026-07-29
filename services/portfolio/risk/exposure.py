"""
Exposure Management

Tracks and manages portfolio exposures:
- Factor exposure monitoring
- Sector exposure monitoring
- Concentration risk detection
- Exposure limit enforcement
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ..construction.models import (
    ExposureReport,
    FactorExposure,
    FactorExposureConstraint,
    SectorExposure,
    SectorExposureConstraint,
    StrategySnapshot,
)


class ExposureManager:
    """Manages factor and sector exposures for a portfolio."""

    def compute_factor_exposures(
        self,
        weights: Dict[str, float],
        snapshots: Dict[str, StrategySnapshot],
        constraints: Optional[Dict[str, FactorExposureConstraint]] = None,
    ) -> Dict[str, FactorExposure]:
        """Compute aggregate factor exposures from strategy weights and exposures."""
        exposures = {}

        # Collect all factor names across strategies
        all_factors = set()
        for snap in snapshots.values():
            all_factors.update(snap.factor_exposures.keys())
        if constraints:
            all_factors.update(constraints.keys())

        for factor_name in all_factors:
            total_exposure = 0.0
            for sid, w in weights.items():
                snap = snapshots.get(sid)
                if snap:
                    total_exposure += w * snap.factor_exposures.get(factor_name, 0.0)

            limit = float("inf")
            if constraints and factor_name in constraints:
                limit = constraints[factor_name].max_exposure

            exposures[factor_name] = FactorExposure(
                factor_name=factor_name,
                exposure=total_exposure,
                contribution_to_risk=0.0,
                limit=limit,
            )

        return exposures

    def compute_sector_exposures(
        self,
        weights: Dict[str, float],
        snapshots: Dict[str, StrategySnapshot],
        constraints: Optional[Dict[str, SectorExposureConstraint]] = None,
    ) -> Dict[str, SectorExposure]:
        """Compute aggregate sector exposures from strategy weights and exposures."""
        exposures = {}

        all_sectors = set()
        for snap in snapshots.values():
            all_sectors.update(snap.sector_exposures.keys())
        if constraints:
            all_sectors.update(constraints.keys())

        for sector_name in all_sectors:
            total_exposure = 0.0
            for sid, w in weights.items():
                snap = snapshots.get(sid)
                if snap:
                    total_exposure += w * snap.sector_exposures.get(sector_name, 0.0)

            limit = float("inf")
            if constraints and sector_name in constraints:
                limit = constraints[sector_name].max_exposure

            exposures[sector_name] = SectorExposure(
                sector_name=sector_name,
                exposure=total_exposure,
                contribution_to_risk=0.0,
                limit=limit,
            )

        return exposures

    def check_limits(
        self,
        factor_exposures: Dict[str, FactorExposure],
        sector_exposures: Dict[str, SectorExposure],
    ) -> List[str]:
        """Check exposures against limits. Returns list of warnings."""
        warnings = []

        for name, exp in factor_exposures.items():
            if exp.limit < float("inf") and abs(exp.exposure) > exp.limit:
                warnings.append(
                    f"Factor '{name}': exposure {exp.exposure:.4f} exceeds limit {exp.limit:.4f}"
                )

        for name, exp in sector_exposures.items():
            if exp.limit < float("inf") and abs(exp.exposure) > exp.limit:
                warnings.append(
                    f"Sector '{name}': exposure {exp.exposure:.4f} exceeds limit {exp.limit:.4f}"
                )

        return warnings

    def detect_concentration(
        self,
        factor_exposures: Dict[str, FactorExposure],
        sector_exposures: Dict[str, SectorExposure],
        factor_threshold: float = 0.5,
        sector_threshold: float = 0.4,
    ) -> List[str]:
        """Detect concentration risks. Returns warnings."""
        warnings = []

        for name, exp in factor_exposures.items():
            if abs(exp.exposure) > factor_threshold:
                warnings.append(
                    f"Factor '{name}' has high concentration: {exp.exposure:.1%}"
                )

        for name, exp in sector_exposures.items():
            if abs(exp.exposure) > sector_threshold:
                warnings.append(
                    f"Sector '{name}' has high concentration: {exp.exposure:.1%}"
                )

        return warnings

    def generate_report(
        self,
        portfolio_id: str,
        weights: Dict[str, float],
        snapshots: Dict[str, StrategySnapshot],
        factor_constraints: Optional[Dict[str, FactorExposureConstraint]] = None,
        sector_constraints: Optional[Dict[str, SectorExposureConstraint]] = None,
    ) -> ExposureReport:
        """Generate a full exposure report for the portfolio."""
        factor_exposures = self.compute_factor_exposures(weights, snapshots, factor_constraints)
        sector_exposures = self.compute_sector_exposures(weights, snapshots, sector_constraints)

        limit_warnings = self.check_limits(factor_exposures, sector_exposures)
        concentration_warnings = self.detect_concentration(factor_exposures, sector_exposures)

        total_factor_risk = sum(abs(e.exposure) for e in factor_exposures.values())
        total_sector_risk = sum(abs(e.exposure) for e in sector_exposures.values())

        return ExposureReport(
            portfolio_id=portfolio_id,
            factor_exposures=factor_exposures,
            sector_exposures=sector_exposures,
            total_factor_risk=total_factor_risk,
            total_sector_risk=total_sector_risk,
            concentration_warnings=limit_warnings + concentration_warnings,
        )
