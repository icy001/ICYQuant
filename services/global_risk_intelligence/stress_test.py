"""Portfolio Stress Test.

Simulates extreme market scenarios (Fed shocks, oil spikes, dollar
surges, VIX explosions, equity crashes) on portfolio value and
estimates drawdown, worst-case loss, and recovery time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class StressScenario:
    """A stress test scenario definition.

    Attributes:
        name: Scenario name.
        equity_shock: Equity market shock (fraction).
        bond_shock: Bond market shock (fraction).
        fx_shock: FX shock (fraction).
        commodity_shock: Commodity shock (fraction).
        volatility_shock: Volatility spike (VIX multiplier).
        correlation_spike: Correlation amplification (additive).
        liquidity_discount: Additional liquidity discount.
        description: Scenario description.
    """

    name: str = ""
    equity_shock: float = 0.0
    bond_shock: float = 0.0
    fx_shock: float = 0.0
    commodity_shock: float = 0.0
    volatility_shock: float = 1.0
    correlation_spike: float = 0.0
    liquidity_discount: float = 0.0
    description: str = ""


@dataclass
class StressTestResult:
    """Result of a single stress test scenario.

    Attributes:
        scenario: Scenario name.
        portfolio_loss: Estimated portfolio loss (fraction).
        drawdown: Estimated drawdown from peak.
        worst_case_loss: Worst-case tail loss.
        recovery_estimate_days: Estimated days to recover.
        passed: Whether the portfolio survives the test.
        severity: Severity classification.
    """

    scenario: str = ""
    portfolio_loss: float = 0.0
    drawdown: float = 0.0
    worst_case_loss: float = 0.0
    recovery_estimate_days: int = 30
    passed: bool = True
    severity: str = "low"

    @property
    def is_severe(self) -> bool:
        return self.severity in ("high", "extreme")


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class PortfolioStressTest:
    """Runs stress test scenarios on portfolio configurations.

    Evaluates portfolio resilience under extreme market conditions
    using predefined and custom scenario templates.

    Attributes:
        scenarios: Library of stress test scenarios.
    """

    # Predefined stress scenarios
    DEFAULT_SCENARIOS: list[StressScenario] = [
        StressScenario(
            name="Fed +100bp",
            equity_shock=-0.12,
            bond_shock=-0.05,
            fx_shock=0.04,
            volatility_shock=1.5,
            correlation_spike=0.15,
            description="Aggressive rate hike of 100bp",
        ),
        StressScenario(
            name="Oil +30%",
            equity_shock=-0.06,
            commodity_shock=0.30,
            fx_shock=0.03,
            volatility_shock=1.3,
            description="Oil price spikes 30% on supply shock",
        ),
        StressScenario(
            name="USD +10%",
            equity_shock=-0.08,
            fx_shock=0.10,
            commodity_shock=-0.15,
            volatility_shock=1.2,
            correlation_spike=0.1,
            description="Dollar surges 10% against all currencies",
        ),
        StressScenario(
            name="VIX 50",
            equity_shock=-0.15,
            volatility_shock=3.0,
            correlation_spike=0.3,
            liquidity_discount=0.05,
            description="VIX explodes to 50 — fear regime",
        ),
        StressScenario(
            name="NASDAQ -20%",
            equity_shock=-0.20,
            volatility_shock=2.5,
            correlation_spike=0.25,
            liquidity_discount=0.03,
            description="NASDAQ crashes 20% in one week",
        ),
        StressScenario(
            name="Credit Crisis",
            equity_shock=-0.10,
            bond_shock=-0.08,
            fx_shock=0.05,
            volatility_shock=2.0,
            correlation_spike=0.35,
            liquidity_discount=0.08,
            description="Credit market seizure",
        ),
        StressScenario(
            name="EM Contagion",
            equity_shock=-0.12,
            fx_shock=0.08,
            commodity_shock=-0.12,
            volatility_shock=1.8,
            correlation_spike=0.2,
            liquidity_discount=0.04,
            description="Emerging market crisis spreads globally",
        ),
        StressScenario(
            name="Rate Cut Panic",
            equity_shock=-0.18,
            bond_shock=0.03,
            volatility_shock=2.8,
            correlation_spike=0.3,
            liquidity_discount=0.06,
            description="Emergency rate cut triggers panic selling",
        ),
    ]

    def __init__(self, scenarios: Optional[list[StressScenario]] = None) -> None:
        self.scenarios = scenarios or self.DEFAULT_SCENARIOS

    # ------------------------------------------------------------------
    # Stress Testing
    # ------------------------------------------------------------------

    def run(self,
            scenario_name: str,
            equity_weight: float = 0.6,
            bond_weight: float = 0.2,
            fx_exposure: float = 0.1,
            commodity_weight: float = 0.05,
            portfolio_value: float = 1_000_000.0,
            ) -> StressTestResult:
        """Run a named stress test scenario.

        Args:
            scenario_name: Name of the scenario.
            equity_weight: Portfolio equity allocation.
            bond_weight: Portfolio bond allocation.
            fx_exposure: FX exposure.
            commodity_weight: Commodity allocation.
            portfolio_value: Total portfolio value.

        Returns:
            StressTestResult.
        """
        scenario = self._find_scenario(scenario_name)
        if scenario is None:
            return StressTestResult(
                scenario=scenario_name,
                severity="unknown",
            )

        # Compute portfolio impact
        loss = (
            equity_weight * scenario.equity_shock
            + bond_weight * scenario.bond_shock
            + fx_exposure * scenario.fx_shock
            + commodity_weight * scenario.commodity_shock
        )

        # Amplification from correlation spike
        amplification = 1.0 + scenario.correlation_spike
        loss *= amplification

        # Liquidity discount
        loss -= scenario.liquidity_discount

        # Drawdown (includes volatility impact)
        vol_impact = (scenario.volatility_shock - 1.0) * 0.05
        drawdown = loss - vol_impact

        # Worst-case
        worst_case = drawdown * 1.5

        # Recovery estimate (rough: losses recover at ~0.5% per day)
        recovery = int(abs(drawdown) / 0.005) if drawdown < 0 else 5

        # Severity
        severity = self._classify_severity(abs(loss))

        # Pass if loss < 20%
        passed = abs(loss) < 0.20

        return StressTestResult(
            scenario=scenario.name,
            portfolio_loss=round(loss, 4),
            drawdown=round(drawdown, 4),
            worst_case_loss=round(worst_case, 4),
            recovery_estimate_days=recovery,
            passed=passed,
            severity=severity,
        )

    def run_all(self,
                equity_weight: float = 0.6,
                bond_weight: float = 0.2,
                fx_exposure: float = 0.1,
                commodity_weight: float = 0.05,
                portfolio_value: float = 1_000_000.0,
                ) -> list[StressTestResult]:
        """Run all scenarios."""
        results: list[StressTestResult] = []
        for sc in self.scenarios:
            results.append(self.run(
                sc.name, equity_weight, bond_weight,
                fx_exposure, commodity_weight, portfolio_value,
            ))
        return results

    def summary(self, results: list[StressTestResult]) -> dict[str, Any]:
        """Generate a summary across scenario results."""
        if not results:
            return {"total": 0, "passed": 0, "failed": 0}

        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed
        worst = min(results, key=lambda r: r.portfolio_loss)
        worst_case_loss = min(r.worst_case_loss for r in results)
        avg_loss = sum(r.portfolio_loss for r in results) / len(results)
        max_recovery = max(r.recovery_estimate_days for r in results)

        return {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / len(results) * 100, 1) if results else 0,
            "worst_scenario": worst.scenario,
            "worst_case_loss": worst_case_loss,
            "avg_portfolio_loss": round(avg_loss, 4),
            "max_recovery_days": max_recovery,
        }

    # ------------------------------------------------------------------
    # Custom scenarios
    # ------------------------------------------------------------------

    def add_scenario(self, scenario: StressScenario) -> None:
        """Add a custom stress test scenario."""
        self.scenarios.append(scenario)

    def get_scenario_names(self) -> list[str]:
        """List all scenario names."""
        return [s.name for s in self.scenarios]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _find_scenario(self, name: str) -> Optional[StressScenario]:
        name_lower = name.lower()
        for sc in self.scenarios:
            if sc.name.lower() == name_lower:
                return sc
        return None

    def _classify_severity(self, loss: float) -> str:
        if loss >= 0.30:
            return "extreme"
        elif loss >= 0.15:
            return "high"
        elif loss >= 0.05:
            return "medium"
        return "low"

    def clear(self) -> None:
        self.scenarios = []
