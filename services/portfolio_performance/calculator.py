"""Portfolio performance calculator (Commit 35).

Calculates portfolio-level daily performance, stripping external cash flows
from the performance measurement, plus period-level TWR / MWR analytics,
benchmark-relative (active return) comparison, risk-adjusted metrics and
rolling window analytics.

.. code-block:: text

    Net PnL = Ending Equity - Beginning Equity - External Cash Flow
    Return  = Net PnL / Beginning Equity
    Active Return = Portfolio TWR - Benchmark Return
    Risk-adjusted = Is the return worth the risk taken?
    Rolling       = How are metrics behaving on trailing windows?
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from .benchmark import (
    BenchmarkObservation,
    BenchmarkPerformanceCalculator,
)
from .models import (
    PortfolioPerformanceInput,
    PortfolioPerformanceResult,
    PortfolioPeriodPerformance,
    PortfolioBenchmarkPerformance,
    PortfolioRiskMetrics,
)
from .returns import PortfolioReturnCalculator
from .risk_metrics import RiskAdjustedPerformanceCalculator
from .rolling import (
    RollingPerformanceCalculator,
    RollingPerformanceResult,
)


ZERO = Decimal("0")


class PortfolioPerformanceCalculator:

    def __init__(
        self,
        return_calculator: PortfolioReturnCalculator | None = None,
        benchmark_calculator: (
            BenchmarkPerformanceCalculator | None
        ) = None,
        risk_calculator: (
            RiskAdjustedPerformanceCalculator | None
        ) = None,
        rolling_calculator: (
            RollingPerformanceCalculator | None
        ) = None,
    ) -> None:

        self._return_calculator = (
            return_calculator
            or PortfolioReturnCalculator()
        )

        self._benchmark_calculator = (
            benchmark_calculator
            or BenchmarkPerformanceCalculator()
        )

        self._risk_calculator = (
            risk_calculator
            or RiskAdjustedPerformanceCalculator()
        )

        self._rolling_calculator = (
            rolling_calculator
            or RollingPerformanceCalculator()
        )

    def calculate(
        self,
        data: PortfolioPerformanceInput,
    ) -> PortfolioPerformanceResult:

        if data.beginning_equity <= ZERO:
            raise ValueError(
                "beginning_equity must be greater than zero"
            )

        pnl = (
            data.ending_equity
            - data.beginning_equity
            - data.external_cash_flow
        )

        return_pct = (
            pnl / data.beginning_equity
        )

        total_internal_pnl = (
            data.trading_pnl
            + data.financing_pnl
            + data.fee_pnl
            + data.other_pnl
        )

        reconciliation_residual = (
            pnl
            - total_internal_pnl
        )

        return PortfolioPerformanceResult(
            portfolio_id=data.portfolio_id,
            trade_date=data.trade_date,
            beginning_equity=data.beginning_equity,
            ending_equity=data.ending_equity,
            external_cash_flow=data.external_cash_flow,
            pnl=pnl,
            return_pct=return_pct,
            trading_pnl=data.trading_pnl,
            financing_pnl=data.financing_pnl,
            fee_pnl=data.fee_pnl,
            other_pnl=data.other_pnl,
            reconciliation_residual=reconciliation_residual,
        )

    def calculate_period(
        self,
        records: list[PortfolioPerformanceResult],
    ) -> PortfolioPeriodPerformance:

        if not records:
            raise ValueError(
                "Portfolio period requires at least one result"
            )

        ordered = sorted(
            records,
            key=lambda item: item.trade_date,
        )

        portfolio_ids = {
            item.portfolio_id
            for item in ordered
        }

        if len(portfolio_ids) != 1:
            raise ValueError(
                "All records must belong to the same portfolio"
            )

        period_returns = [
            item.return_pct
            for item in ordered
        ]

        twr = (
            self._return_calculator.calculate_twr(
                period_returns
            )
        )

        total_external_cash_flow = sum(
            (
                item.external_cash_flow
                for item in ordered
            ),
            ZERO,
        )

        total_pnl = sum(
            (
                item.pnl
                for item in ordered
            ),
            ZERO,
        )

        trading_pnl = sum(
            (
                item.trading_pnl
                for item in ordered
            ),
            ZERO,
        )

        financing_pnl = sum(
            (
                item.financing_pnl
                for item in ordered
            ),
            ZERO,
        )

        fee_pnl = sum(
            (
                item.fee_pnl
                for item in ordered
            ),
            ZERO,
        )

        other_pnl = sum(
            (
                item.other_pnl
                for item in ordered
            ),
            ZERO,
        )

        reconciliation_residual = (
            total_pnl
            - trading_pnl
            - financing_pnl
            - fee_pnl
            - other_pnl
        )

        cash_flows = [
            -ordered[0].beginning_equity
        ]

        for item in ordered:
            cash_flows.append(
                -item.external_cash_flow
            )

        cash_flows.append(
            ordered[-1].ending_equity
        )

        mwr = (
            self._return_calculator.calculate_mwr(
                cash_flows
            )
        )

        return PortfolioPeriodPerformance(
            portfolio_id=ordered[0].portfolio_id,
            start_date=ordered[0].trade_date,
            end_date=ordered[-1].trade_date,
            observation_count=len(ordered),
            beginning_equity=ordered[0].beginning_equity,
            ending_equity=ordered[-1].ending_equity,
            total_external_cash_flow=total_external_cash_flow,
            total_pnl=total_pnl,
            twr=twr,
            mwr=mwr,
            trading_pnl=trading_pnl,
            financing_pnl=financing_pnl,
            fee_pnl=fee_pnl,
            other_pnl=other_pnl,
            reconciliation_residual=reconciliation_residual,
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

        if not portfolio_records:
            raise ValueError(
                "Portfolio records cannot be empty"
            )

        if not benchmark_observations:
            raise ValueError(
                "Benchmark observations cannot be empty"
            )

        portfolio_period = self.calculate_period(
            portfolio_records
        )

        benchmark_return = (
            self._benchmark_calculator
            .calculate_benchmark_return(
                benchmark_observations
            )
        )

        active_return = (
            portfolio_period.twr
            - benchmark_return
        )

        return PortfolioBenchmarkPerformance(
            portfolio_id=portfolio_id,
            benchmark_id=benchmark_id,
            start_date=portfolio_period.start_date,
            end_date=portfolio_period.end_date,
            portfolio_return=portfolio_period.twr,
            benchmark_return=benchmark_return,
            active_return=active_return,
            tracking_difference=active_return,
        )

    def calculate_risk_metrics(
        self,
        *,
        portfolio_returns: list[Decimal],
        benchmark_returns: list[Decimal] | None = None,
        risk_free_rate: Decimal = ZERO,
        target_return: Decimal = ZERO,
        annualization_factor: int = 252,
    ) -> PortfolioRiskMetrics:

        portfolio_returns = [
            Decimal(str(value))
            for value in portfolio_returns
        ]

        benchmark_returns = (
            None
            if benchmark_returns is None
            else [
                Decimal(str(value))
                for value in benchmark_returns
            ]
        )

        volatility = (
            self._risk_calculator.volatility(
                portfolio_returns,
                annualization_factor=annualization_factor,
            )
        )

        downside_deviation = (
            self._risk_calculator.downside_deviation(
                portfolio_returns,
                target_return=target_return,
                annualization_factor=annualization_factor,
            )
        )

        sharpe_ratio = (
            self._risk_calculator.sharpe_ratio(
                portfolio_returns,
                risk_free_rate=risk_free_rate,
                annualization_factor=annualization_factor,
            )
        )

        sortino_ratio = (
            self._risk_calculator.sortino_ratio(
                portfolio_returns,
                target_return=target_return,
                annualization_factor=annualization_factor,
            )
        )

        maximum_drawdown = (
            self._risk_calculator.maximum_drawdown(
                portfolio_returns
            )
        )

        calmar_ratio = (
            self._risk_calculator.calmar_ratio(
                portfolio_returns,
                annualization_factor=annualization_factor,
            )
        )

        if benchmark_returns is not None:
            information_ratio = (
                self._risk_calculator.information_ratio(
                    portfolio_returns,
                    benchmark_returns,
                    annualization_factor=annualization_factor,
                )
            )

            beta = (
                self._risk_calculator.beta(
                    portfolio_returns,
                    benchmark_returns,
                )
            )
        else:
            information_ratio = ZERO
            beta = ZERO

        return PortfolioRiskMetrics(
            volatility=volatility,
            downside_deviation=downside_deviation,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            maximum_drawdown=maximum_drawdown,
            calmar_ratio=calmar_ratio,
            information_ratio=information_ratio,
            beta=beta,
        )

    def calculate_rolling_performance(
        self,
        *,
        dates: list[date],
        returns: list[Decimal],
        window_size: int,
        annualization_factor: int = 252,
        risk_free_rate: Decimal = ZERO,
        target_return: Decimal = ZERO,
    ) -> list[RollingPerformanceResult]:

        return self._rolling_calculator.calculate(
            dates=dates,
            returns=[
                Decimal(str(value))
                for value in returns
            ],
            window_size=window_size,
            annualization_factor=annualization_factor,
            risk_free_rate=Decimal(
                str(risk_free_rate)
            ),
            target_return=Decimal(
                str(target_return)
            ),
        )
