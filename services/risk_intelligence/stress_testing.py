"""ICYQuant Stress Testing Engine.

Monte Carlo, historical scenario, and hypothetical stress testing
for portfolio and position-level risk assessment.

Usage::

    engine = StressTestEngine(StressTestConfig())
    results = engine.run_all_stress_tests(portfolio, scenarios)
    print(results.summary())
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from services.risk_intelligence.config import (
    StressTestConfig,
    StressScenarioType,
)


# ============================================================================
# Data Types
# ============================================================================


@dataclass
class StressScenario:
    """Stress test scenario definition."""

    name: str
    scenario_type: StressScenarioType = StressScenarioType.HYPOTHETICAL
    description: str = ""
    shocks: Dict[str, float] = field(default_factory=dict)
    correlations: Optional[Dict[str, float]] = None
    duration_days: int = 10
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StressTestResult:
    """Result of a single stress scenario run."""

    scenario_name: str
    initial_value: float
    stressed_value: float
    pnl: float
    pnl_pct: float
    max_drawdown: float = 0.0
    estimated_var_99: float = 0.0
    estimated_cvar_99: float = 0.0
    worst_case: float = 0.0
    num_simulations: int = 0
    passed: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "initial_value": round(self.initial_value, 2),
            "stressed_value": round(self.stressed_value, 2),
            "pnl": round(self.pnl, 2),
            "pnl_pct": round(self.pnl_pct, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "estimated_var_99": round(self.estimated_var_99, 2),
            "estimated_cvar_99": round(self.estimated_cvar_99, 2),
            "worst_case": round(self.worst_case, 2),
            "passed": self.passed,
        }


@dataclass
class StressReport:
    """Aggregated stress test report."""

    scenario_results: List[StressTestResult] = field(default_factory=list)
    overall_pass: bool = True
    max_loss_scenario: str = ""
    max_loss_pct: float = 0.0
    worst_case_loss: float = 0.0
    generated_at: datetime = field(default_factory=datetime.utcnow)
    recommendation: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_results": [r.to_dict() for r in self.scenario_results],
            "overall_pass": self.overall_pass,
            "max_loss_scenario": self.max_loss_scenario,
            "max_loss_pct": round(self.max_loss_pct, 4),
            "worst_case_loss": round(self.worst_case_loss, 2),
            "recommendation": self.recommendation,
            "generated_at": self.generated_at.isoformat(),
        }


# ============================================================================
# Stress Test Engine
# ============================================================================


class StressTestEngine:
    """Portfolio Stress Test Engine.

    Runs Monte Carlo simulations, historical scenarios, and hypothetical
    stress tests to assess portfolio resilience.

    Usage::

        engine = StressTestEngine(StressTestConfig())
        report = engine.run_all_stress_tests(portfolio, scenarios)
    """

    def __init__(self, config: Optional[StressTestConfig] = None) -> None:
        self.config = config or StressTestConfig()
        self._history: List[StressReport] = []

    # ------------------------------------------------------------------
    # Monte Carlo
    # ------------------------------------------------------------------

    def monte_carlo(
        self,
        portfolio_value: float,
        returns: List[float],
        num_simulations: Optional[int] = None,
        horizon_days: int = 10,
    ) -> StressTestResult:
        """Run Monte Carlo stress test.

        Args:
            portfolio_value: Current portfolio value.
            returns: Historical return series.
            num_simulations: Number of MC paths.
            horizon_days: Simulation horizon in days.

        Returns:
            StressTestResult with worst-case and VaR estimates.
        """
        num_simulations = num_simulations or self.config.default_num_simulations

        if len(returns) < 20:
            return StressTestResult(
                scenario_name="Monte Carlo",
                initial_value=portfolio_value,
                stressed_value=portfolio_value,
                pnl=0.0,
                pnl_pct=0.0,
                num_simulations=num_simulations,
            )

        mu = sum(returns) / len(returns)
        vol = self._compute_volatility(returns)

        # Simulate paths
        path_pnls: List[float] = []
        random.seed(42)

        for _ in range(num_simulations):
            path_return = 0.0
            for _ in range(horizon_days):
                shock = random.gauss(mu, vol)
                path_return += shock
            path_pnls.append(path_return)

        path_pnls.sort()

        n = len(path_pnls)
        idx_99 = max(0, int(n * self.config.confidence_level) - 1)
        idx_97 = max(0, int(n * 0.975) - 1)
        var_99 = abs(path_pnls[n - 1 - idx_99]) * portfolio_value
        cvar_99 = (
            sum(abs(p) for p in path_pnls[n - 1 - idx_99:])
            / max(1, n - idx_99)
        ) * portfolio_value
        worst_case = abs(min(path_pnls)) * portfolio_value
        stressed_value = portfolio_value * (1 + path_pnls[int(n * 0.05)])

        pnl = stressed_value - portfolio_value
        pnl_pct = pnl / portfolio_value if portfolio_value > 0 else 0.0

        return StressTestResult(
            scenario_name="Monte Carlo",
            initial_value=portfolio_value,
            stressed_value=stressed_value,
            pnl=pnl,
            pnl_pct=pnl_pct,
            estimated_var_99=var_99,
            estimated_cvar_99=cvar_99,
            worst_case=worst_case,
            num_simulations=num_simulations,
            passed=abs(pnl_pct) <= 0.20,
        )

    # ------------------------------------------------------------------
    # Scenario-Based Stress
    # ------------------------------------------------------------------

    def run_scenario(
        self,
        portfolio_value: float,
        positions: Dict[str, float],
        scenario: StressScenario,
    ) -> StressTestResult:
        """Stress test against a specific scenario.

        Args:
            portfolio_value: Total portfolio value.
            positions: {asset_id: market_value}.
            scenario: StressScenario definition.

        Returns:
            StressTestResult.
        """
        total_loss = 0.0
        max_dd = 0.0

        for asset, value in positions.items():
            weight = value / portfolio_value if portfolio_value > 0 else 0.0
            shock = scenario.shocks.get(asset, 0.0)

            # Apply correlation amplification if provided
            if scenario.correlations:
                corr = scenario.correlations.get(asset, 0.0)
                if corr < 0:
                    shock *= (1.0 + abs(corr) * 0.5)

            loss = value * shock
            total_loss += loss

            asset_dd = abs(shock)
            if asset_dd > max_dd:
                max_dd = asset_dd

        stressed_value = portfolio_value + total_loss
        pnl_pct = total_loss / portfolio_value if portfolio_value > 0 else 0.0

        return StressTestResult(
            scenario_name=scenario.name,
            initial_value=portfolio_value,
            stressed_value=stressed_value,
            pnl=total_loss,
            pnl_pct=pnl_pct,
            max_drawdown=max_dd,
            worst_case=total_loss * 1.5,
            passed=abs(pnl_pct) <= 0.15,
            metadata={"scenario_type": scenario.scenario_type.value},
        )

    def run_all_stress_tests(
        self,
        portfolio_value: float,
        positions: Dict[str, float],
        scenarios: List[StressScenario],
        returns: Optional[List[float]] = None,
        loss_limit_pct: float = 0.20,
    ) -> StressReport:
        """Run all configured stress tests.

        Args:
            portfolio_value: Current portfolio value.
            positions: Position map {asset_id: market_value}.
            scenarios: List of stress scenarios.
            returns: Historical returns for MC.
            loss_limit_pct: Maximum acceptable loss percentage.

        Returns:
            StressReport with aggregated results.
        """
        results: List[StressTestResult] = []

        # Monte Carlo simulation
        if returns and len(returns) >= 20:
            mc_result = self.monte_carlo(portfolio_value, returns)
            results.append(mc_result)

        # Scenario-based tests
        for scenario in scenarios:
            result = self.run_scenario(portfolio_value, positions, scenario)
            results.append(result)

        # Aggregate
        max_loss = 0.0
        max_loss_scenario = ""
        max_loss_pct = 0.0
        worst_case = 0.0
        any_failed = False

        for r in results:
            if abs(r.pnl) > max_loss:
                max_loss = abs(r.pnl)
                max_loss_scenario = r.scenario_name
            if abs(r.pnl_pct) > abs(max_loss_pct):
                max_loss_pct = r.pnl_pct
            if r.worst_case > worst_case:
                worst_case = r.worst_case
            if not r.passed:
                any_failed = not any_failed

        # Generate recommendation
        if abs(max_loss_pct) > loss_limit_pct:
            recommendation = (
                f"CRITICAL: Max loss {max_loss_pct:.1%} exceeds limit "
                f"{loss_limit_pct:.1%}. Immediate position reduction required."
            )
        elif abs(max_loss_pct) > loss_limit_pct * 0.7:
            recommendation = (
                f"WARNING: Max loss {max_loss_pct:.1%} approaches limit. "
                "Consider hedging or reducing exposure."
            )
        elif any_failed:
            recommendation = (
                "Some stress tests failed. Review scenario results."
            )
        else:
            recommendation = "Portfolio resilient under all scenarios."

        report = StressReport(
            scenario_results=results,
            overall_pass=not any_failed,
            max_loss_scenario=max_loss_scenario,
            max_loss_pct=max_loss_pct,
            worst_case_loss=worst_case,
            recommendation=recommendation,
        )

        self._history.append(report)
        if len(self._history) > 100:
            self._history = self._history[-100:]

        return report

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _compute_volatility(self, returns: List[float]) -> float:
        """Compute daily volatility from returns."""
        if len(returns) < 2:
            return 0.01
        mean = sum(returns) / len(returns)
        var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        return math.sqrt(max(var, 0))

    def get_history(self, limit: int = 20) -> List[StressReport]:
        """Get recent stress test reports."""
        return self._history[-limit:]

    def quick_check(
        self,
        portfolio_value: float,
        positions: Dict[str, float],
        returns: List[float],
    ) -> Dict[str, Any]:
        """Quick stress check with default parameters."""
        mc = self.monte_carlo(portfolio_value, returns, num_simulations=1000)
        return {
            "var_99": round(mc.estimated_var_99, 2),
            "cvar_99": round(mc.estimated_cvar_99, 2),
            "worst_case": round(mc.worst_case, 2),
            "worst_case_pct": round(mc.worst_case / portfolio_value, 4),
            "num_positions": len(positions),
        }
