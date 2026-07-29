"""Stress Test Simulator - runs stress scenarios on portfolios."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StressSimulationResult:
    """Result of a stress test simulation."""
    scenario_name: str
    scenario_description: str
    severity: str
    portfolio_id: str = ""
    initial_value: float = 0.0
    stressed_value: float = 0.0
    loss_pct: float = 0.0
    loss_amount: float = 0.0
    worst_asset: str = ""
    worst_asset_loss_pct: float = 0.0
    action_required: str = "MONITOR"
    post_stress_positions: Dict[str, float] = field(default_factory=dict)
    recovery_days_estimate: int = 0
    margin_call_risk: bool = False
    liquidation_risk: bool = False
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "scenario": self.scenario_name,
            "description": self.scenario_description,
            "severity": self.severity,
            "portfolio_impact": {
                "initial_value": self.initial_value,
                "stressed_value": round(self.stressed_value, 2),
                "loss_pct": round(self.loss_pct, 4),
                "loss_amount": round(self.loss_amount, 2),
            },
            "worst_asset": self.worst_asset,
            "worst_asset_loss": round(self.worst_asset_loss_pct, 4),
            "action": self.action_required,
            "recovery_days": self.recovery_days_estimate,
            "risks": {
                "margin_call": self.margin_call_risk,
                "liquidation": self.liquidation_risk,
            },
            "details": self.details,
        }


class StressSimulator:
    """Stress Test Simulator.

    Simulates portfolio impact under various stress scenarios:
    - Market crash (e.g., S&P 500 -10%)
    - Liquidity crisis (spread ×3)
    - Sector shock (Semiconductor -20%)
    - Interest rate shock
    - Currency crisis
    """

    def __init__(self):
        self.results: List[StressSimulationResult] = []

    def simulate(
        self,
        scenario: dict,
        positions: Dict[str, float],
        portfolio_id: str = "",
        margin_enabled: bool = False,
    ) -> StressSimulationResult:
        """Run a single stress scenario on a portfolio.

        Args:
            scenario: Scenario definition dict.
            positions: Current positions {asset: value}.
            portfolio_id: Portfolio identifier.
            margin_enabled: Whether margin is used.

        Returns:
            StressSimulationResult with impact analysis.
        """
        shocks = scenario.get("market_shock", {})
        vol_mult = scenario.get("volatility_multiplier", 1.0)
        liq_disc = scenario.get("liquidity_discount", 0.0)

        initial_value = sum(positions.values())
        stressed_value = initial_value
        worst_asset = ""
        worst_loss = 0.0
        post_stress = dict(positions)

        for asset, position in positions.items():
            # Find applicable shock
            shock_pct = 0.0
            for shock_asset, shock_val in shocks.items():
                if shock_asset.lower() in asset.lower():
                    shock_pct = shock_val
                    break
            # Default shock: scaled by volatility multiplier
            if shock_pct == 0.0:
                shock_pct = -0.02 * vol_mult

            # Apply shock
            loss = position * abs(shock_pct)
            stressed_value -= loss

            # Apply liquidity discount
            liq_loss = position * liq_disc
            stressed_value -= liq_loss

            # Track worst asset
            asset_loss_pct = abs(shock_pct) + liq_disc
            if asset_loss_pct > worst_loss:
                worst_loss = asset_loss_pct
                worst_asset = asset

            # Update post-stress positions
            post_stress[asset] = position * (1.0 - abs(shock_pct) - liq_disc)

        loss_pct = (stressed_value - initial_value) / max(initial_value, 1.0)
        loss_amount = initial_value - stressed_value

        # Determine action
        action = self._determine_action(abs(loss_pct))

        # Estimate recovery days
        recovery_days = self._estimate_recovery(abs(loss_pct))

        # Risk flags
        margin_call_risk = margin_enabled and abs(loss_pct) > 0.10
        liquidation_risk = margin_enabled and abs(loss_pct) > 0.20

        result = StressSimulationResult(
            scenario_name=scenario.get("name", "Unknown"),
            scenario_description=scenario.get("description", ""),
            severity=scenario.get("severity", "MODERATE"),
            portfolio_id=portfolio_id,
            initial_value=initial_value,
            stressed_value=stressed_value,
            loss_pct=loss_pct,
            loss_amount=loss_amount,
            worst_asset=worst_asset,
            worst_asset_loss_pct=worst_loss,
            action_required=action,
            post_stress_positions=post_stress,
            recovery_days_estimate=recovery_days,
            margin_call_risk=margin_call_risk,
            liquidation_risk=liquidation_risk,
            details={
                "shocks_applied": shocks,
                "volatility_multiplier": vol_mult,
                "liquidity_discount": liq_disc,
            },
        )
        self.results.append(result)
        return result

    def simulate_all(
        self,
        scenarios: List[dict],
        positions: Dict[str, float],
        portfolio_id: str = "",
    ) -> Dict[str, Any]:
        """Run all provided stress scenarios.

        Args:
            scenarios: List of scenario definition dicts.
            positions: Current positions.
            portfolio_id: Portfolio identifier.

        Returns:
            Dict with all simulation results.
        """
        results = []
        for scenario in scenarios:
            result = self.simulate(scenario, positions, portfolio_id)
            results.append(result.to_dict())

        total_losses = [r["portfolio_impact"]["loss_pct"] for r in results]
        worst = max(total_losses) if total_losses else 0.0

        return {
            "portfolio_id": portfolio_id,
            "scenarios_run": len(results),
            "results": results,
            "worst_case_loss": round(worst, 4),
            "average_loss": round(sum(total_losses) / max(len(total_losses), 1), 4),
            "action": self._determine_action(worst),
        }

    def _determine_action(self, loss_pct: float) -> str:
        if loss_pct > 0.20:
            return "REDUCE_EXPOSURE_SIGNIFICANTLY"
        elif loss_pct > 0.10:
            return "REDUCE_POSITION"
        elif loss_pct > 0.05:
            return "MONITOR_CLOSELY"
        return "MONITOR"

    def _estimate_recovery(self, loss_pct: float) -> int:
        """Estimate days to recover from loss (simplified)."""
        if loss_pct < 0.05:
            return 5
        elif loss_pct < 0.10:
            return 15
        elif loss_pct < 0.20:
            return 45
        elif loss_pct < 0.30:
            return 90
        return 180

    def get_latest_result(self) -> Optional[StressSimulationResult]:
        """Get the most recent simulation result."""
        return self.results[-1] if self.results else None

    def get_results_by_severity(self, severity: str) -> List[StressSimulationResult]:
        """Get all results for a given severity."""
        return [r for r in self.results if r.severity.upper() == severity.upper()]
