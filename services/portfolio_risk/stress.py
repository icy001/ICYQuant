"""Portfolio stress testing and scenario analysis (Commit 36 Part 1.5).

Completes the portfolio risk ladder with *"if the market really breaks, how
much do we lose?"*:

.. code-block:: text

    Scenario -> Shock -> Portfolio Revaluation -> Stress Loss
        -> Risk Classification

``PortfolioStressCalculator`` revalues positions under a
``StressScenario`` and aggregates the stress PnL; ``calculate_scenarios``
runs a full Scenario Matrix in one pass.

Design principle: ``positions`` values must carry economic direction
(Long = +, Short = -), so ``Stressed Value = Base Value * (1 + Shock)``
produces the correct PnL for both sides.
"""

from __future__ import annotations

from decimal import Decimal

from .models import (
    PositionShock,
    PositionStressResult,
    StressRiskLevel,
    StressScenario,
    StressTestResult,
)


ZERO = Decimal("0")
ONE = Decimal("1")


class PortfolioStressCalculator:

    def calculate(
        self,
        *,
        portfolio_id: str,
        equity: Decimal,
        positions: dict[str, Decimal],
        scenario: StressScenario,
    ) -> StressTestResult:

        if equity <= ZERO:
            raise ValueError(
                "equity must be greater than zero"
            )

        shock_map = {
            shock.instrument_id: shock
            for shock in scenario.shocks
        }

        position_results = []

        total_pnl_change = ZERO

        for instrument_id, base_value in positions.items():

            shock = shock_map.get(
                instrument_id
            )

            if shock is None:
                stressed_value = base_value
            else:
                stressed_value = (
                    base_value
                    * (
                        ONE
                        + shock.price_shock
                    )
                )

            pnl_change = (
                stressed_value
                - base_value
            )

            pnl_change_pct = (
                ZERO
                if base_value == ZERO
                else pnl_change / base_value
            )

            position_results.append(
                PositionStressResult(
                    instrument_id=instrument_id,
                    base_value=base_value,
                    stressed_value=stressed_value,
                    pnl_change=pnl_change,
                    pnl_change_pct=pnl_change_pct,
                )
            )

            total_pnl_change += pnl_change

        stressed_equity = (
            equity
            + total_pnl_change
        )

        pnl_change_pct = (
            total_pnl_change
            / equity
        )

        return StressTestResult(
            portfolio_id=portfolio_id,
            scenario_id=scenario.scenario_id,
            base_equity=equity,
            stressed_equity=stressed_equity,
            pnl_change=total_pnl_change,
            pnl_change_pct=pnl_change_pct,
            positions=tuple(position_results),
            risk_level=self._classify(
                pnl_change_pct
            ),
        )

    def calculate_scenarios(
        self,
        *,
        portfolio_id: str,
        equity: Decimal,
        positions: dict[str, Decimal],
        scenarios: list[StressScenario],
    ) -> tuple[StressTestResult, ...]:

        return tuple(
            self.calculate(
                portfolio_id=portfolio_id,
                equity=equity,
                positions=positions,
                scenario=scenario,
            )
            for scenario in scenarios
        )

    @staticmethod
    def _classify(
        pnl_change_pct: Decimal,
    ) -> StressRiskLevel:

        loss = -pnl_change_pct

        if loss >= Decimal("0.20"):
            return StressRiskLevel.CRITICAL

        if loss >= Decimal("0.10"):
            return StressRiskLevel.HIGH

        if loss >= Decimal("0.05"):
            return StressRiskLevel.MEDIUM

        return StressRiskLevel.LOW
