"""Stress Test Engine – simulate extreme market scenarios."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StressTestResult:
    """Result of a single stress test scenario.

    Captures the scenario definition, projected portfolio loss,
    drawdown, estimated recovery time, and pass/fail status.
    """

    scenario_name: str
    portfolio_loss: float  # negative value
    drawdown: float  # negative value
    recovery_time_days: int
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "scenario_name": self.scenario_name,
            "portfolio_loss": self.portfolio_loss,
            "drawdown": self.drawdown,
            "recovery_time_days": self.recovery_time_days,
            "passed": self.passed,
            "details": self.details,
        }


class StressTestEngine:
    """Runs stress tests against a portfolio using predefined scenarios.

    Each scenario applies shocks to asset prices and computes the
    resulting portfolio loss, drawdown, and recovery profile.
    """

    def __init__(
        self,
        max_acceptable_loss: float = 0.20,
        max_acceptable_drawdown: float = 0.25,
    ):
        self.max_acceptable_loss = max_acceptable_loss
        self.max_acceptable_drawdown = max_acceptable_drawdown

    def run(
        self,
        scenario: str,
        portfolio_value: float = 1_000_000.0,
        price_shock: float = -0.10,
        correlation_amplification: float = 0.0,
        liquidity_discount: float = 0.0,
    ) -> StressTestResult:
        """Run a stress test scenario.

        Args:
            scenario: Name of the stress scenario
            portfolio_value: Current portfolio value
            price_shock: Price movement shock (e.g., -0.10 = -10%)
            correlation_amplification: Additional correlation effect (0-1)
            liquidity_discount: Fire-sale discount on exits (0-1)
        """
        # Base loss from price shock
        base_loss = price_shock

        # Amplify by correlation breakdown
        amplified_loss = base_loss * (1 + correlation_amplification)

        # Add liquidity cost
        total_loss = amplified_loss - liquidity_discount

        # Clamp to realistic range
        total_loss = max(total_loss, -1.0)
        portfolio_loss = total_loss

        # Drawdown typically slightly worse than final loss
        drawdown = total_loss * (1 + abs(correlation_amplification) * 0.5)
        drawdown = max(drawdown, -1.0)

        # Recovery time estimate (days)
        if abs(total_loss) < 0.05:
            recovery_time_days = 5
        elif abs(total_loss) < 0.15:
            recovery_time_days = 21
        elif abs(total_loss) < 0.30:
            recovery_time_days = 60
        else:
            recovery_time_days = 120

        # Pass/fail
        passed = (
            abs(portfolio_loss) <= self.max_acceptable_loss
            and abs(drawdown) <= self.max_acceptable_drawdown
        )

        return StressTestResult(
            scenario_name=scenario,
            portfolio_loss=round(portfolio_loss, 4),
            drawdown=round(drawdown, 4),
            recovery_time_days=recovery_time_days,
            passed=passed,
            details={
                "price_shock": price_shock,
                "correlation_amplification": correlation_amplification,
                "liquidity_discount": liquidity_discount,
                "portfolio_value": portfolio_value,
            },
        )

    def run_simple(self, scenario: str) -> dict:
        """Legacy simple run returning scenario and fixed loss."""
        return {"scenario": scenario, "loss": -0.1}

    def run_batch(
        self,
        scenarios: List[Dict[str, Any]],
        portfolio_value: float = 1_000_000.0,
    ) -> List[StressTestResult]:
        """Run multiple stress test scenarios in batch.

        Each scenario dict should contain: name, price_shock, and
        optionally correlation_amplification, liquidity_discount.
        """
        results: List[StressTestResult] = []
        for sc in scenarios:
            result = self.run(
                scenario=sc.get("name", "unnamed"),
                portfolio_value=portfolio_value,
                price_shock=sc.get("price_shock", -0.10),
                correlation_amplification=sc.get(
                    "correlation_amplification", 0.0
                ),
                liquidity_discount=sc.get("liquidity_discount", 0.0),
            )
            results.append(result)
        return results

    def summary(self, results: List[StressTestResult]) -> dict:
        """Generate a summary of batch stress test results."""
        if not results:
            return {"total": 0, "passed": 0, "failed": 0}

        passed_count = sum(1 for r in results if r.passed)
        max_loss = min(r.portfolio_loss for r in results)
        max_drawdown = min(r.drawdown for r in results)

        return {
            "total": len(results),
            "passed": passed_count,
            "failed": len(results) - passed_count,
            "max_loss": max_loss,
            "max_drawdown": max_drawdown,
            "worst_scenario": next(
                (r.scenario_name for r in results
                 if r.portfolio_loss == max_loss),
                "",
            ),
        }
