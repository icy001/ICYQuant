"""Rolling performance analytics (Commit 35 Part 1.5).

Upgrades every previously implemented performance metric into a rolling
window analysis capability:

.. code-block:: text

    Daily Performance
    TWR / MWR
    Benchmark / Active Return
    Volatility / Sharpe / Sortino
    Drawdown / Calmar

Each window produces a :class:`RollingPerformanceResult` that combines
compounded total return, annualized return and the core risk-adjusted
metrics evaluated on the trailing window only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .risk_metrics import (
    RiskAdjustedPerformanceCalculator,
)
from .returns import (
    PortfolioReturnCalculator,
)


ZERO = Decimal("0")


@dataclass(frozen=True)
class RollingPerformanceResult:
    as_of_date: date

    window_size: int

    total_return: Decimal
    annualized_return: Decimal

    volatility: Decimal
    sharpe_ratio: Decimal
    sortino_ratio: Decimal

    maximum_drawdown: Decimal
    calmar_ratio: Decimal


class RollingPerformanceCalculator:
    """
    Rolling performance analytics.

    Slides a fixed-size window across a series of dated returns and computes
    the performance / risk metrics on each trailing window.
    """

    def __init__(
        self,
        return_calculator: PortfolioReturnCalculator | None = None,
        risk_calculator: (
            RiskAdjustedPerformanceCalculator | None
        ) = None,
    ) -> None:

        self._return_calculator = (
            return_calculator
            or PortfolioReturnCalculator()
        )

        self._risk_calculator = (
            risk_calculator
            or RiskAdjustedPerformanceCalculator()
        )

    def calculate(
        self,
        *,
        dates: list[date],
        returns: list[Decimal],
        window_size: int,
        annualization_factor: int = 252,
        risk_free_rate: Decimal = ZERO,
        target_return: Decimal = ZERO,
    ) -> list[RollingPerformanceResult]:

        if len(dates) != len(returns):
            raise ValueError(
                "dates and returns must have the same length"
            )

        if window_size <= 0:
            raise ValueError(
                "window_size must be greater than zero"
            )

        if len(returns) < window_size:
            return []

        results: list[
            RollingPerformanceResult
        ] = []

        for end_index in range(
            window_size - 1,
            len(returns),
        ):

            start_index = (
                end_index
                - window_size
                + 1
            )

            window_returns = returns[
                start_index:
                end_index + 1
            ]

            total_return = (
                self._return_calculator.calculate_twr(
                    window_returns
                )
            )

            annualized_return = (
                self._annualized_return(
                    window_returns,
                    annualization_factor,
                )
            )

            volatility = (
                self._risk_calculator.volatility(
                    window_returns,
                    annualization_factor=annualization_factor,
                )
            )

            sharpe_ratio = (
                self._risk_calculator.sharpe_ratio(
                    window_returns,
                    risk_free_rate=risk_free_rate,
                    annualization_factor=annualization_factor,
                )
            )

            sortino_ratio = (
                self._risk_calculator.sortino_ratio(
                    window_returns,
                    target_return=target_return,
                    annualization_factor=annualization_factor,
                )
            )

            maximum_drawdown = (
                self._risk_calculator.maximum_drawdown(
                    window_returns
                )
            )

            calmar_ratio = (
                self._risk_calculator.calmar_ratio(
                    window_returns,
                    annualization_factor=annualization_factor,
                )
            )

            results.append(
                RollingPerformanceResult(
                    as_of_date=dates[end_index],
                    window_size=window_size,
                    total_return=total_return,
                    annualized_return=annualized_return,
                    volatility=volatility,
                    sharpe_ratio=sharpe_ratio,
                    sortino_ratio=sortino_ratio,
                    maximum_drawdown=maximum_drawdown,
                    calmar_ratio=calmar_ratio,
                )
            )

        return results

    @staticmethod
    def _annualized_return(
        returns: list[Decimal],
        annualization_factor: int,
    ) -> Decimal:

        if not returns:
            return ZERO

        wealth = 1.0

        for value in returns:
            wealth *= 1.0 + float(value)

        years = (
            len(returns)
            / annualization_factor
        )

        if years <= 0:
            return ZERO

        annualized = (
            wealth ** (1.0 / years)
        ) - 1.0

        return Decimal(
            str(annualized)
        )
