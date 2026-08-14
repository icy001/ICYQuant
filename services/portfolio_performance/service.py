"""Portfolio performance service (Commit 35).

A thin application-layer wrapper: normalizes plain inputs (str / int / float)
into ``Decimal``-typed ``PortfolioPerformanceInput`` and delegates to the
calculator, including period TWR / MWR, benchmark-relative analytics,
risk-adjusted performance metrics and rolling window analytics.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from .benchmark import BenchmarkObservation
from .calculator import PortfolioPerformanceCalculator
from .models import (
    PortfolioPerformanceInput,
    PortfolioPerformanceResult,
    PortfolioPeriodPerformance,
    PortfolioBenchmarkPerformance,
    PortfolioRiskMetrics,
)
from .rolling import RollingPerformanceResult


class PortfolioPerformanceService:

    def __init__(
        self,
        calculator: PortfolioPerformanceCalculator | None = None,
    ) -> None:
        self._calculator = (
            calculator
            or PortfolioPerformanceCalculator()
        )

    def calculate(
        self,
        *,
        portfolio_id: str,
        trade_date: date,
        beginning_equity,
        ending_equity,
        external_cash_flow=0,
        trading_pnl=0,
        financing_pnl=0,
        fee_pnl=0,
        other_pnl=0,
    ) -> PortfolioPerformanceResult:

        input_data = PortfolioPerformanceInput(
            portfolio_id=portfolio_id,
            trade_date=trade_date,
            beginning_equity=Decimal(
                str(beginning_equity)
            ),
            ending_equity=Decimal(
                str(ending_equity)
            ),
            external_cash_flow=Decimal(
                str(external_cash_flow)
            ),
            trading_pnl=Decimal(
                str(trading_pnl)
            ),
            financing_pnl=Decimal(
                str(financing_pnl)
            ),
            fee_pnl=Decimal(
                str(fee_pnl)
            ),
            other_pnl=Decimal(
                str(other_pnl)
            ),
        )

        return self._calculator.calculate(
            input_data
        )

    def calculate_period(
        self,
        records: list[PortfolioPerformanceResult],
    ) -> PortfolioPeriodPerformance:

        return self._calculator.calculate_period(
            records
        )

    def calculate_benchmark_relative(
        self,
        *,
        portfolio_id: str,
        benchmark_id: str,
        portfolio_records: list[
            PortfolioPerformanceResult
        ],
        benchmark_observations: list[
            BenchmarkObservation
        ],
    ) -> PortfolioBenchmarkPerformance:

        return self._calculator.calculate_benchmark_relative(
            portfolio_id=portfolio_id,
            benchmark_id=benchmark_id,
            portfolio_records=portfolio_records,
            benchmark_observations=benchmark_observations,
        )

    def calculate_risk_metrics(
        self,
        *,
        portfolio_returns,
        benchmark_returns=None,
        risk_free_rate=0,
        target_return=0,
        annualization_factor=252,
    ) -> PortfolioRiskMetrics:

        return self._calculator.calculate_risk_metrics(
            portfolio_returns=portfolio_returns,
            benchmark_returns=benchmark_returns,
            risk_free_rate=Decimal(
                str(risk_free_rate)
            ),
            target_return=Decimal(
                str(target_return)
            ),
            annualization_factor=annualization_factor,
        )

    def calculate_rolling_performance(
        self,
        *,
        dates: list[date],
        returns,
        window_size: int,
        annualization_factor: int = 252,
        risk_free_rate=0,
        target_return=0,
    ) -> list[RollingPerformanceResult]:

        return self._calculator.calculate_rolling_performance(
            dates=dates,
            returns=returns,
            window_size=window_size,
            annualization_factor=annualization_factor,
            risk_free_rate=risk_free_rate,
            target_return=target_return,
        )
