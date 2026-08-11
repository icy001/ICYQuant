"""StressRunner — execute stress scenarios and collect results.

Runs stress scenarios through the engine and produces
comprehensive result sets for analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.institutional_risk.stress_engine import (
    StressEngine,
    StressResult,
    StressScenario,
    StressScenarioType,
)
from services.institutional_risk.stress_scenario import (
    ScenarioDefinition,
    ScenarioSeverity,
    StressScenarioLibrary,
)


@dataclass
class StressRunConfig:
    """Configuration for a stress test run."""

    run_historical: bool = True
    run_hypothetical: bool = True
    run_factor: bool = True
    run_liquidity: bool = True
    run_correlation: bool = True
    run_combined: bool = True
    loss_limit_pct: float = 25.0
    survival_threshold: float = 60.0


@dataclass
class StressRunReport:
    """Report from a full stress test run."""

    total_scenarios: int = 0
    passed: int = 0
    failed: int = 0
    results: List[StressResult] = field(default_factory=list)
    worst_scenario: Optional[StressResult] = None
    worst_loss_pct: float = 0.0
    average_loss_pct: float = 0.0
    failures: List[StressResult] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class StressRunner:
    """Runs stress scenarios through the engine.

    Converts ScenarioDefinition to StressScenario, runs them,
    and aggregates results into actionable reports.

    Usage::

        runner = StressRunner()
        report = runner.run_all(
            capital=100_000_000,
            portfolio_composition={"strat_A": {"allocation": 30_000_000, "beta": 1.2}},
            current_risk={"var_99": 8_000_000, "survival": 78},
        )
        if report.failures:
            print(f"WARNING: {len(report.failures)} scenarios failed")
    """

    def __init__(
        self,
        library: Optional[StressScenarioLibrary] = None,
        config: Optional[StressRunConfig] = None,
    ):
        self._library = library or StressScenarioLibrary()
        self._engine = StressEngine()
        self._config = config or StressRunConfig()

    def run_all(
        self,
        capital: float,
        portfolio_composition: Dict[str, Dict[str, Any]],
        current_risk: Optional[Dict[str, float]] = None,
        custom_scenarios: Optional[List[StressScenario]] = None,
    ) -> StressRunReport:
        """Run all configured stress scenarios.

        Args:
            capital: total capital pool value
            portfolio_composition: {strategy_id: {allocation, beta, ...}}
            current_risk: current risk metrics
            custom_scenarios: additional custom scenarios
        """
        report = StressRunReport()
        all_results: List[StressResult] = []

        # convert library scenarios to engine scenarios
        scenarios = self._convert_library_scenarios()

        if custom_scenarios:
            scenarios.extend(custom_scenarios)

        for scenario in scenarios:
            result = self._engine.run(
                scenario, capital, portfolio_composition, current_risk
            )
            all_results.append(result)

            if result.passed:
                report.passed += 1
            else:
                report.failed += 1
                report.failures.append(result)

            if abs(result.portfolio_loss_pct) > report.worst_loss_pct:
                report.worst_loss_pct = abs(result.portfolio_loss_pct)
                report.worst_scenario = result

        report.results = all_results
        report.total_scenarios = len(all_results)

        if all_results:
            report.average_loss_pct = sum(
                abs(r.portfolio_loss_pct) for r in all_results
            ) / len(all_results)

        # generate recommendations
        report.recommendations = self._generate_recommendations(report, capital)

        return report

    def _convert_library_scenarios(self) -> List[StressScenario]:
        """Convert library ScenarioDefinitions to engine StressScenarios."""
        engine_scenarios: List[StressScenario] = []

        for sdef in self._library.list_all():
            scenario = StressScenario(
                name=sdef.name,
                scenario_type=StressScenarioType.HYPOTHETICAL,
                market_shock_pct=sdef.market_shock,
                volatility_shock_pct=sdef.volatility_shock,
                liquidity_shock_pct=sdef.liquidity_shock,
                correlation_shock_pct=sdef.correlation_shock,
                spread_shock_pct=sdef.spread_shock,
                gap_shock_pct=sdef.gap_shock,
                execution_shock_pct=sdef.execution_shock,
                description=sdef.description,
                factor_shocks=sdef.factor_shocks,
            )
            engine_scenarios.append(scenario)

        return engine_scenarios

    def _generate_recommendations(
        self,
        report: StressRunReport,
        capital: float,
    ) -> List[str]:
        """Generate actionable recommendations from stress results."""
        recommendations: List[str] = []

        if report.failed > report.total_scenarios * 0.5:
            recommendations.append(
                f"CRITICAL: {report.failed}/{report.total_scenarios} scenarios fail — "
                "consider significant portfolio adjustment"
            )

        if report.worst_loss_pct > 30.0:
            recommendations.append(
                f"Worst-case loss {report.worst_loss_pct:.1f}% exceeds 30% — "
                "increase capital reserve and reduce leverage"
            )

        if report.worst_scenario and report.worst_scenario.survival_score_under_stress < 40:
            recommendations.append(
                "Survival score drops below 40 under stress — "
                "reduce high-beta and high-correlation positions"
            )

        # check for concentration issues
        if report.worst_scenario:
            strategy_losses = report.worst_scenario.strategy_losses
            if strategy_losses:
                total_loss = sum(abs(l) for l in strategy_losses.values())
                for sid, loss in strategy_losses.items():
                    if total_loss > 0 and abs(loss) / total_loss > 0.5:
                        recommendations.append(
                            f"Concentration risk: {sid} contributes "
                            f"{abs(loss)/total_loss*100:.0f}% of worst-case loss"
                        )

        return recommendations

    def run_single(
        self,
        scenario_id: str,
        capital: float,
        portfolio_composition: Dict[str, Dict[str, Any]],
        current_risk: Optional[Dict[str, float]] = None,
    ) -> Optional[StressResult]:
        """Run a single scenario by ID."""
        sdef = self._library.get(scenario_id)
        if sdef is None:
            return None

        scenario = StressScenario(
            name=sdef.name,
            scenario_type=StressScenarioType.HISTORICAL,
            market_shock_pct=sdef.market_shock,
            volatility_shock_pct=sdef.volatility_shock,
            liquidity_shock_pct=sdef.liquidity_shock,
            correlation_shock_pct=sdef.correlation_shock,
            spread_shock_pct=sdef.spread_shock,
            gap_shock_pct=sdef.gap_shock,
            execution_shock_pct=sdef.execution_shock,
            description=sdef.description,
        )

        return self._engine.run(scenario, capital, portfolio_composition, current_risk)
