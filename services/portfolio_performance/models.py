"""Portfolio performance domain models (Commit 35).

``PortfolioPerformanceInput`` carries the equity marks and PnL components for
a single portfolio / day; ``PortfolioPerformanceResult`` is the calculated
output whose core identity is fixed as:

.. code-block:: text

    PnL = Ending Equity - Beginning Equity - External Cash Flow

``PortfolioPeriodPerformance`` aggregates a series of daily results into a
period view carrying both TWR and MWR.

``PortfolioBenchmarkPerformance`` compares the portfolio's TWR against a
benchmark's compounded return over the same period.

``PortfolioRiskMetrics`` carries the risk-adjusted performance metrics
(volatility, downside deviation, Sharpe, Sortino, drawdown, Calmar,
information ratio, beta).

``RollingPerformanceResult`` is the output of the rolling window engine:
one performance / risk snapshot per trailing window as-of date.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class PortfolioPerformanceInput:
    portfolio_id: str
    trade_date: date

    beginning_equity: Decimal
    ending_equity: Decimal

    external_cash_flow: Decimal = Decimal("0")

    trading_pnl: Decimal = Decimal("0")
    financing_pnl: Decimal = Decimal("0")
    fee_pnl: Decimal = Decimal("0")
    other_pnl: Decimal = Decimal("0")


@dataclass(frozen=True)
class PortfolioPerformanceResult:
    portfolio_id: str
    trade_date: date

    beginning_equity: Decimal
    ending_equity: Decimal

    external_cash_flow: Decimal

    pnl: Decimal
    return_pct: Decimal

    trading_pnl: Decimal
    financing_pnl: Decimal
    fee_pnl: Decimal
    other_pnl: Decimal

    reconciliation_residual: Decimal

    @property
    def total_internal_pnl(self) -> Decimal:
        return (
            self.trading_pnl
            + self.financing_pnl
            + self.fee_pnl
            + self.other_pnl
        )


@dataclass(frozen=True)
class PortfolioPeriodPerformance:
    portfolio_id: str

    start_date: date
    end_date: date

    observation_count: int

    beginning_equity: Decimal
    ending_equity: Decimal

    total_external_cash_flow: Decimal
    total_pnl: Decimal

    twr: Decimal
    mwr: Decimal

    trading_pnl: Decimal
    financing_pnl: Decimal
    fee_pnl: Decimal
    other_pnl: Decimal

    reconciliation_residual: Decimal


@dataclass(frozen=True)
class PortfolioBenchmarkPerformance:
    portfolio_id: str
    benchmark_id: str

    start_date: date
    end_date: date

    portfolio_return: Decimal
    benchmark_return: Decimal

    active_return: Decimal

    tracking_difference: Decimal


@dataclass(frozen=True)
class PortfolioRiskMetrics:
    volatility: Decimal
    downside_deviation: Decimal

    sharpe_ratio: Decimal
    sortino_ratio: Decimal

    maximum_drawdown: Decimal
    calmar_ratio: Decimal

    information_ratio: Decimal
    beta: Decimal


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
