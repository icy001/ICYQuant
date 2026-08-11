"""StressEngine — unified stress testing engine.

Supports historical scenarios, hypothetical scenarios, factor shocks,
liquidity scenarios, and portfolio-level stress tests.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional


class StressScenarioType(Enum):
    HISTORICAL = auto()
    HYPOTHETICAL = auto()
    FACTOR = auto()
    LIQUIDITY = auto()
    PORTFOLIO = auto()
    CORRELATION = auto()
    COMBINED = auto()


@dataclass
class StressScenario:
    """A stress scenario definition."""

    name: str
    scenario_type: StressScenarioType
    market_shock_pct: float = 0.0
    volatility_shock_pct: float = 0.0
    liquidity_shock_pct: float = 0.0
    correlation_shock_pct: float = 0.0
    spread_shock_pct: float = 0.0
    gap_shock_pct: float = 0.0
    execution_shock_pct: float = 0.0
    probability: float = 0.01
    description: str = ""
    factor_shocks: Dict[str, float] = field(default_factory=dict)


@dataclass
class StressResult:
    """Result of a stress test."""

    scenario_name: str
    portfolio_loss: float = 0.0
    portfolio_loss_pct: float = 0.0
    capital_remaining: float = 0.0
    capital_loss_pct: float = 0.0
    var_under_stress: float = 0.0
    es_under_stress: float = 0.0
    drawdown_under_stress: float = 0.0
    survival_score_under_stress: float = 0.0
    strategy_losses: Dict[str, float] = field(default_factory=dict)
    margin_requirement: float = 0.0
    liquidity_requirement: float = 0.0
    recovery_requirement: float = 0.0
    passed: bool = True
    reason: str = ""


class StressEngine:
    """Unified stress testing engine.

    Applies stress scenarios to portfolios and computes resulting
    P&L, capital loss, margin requirements, etc.

    Usage::

        engine = StressEngine()
        scenario = StressScenario(
            name="Market Crash",
            scenario_type=StressScenarioType.HYPOTHETICAL,
            market_shock_pct=-15.0,
            volatility_shock_pct=100.0,
            liquidity_shock_pct=-50.0,
        )
        result = engine.run(scenario, portfolio=100_000_000, exposures=...)
        if not result.passed:
            print(f"FAILED: {result.reason}")
    """

    def __init__(self, stress_loss_limit_pct: float = 25.0):
        self._stress_loss_limit = stress_loss_limit_pct

    def run(
        self,
        scenario: StressScenario,
        capital: float,
        portfolio_composition: Dict[str, Dict[str, Any]],
        current_risk: Optional[Dict[str, float]] = None,
        factor_exposures: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> StressResult:
        """Run a stress scenario.

        Args:
            scenario: stress scenario definition
            capital: current capital pool value
            portfolio_composition: {strategy_id: {"allocation": float, "beta": float, ...}}
            current_risk: current risk metrics {var_99, es_99, dd_pct, survival}
            factor_exposures: per-strategy factor exposures
        """
        result = StressResult(scenario_name=scenario.name)

        total_loss = 0.0
        strategy_losses: Dict[str, float] = {}

        for sid, comp in portfolio_composition.items():
            allocation = comp.get("allocation", 0.0)
            beta = comp.get("beta", 1.0)
            liquidity_factor = comp.get("liquidity_factor", 1.0)
            leverage = comp.get("leverage", 1.0)

            # market shock impact
            market_impact = allocation * beta * (scenario.market_shock_pct / 100.0)

            # volatility impact on beta
            vol_adj_beta = beta * (1.0 + scenario.volatility_shock_pct / 100.0)
            vol_impact = allocation * (vol_adj_beta - beta) * (scenario.market_shock_pct / 100.0)

            # liquidity impact
            liq_impact = allocation * liquidity_factor * (scenario.liquidity_shock_pct / 100.0)

            # correlation impact: diversification loss
            corr_impact = allocation * beta * (scenario.correlation_shock_pct / 100.0) * 0.5

            # spread impact
            spread_impact = allocation * (scenario.spread_shock_pct / 100.0) * 0.3

            # gap impact
            gap_impact = allocation * (scenario.gap_shock_pct / 100.0) * 0.2

            # execution impact
            exec_impact = allocation * (scenario.execution_shock_pct / 100.0) * 0.1

            strategy_loss = (
                market_impact + vol_impact + liq_impact + corr_impact
                + spread_impact + gap_impact + exec_impact
            ) * leverage

            strategy_losses[sid] = strategy_loss
            total_loss += strategy_loss

        result.portfolio_loss = total_loss
        result.portfolio_loss_pct = (total_loss / max(capital, 1e-9)) * 100 if capital > 0 else 0.0
        result.capital_remaining = capital + total_loss
        result.capital_loss_pct = abs(result.portfolio_loss_pct)
        result.strategy_losses = strategy_losses

        # risk under stress
        if current_risk:
            market_ratio = 1.0 + scenario.market_shock_pct / 100.0
            vol_ratio = 1.0 + scenario.volatility_shock_pct / 100.0
            liq_ratio = 1.0 + scenario.liquidity_shock_pct / 100.0
            corr_ratio = 1.0 + scenario.correlation_shock_pct / 100.0

            stress_multiplier = abs(market_ratio) * abs(vol_ratio) * liq_ratio * corr_ratio

            result.var_under_stress = current_risk.get("var_99", 0.0) * stress_multiplier
            result.es_under_stress = current_risk.get("es_99", 0.0) * stress_multiplier
            result.drawdown_under_stress = (
                current_risk.get("dd_pct", 0.0) + abs(result.portfolio_loss_pct)
            )

        # margin requirement
        result.margin_requirement = abs(total_loss) * 0.25

        # liquidity requirement
        result.liquidity_requirement = abs(total_loss) * 1.5

        # recovery requirement
        if result.capital_remaining > 0:
            result.recovery_requirement = (capital / result.capital_remaining - 1) * 100

        # survival score under stress
        survival_base = current_risk.get("survival", 100.0) if current_risk else 100.0
        survival_drop = abs(result.capital_loss_pct) * 2.0
        result.survival_score_under_stress = max(0.0, survival_base - survival_drop)

        # pass/fail
        result.passed = True
        if abs(result.portfolio_loss_pct) > self._stress_loss_limit:
            result.passed = False
            result.reason = (
                f"Stress loss {abs(result.portfolio_loss_pct):.1f}% "
                f"exceeds limit {self._stress_loss_limit}%"
            )

        return result

    def run_batch(
        self,
        scenarios: List[StressScenario],
        capital: float,
        portfolio_composition: Dict[str, Dict[str, Any]],
        current_risk: Optional[Dict[str, float]] = None,
    ) -> List[StressResult]:
        """Run multiple stress scenarios."""
        return [
            self.run(s, capital, portfolio_composition, current_risk)
            for s in scenarios
        ]

    @classmethod
    def predefined_scenarios(cls) -> List[StressScenario]:
        """Get standard predefined stress scenarios."""
        return [
            StressScenario(
                name="Market Crash -5%",
                scenario_type=StressScenarioType.HYPOTHETICAL,
                market_shock_pct=-5.0,
                volatility_shock_pct=50.0,
                liquidity_shock_pct=-20.0,
                description="Moderate market correction",
            ),
            StressScenario(
                name="Market Crash -10%",
                scenario_type=StressScenarioType.HYPOTHETICAL,
                market_shock_pct=-10.0,
                volatility_shock_pct=75.0,
                liquidity_shock_pct=-30.0,
                correlation_shock_pct=20.0,
                description="Significant market decline",
            ),
            StressScenario(
                name="Market Crash -20%",
                scenario_type=StressScenarioType.HYPOTHETICAL,
                market_shock_pct=-20.0,
                volatility_shock_pct=100.0,
                liquidity_shock_pct=-50.0,
                correlation_shock_pct=40.0,
                spread_shock_pct=80.0,
                description="Severe market crash",
            ),
            StressScenario(
                name="Liquidity Crisis",
                scenario_type=StressScenarioType.LIQUIDITY,
                market_shock_pct=-10.0,
                liquidity_shock_pct=-60.0,
                spread_shock_pct=100.0,
                execution_shock_pct=-40.0,
                description="Liquidity evaporation scenario",
            ),
            StressScenario(
                name="Correlation +50%",
                scenario_type=StressScenarioType.CORRELATION,
                correlation_shock_pct=50.0,
                volatility_shock_pct=30.0,
                description="Diversification collapse",
            ),
            StressScenario(
                name="Combined Crisis",
                scenario_type=StressScenarioType.COMBINED,
                market_shock_pct=-15.0,
                volatility_shock_pct=100.0,
                liquidity_shock_pct=-50.0,
                correlation_shock_pct=50.0,
                spread_shock_pct=100.0,
                gap_shock_pct=-10.0,
                execution_shock_pct=-30.0,
                description="Worst-case combined shock",
            ),
        ]
