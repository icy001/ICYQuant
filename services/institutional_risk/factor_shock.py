"""FactorShock — simulate factor-level shock scenarios.

Simulates what happens when a specific factor experiences a
large move, e.g., "AI factor drops 20%".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class FactorShockScenario:
    """A factor shock scenario definition."""

    factor: str
    shock_pct: float  # e.g., -20.0 for -20%
    probability: float = 0.01
    description: str = ""


@dataclass
class FactorShockResult:
    """Result of applying a factor shock."""

    scenario: FactorShockScenario
    strategy_impacts: Dict[str, float] = field(default_factory=dict)
    total_portfolio_impact: float = 0.0
    total_capital_impact: float = 0.0
    impacted_strategies: List[str] = field(default_factory=list)
    risk_increase_pct: float = 0.0
    var_impact: float = 0.0


class FactorShockSimulator:
    """Simulates factor-level shock scenarios.

    Applies factor shocks to compute strategy and portfolio losses,
    enabling factor-based stress testing.

    Usage::

        sim = FactorShockSimulator()
        result = sim.simulate(
            scenario=FactorShockScenario(factor="AI", shock_pct=-20.0),
            strategy_exposures={"strat_A": {"AI": 1.7}},
            capital_allocated={"strat_A": 30_000_000},
        )
        print(f"Portfolio impact: {result.total_portfolio_impact:.0f}")
    """

    def simulate(
        self,
        scenario: FactorShockScenario,
        strategy_exposures: Dict[str, Dict[str, float]],
        capital_allocated: Dict[str, float],
        factor_betas: Optional[Dict[str, float]] = None,
    ) -> FactorShockResult:
        """Simulate a factor shock.

        Args:
            scenario: the shock scenario
            strategy_exposures: {strategy_id: {factor: exposure}}
            capital_allocated: {strategy_id: capital_amount}
            factor_betas: optional factor betas for P&L translation
        """
        result = FactorShockResult(scenario=scenario)

        shock_decimal = scenario.shock_pct / 100.0
        total_impact = 0.0

        for sid, exposures in strategy_exposures.items():
            factor_exp = exposures.get(scenario.factor, 0.0)
            if factor_exp == 0.0:
                continue

            capital = capital_allocated.get(sid, 0.0)
            impact = capital * factor_exp * shock_decimal
            result.strategy_impacts[sid] = impact
            total_impact += impact

            if abs(impact) > capital * 0.01:  # >1% impact
                result.impacted_strategies.append(sid)

        result.total_portfolio_impact = total_impact
        result.total_capital_impact = total_impact

        return result

    def simulate_multi_factor(
        self,
        scenarios: List[FactorShockScenario],
        strategy_exposures: Dict[str, Dict[str, float]],
        capital_allocated: Dict[str, float],
    ) -> List[FactorShockResult]:
        """Simulate multiple factor shocks simultaneously."""
        results = []
        for scenario in scenarios:
            result = self.simulate(scenario, strategy_exposures, capital_allocated)
            results.append(result)
        return results

    def find_worst_factor(
        self,
        strategy_exposures: Dict[str, Dict[str, float]],
        capital_allocated: Dict[str, float],
        shock_pct: float = -20.0,
    ) -> Tuple[str, float]:
        """Find the factor that would cause the worst loss."""
        all_factors: set = set()
        for exposures in strategy_exposures.values():
            all_factors.update(exposures.keys())

        worst_factor = ""
        worst_impact = 0.0

        for factor in all_factors:
            scenario = FactorShockScenario(
                factor=factor,
                shock_pct=shock_pct,
                description=f"Auto-generated {factor} shock",
            )
            result = self.simulate(scenario, strategy_exposures, capital_allocated)
            impact = abs(result.total_portfolio_impact)
            if impact > worst_impact:
                worst_impact = impact
                worst_factor = factor

        return worst_factor, worst_impact

    def compute_factor_stress_matrix(
        self,
        factors: List[str],
        shock_levels: List[float],
        strategy_exposures: Dict[str, Dict[str, float]],
        capital_allocated: Dict[str, float],
    ) -> Dict[str, Dict[float, float]]:
        """Compute a factor-by-shock-level stress matrix.

        Returns:
            {factor: {shock%: portfolio_impact}}
        """
        matrix: Dict[str, Dict[float, float]] = {}
        for factor in factors:
            matrix[factor] = {}
            for shock in shock_levels:
                scenario = FactorShockScenario(factor=factor, shock_pct=shock)
                result = self.simulate(scenario, strategy_exposures, capital_allocated)
                matrix[factor][shock] = result.total_portfolio_impact
        return matrix
