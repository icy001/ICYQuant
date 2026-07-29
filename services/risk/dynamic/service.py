"""Dynamic Risk Service - orchestrates the full dynamic risk management loop."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..dynamic.models import (
    RiskSnapshot, RiskLevel, RiskDecision, RiskAction,
    MarketRegime, StressScenario, StressResult, StressSeverity,
    RiskThresholds,
)
from ..dynamic.calculator import RiskCalculator
from ..dynamic.volatility import VolatilityTargeter
from ..dynamic.monitor import RiskMonitor
from ..stress.scenario import ScenarioEngine
from ..stress.simulator import StressSimulator


class DynamicRiskService:
    """Dynamic Risk Management Service.

    Orchestrates the full dynamic risk loop:

    Portfolio
        ↓
    Risk Engine (monitor + calculator)
        ↓
    Risk Decision
        ↓
    Position Adjustment
        ↓
    Order Engine
    """

    def __init__(
        self,
        thresholds: Optional[RiskThresholds] = None,
        target_volatility: float = 0.15,
    ):
        self.thresholds = thresholds or RiskThresholds()
        self.calculator = RiskCalculator()
        self.vol_targeter = VolatilityTargeter(target_volatility=target_volatility)
        self.monitor = RiskMonitor(thresholds=self.thresholds)
        self.scenario_engine = ScenarioEngine()
        self.simulator = StressSimulator()
        self._decision_counter = 0

    def assess_risk(
        self,
        portfolio_id: str,
        returns: List[float],
        weights: Optional[List[float]] = None,
        volatilities: Optional[List[float]] = None,
        correlation_matrix: Optional[List[List[float]]] = None,
        positions: Optional[Dict[str, float]] = None,
        drawdown: float = 0.0,
        max_drawdown: float = 0.0,
        exposure: Optional[Dict[str, float]] = None,
        total_value: float = 1.0,
    ) -> Dict[str, Any]:
        """Run a full risk assessment cycle.

        Args:
            portfolio_id: Portfolio identifier.
            returns: Historical return series.
            weights: Asset weights.
            volatilities: Asset volatilities.
            correlation_matrix: Correlation matrix.
            positions: Position sizes by asset.
            drawdown: Current drawdown.
            max_drawdown: Maximum historical drawdown.
            exposure: Exposure breakdown.
            total_value: Total portfolio value.

        Returns:
            Dict with full risk assessment.
        """
        # Step 1: Compute risk metrics
        metrics = self.calculator.compute_risk_metrics(
            returns=returns,
            weights=weights,
            volatilities=volatilities,
            correlation_matrix=correlation_matrix,
            total_value=total_value,
        )

        # Step 2: Update position-level risks
        if weights and volatilities and positions:
            for i, (asset, pos_size) in enumerate(positions.items()):
                weight = weights[i] if i < len(weights) else 0.0
                vol = volatilities[i] if i < len(volatilities) else 0.15
                beta = 1.0  # default
                comp_var = metrics.get("component_var", [])
                risk_contrib = (comp_var[i]["risk_contribution_pct"]
                                if i < len(comp_var) else 0.0)
                marginal = (comp_var[i]["marginal_var"] if i < len(comp_var) else 0.0)

                self.monitor.update_position_risk(
                    symbol=asset,
                    weight=weight,
                    notional=pos_size,
                    volatility=vol,
                    var_95=abs(metrics["var_95"]) * pos_size,
                    cvar_95=abs(metrics["cvar_95"]) * pos_size,
                    marginal_risk=marginal,
                    risk_contribution_pct=risk_contrib,
                    beta=beta,
                )

        # Step 3: Collect risk snapshot
        concentration = 1.0 / max(len(positions or {}), 1)
        snapshot = self.monitor.collect_snapshot(
            portfolio_id=portfolio_id,
            volatility=metrics["volatility"],
            var_95=metrics["var_95"],
            var_99=metrics["var_99"],
            cvar_95=metrics["cvar_95"],
            cvar_99=metrics["cvar_99"],
            drawdown=drawdown,
            max_drawdown=max_drawdown,
            exposure=exposure or {},
            concentration_ratio=concentration,
            sharpe_ratio=0.0,
            position_count=len(positions or {}),
        )

        # Step 4: Volatility targeting adjustment
        vol_adj = self.vol_targeter.compute_adjustment(
            current_volatility=metrics["annualized_volatility"],
            current_position=total_value,
        )

        # Step 5: Generate risk decision
        decision = self.monitor.get_risk_decision()

        return {
            "snapshot": snapshot.to_dict(),
            "risk_metrics": metrics,
            "volatility_adjustment": vol_adj,
            "decision": decision,
            "regime": self.monitor.get_regime_assessment().to_dict(),
            "alerts": self.monitor.get_alerts()[-5:],
        }

    def decide_position_adjustment(
        self,
        portfolio_id: str,
        current_positions: Dict[str, float],
        returns: List[float],
    ) -> Dict[str, Any]:
        """Make a position adjustment decision based on risk.

        Args:
            portfolio_id: Portfolio identifier.
            current_positions: Current positions {symbol: size}.
            returns: Return series.

        Returns:
            Dict with position adjustment plan.
        """
        # Compute current risk
        vol = self.calculator._compute_volatility(returns) * (252 ** 0.5)
        var_95 = abs(self.calculator._parametric_var(returns, 0.95))
        total_value = sum(current_positions.values())

        # Vol targeting
        vol_adj = self.vol_targeter.compute_adjustment(
            current_volatility=vol,
            current_position=total_value,
        )

        # Per-position adjustments
        adjustments = {}
        for symbol, size in current_positions.items():
            target_size = size * vol_adj["scale_factor"]
            adjustments[symbol] = {
                "current": size,
                "target": round(target_size, 2),
                "adjustment": round(target_size - size, 2),
                "action": "REDUCE" if target_size < size else ("INCREASE" if target_size > size else "HOLD"),
            }

        # Ensure we have a snapshot for the decision
        snapshot = self.monitor.get_latest_snapshot()
        if snapshot is None:
            snapshot = self.monitor.collect_snapshot(
                portfolio_id=portfolio_id,
                volatility=vol,
                var_95=var_95,
                var_99=var_95 * 1.4,
                cvar_95=var_95 * 1.5,
                cvar_99=var_95 * 2.0,
                drawdown=0.0,
                max_drawdown=0.0,
                exposure={},
                concentration_ratio=1.0 / max(len(current_positions), 1),
                position_count=len(current_positions),
            )

        self._decision_counter += 1
        decision = RiskDecision(
            decision_id=f"RISK_DEC_{self._decision_counter:04d}",
            portfolio_id=portfolio_id,
            timestamp=datetime.utcnow(),
            risk_snapshot=snapshot,
            action=RiskAction.REDUCE_POSITION if vol_adj["scale_factor"] < 0.95 else RiskAction.NONE,
            target_exposure={s: a["target"] for s, a in adjustments.items()},
            position_adjustments=adjustments,
            reason=f"Volatility targeting: {vol_adj['action']} (scale={vol_adj['scale_factor']:.2f})",
            urgency=self.monitor._compute_urgency(snapshot),
            reduction_pct=max(0.0, (1.0 - vol_adj["scale_factor"])),
        )

        return decision.to_dict()

    def run_stress_test(
        self,
        portfolio_id: str,
        positions: Dict[str, float],
        scenarios: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run stress tests on the portfolio.

        Args:
            portfolio_id: Portfolio identifier.
            positions: Current positions.
            scenarios: Optional list of scenario names to run.

        Returns:
            Dict with stress test results.
        """
        if scenarios is None:
            scenarios = ["market_crash", "liquidity_crisis", "sector_shock"]

        results = []
        for scenario_name in scenarios:
            scenario_def = self.scenario_engine.get_scenario(scenario_name)
            if not scenario_def:
                continue

            result = self.simulator.simulate(scenario_def, positions)
            results.append(result.to_dict() if hasattr(result, 'to_dict') else result)

        total_loss = sum(r.get("loss_pct", 0) for r in results) if results else 0.0
        worst = max(results, key=lambda r: r.get("loss_pct", 0)) if results else {"loss_pct": 0}

        return {
            "portfolio_id": portfolio_id,
            "scenarios_run": len(results),
            "results": results,
            "average_loss": round(total_loss / max(len(results), 1), 4),
            "worst_case": worst,
            "action": "REDUCE_POSITION" if worst.get("loss_pct", 0) > 0.08 else "MONITOR",
        }

    def apply_vol_target(
        self,
        positions: Dict[str, float],
        volatilities: Dict[str, float],
        correlations: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> Dict[str, Any]:
        """Apply volatility targeting to all positions.

        Args:
            positions: Current positions.
            volatilities: Asset volatilities.
            correlations: Optional correlation matrix.

        Returns:
            Dict with adjusted positions.
        """
        return self.vol_targeter.compute_multi_asset_adjustment(
            positions=positions,
            volatilities=volatilities,
            correlations=correlations,
        )

    def get_risk_report(self, portfolio_id: Optional[str] = None) -> Dict[str, Any]:
        """Generate a comprehensive risk report.

        Args:
            portfolio_id: Optional portfolio filter.

        Returns:
            Dict with full risk report.
        """
        snapshot = self.monitor.get_latest_snapshot()
        if not snapshot:
            return {"error": "No data available"}

        return {
            "portfolio": portfolio_id or snapshot.portfolio_id,
            "timestamp": snapshot.timestamp.isoformat(),
            "risk_level": snapshot.risk_level.value,
            "market_regime": snapshot.market_regime.value,
            "metrics": {
                "volatility": snapshot.volatility,
                "var_95": snapshot.var_95,
                "var_99": snapshot.var_99,
                "cvar_95": snapshot.cvar_95,
                "cvar_99": snapshot.cvar_99,
                "drawdown": snapshot.drawdown,
                "max_drawdown": snapshot.max_drawdown,
                "concentration": snapshot.concentration_ratio,
            },
            "exposure": snapshot.exposure,
            "alerts": self.monitor.get_alerts(),
            "position_count": len(self.monitor.position_risks),
            "top_risk_contributors": self.monitor._get_top_contributors(5),
        }
