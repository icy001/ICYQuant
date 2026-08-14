"""Risk-adjusted portfolio performance metrics (Commit 35 Part 1.4).

Provides the risk-adjusted performance layer that answers:

.. code-block:: text

    Is the return worth the risk taken?

Supported metrics:

- Volatility
- Downside deviation
- Sharpe ratio
- Sortino ratio
- Maximum drawdown
- Calmar ratio
- Information ratio
- Beta
"""

from __future__ import annotations

from decimal import Decimal
from math import sqrt


ZERO = Decimal("0")
ONE = Decimal("1")


class RiskAdjustedPerformanceCalculator:
    """
    Risk-adjusted portfolio performance metrics.

    Supported metrics:

    - Volatility
    - Downside deviation
    - Sharpe ratio
    - Sortino ratio
    - Maximum drawdown
    - Calmar ratio
    - Information ratio
    - Beta
    """

    def volatility(
        self,
        returns: list[Decimal],
        *,
        annualization_factor: int = 252,
    ) -> Decimal:

        if len(returns) < 2:
            return ZERO

        values = [float(value) for value in returns]

        mean = sum(values) / len(values)

        variance = sum(
            (value - mean) ** 2
            for value in values
        ) / (len(values) - 1)

        return Decimal(
            str(
                sqrt(variance)
                * sqrt(annualization_factor)
            )
        )

    def downside_deviation(
        self,
        returns: list[Decimal],
        *,
        target_return: Decimal = ZERO,
        annualization_factor: int = 252,
    ) -> Decimal:

        if not returns:
            return ZERO

        downside = [
            min(
                float(value - target_return),
                0.0,
            )
            for value in returns
        ]

        squared = [
            value ** 2
            for value in downside
        ]

        mean_squared = (
            sum(squared)
            / len(squared)
        )

        return Decimal(
            str(
                sqrt(mean_squared)
                * sqrt(annualization_factor)
            )
        )

    def sharpe_ratio(
        self,
        returns: list[Decimal],
        *,
        risk_free_rate: Decimal = ZERO,
        annualization_factor: int = 252,
    ) -> Decimal:

        if len(returns) < 2:
            return ZERO

        annualized_return = (
            self._annualized_return(
                returns,
                annualization_factor,
            )
        )

        volatility = self.volatility(
            returns,
            annualization_factor=annualization_factor,
        )

        if volatility == ZERO:
            return ZERO

        return (
            annualized_return
            - risk_free_rate
        ) / volatility

    def sortino_ratio(
        self,
        returns: list[Decimal],
        *,
        target_return: Decimal = ZERO,
        annualization_factor: int = 252,
    ) -> Decimal:

        if not returns:
            return ZERO

        annualized_return = (
            self._annualized_return(
                returns,
                annualization_factor,
            )
        )

        downside = self.downside_deviation(
            returns,
            target_return=target_return,
            annualization_factor=annualization_factor,
        )

        if downside == ZERO:
            return ZERO

        return (
            annualized_return
            - target_return
        ) / downside

    def maximum_drawdown(
        self,
        returns: list[Decimal],
    ) -> Decimal:

        if not returns:
            return ZERO

        wealth = ONE
        peak = ONE
        max_drawdown = ZERO

        for value in returns:
            wealth *= ONE + value

            if wealth > peak:
                peak = wealth

            drawdown = (
                wealth / peak
            ) - ONE

            if drawdown < max_drawdown:
                max_drawdown = drawdown

        return max_drawdown

    def calmar_ratio(
        self,
        returns: list[Decimal],
        *,
        annualization_factor: int = 252,
    ) -> Decimal:

        if not returns:
            return ZERO

        annualized_return = (
            self._annualized_return(
                returns,
                annualization_factor,
            )
        )

        max_drawdown = self.maximum_drawdown(
            returns
        )

        if max_drawdown == ZERO:
            return ZERO

        return (
            annualized_return
            / abs(max_drawdown)
        )

    def information_ratio(
        self,
        portfolio_returns: list[Decimal],
        benchmark_returns: list[Decimal],
        *,
        annualization_factor: int = 252,
    ) -> Decimal:

        if (
            len(portfolio_returns)
            != len(benchmark_returns)
        ):
            raise ValueError(
                "Portfolio and benchmark returns "
                "must have the same length"
            )

        if len(portfolio_returns) < 2:
            return ZERO

        active_returns = [
            portfolio_returns[index]
            - benchmark_returns[index]
            for index in range(
                len(portfolio_returns)
            )
        ]

        tracking_error = self.volatility(
            active_returns,
            annualization_factor=annualization_factor,
        )

        if tracking_error == ZERO:
            return ZERO

        annualized_active_return = (
            self._annualized_return(
                active_returns,
                annualization_factor,
            )
        )

        return (
            annualized_active_return
            / tracking_error
        )

    def beta(
        self,
        portfolio_returns: list[Decimal],
        benchmark_returns: list[Decimal],
    ) -> Decimal:

        if (
            len(portfolio_returns)
            != len(benchmark_returns)
        ):
            raise ValueError(
                "Portfolio and benchmark returns "
                "must have the same length"
            )

        if len(portfolio_returns) < 2:
            return ZERO

        portfolio = [
            float(value)
            for value in portfolio_returns
        ]

        benchmark = [
            float(value)
            for value in benchmark_returns
        ]

        portfolio_mean = (
            sum(portfolio)
            / len(portfolio)
        )

        benchmark_mean = (
            sum(benchmark)
            / len(benchmark)
        )

        covariance = sum(
            (
                portfolio[index]
                - portfolio_mean
            )
            * (
                benchmark[index]
                - benchmark_mean
            )
            for index in range(len(portfolio))
        ) / (len(portfolio) - 1)

        benchmark_variance = sum(
            (
                value
                - benchmark_mean
            ) ** 2
            for value in benchmark
        ) / (len(benchmark) - 1)

        if benchmark_variance == 0:
            return ZERO

        return Decimal(
            str(
                covariance
                / benchmark_variance
            )
        )

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
