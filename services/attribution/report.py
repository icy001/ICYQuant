"""Cumulative / period attribution reporting (Commit 34 Part 1.4).

Builds period-level attribution reports from daily ``AttributionResult``
records. Daily returns are compounded; contributions are aggregated
arithmetically because they are already expressed in return-space.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .models import AttributionResult


@dataclass(frozen=True)
class AttributionPeriodReport:
    strategy_id: str

    start_date: date
    end_date: date

    observation_count: int

    strategy_return: Decimal
    benchmark_return: Decimal
    active_return: Decimal

    trading_contribution: Decimal
    financing_contribution: Decimal
    fee_contribution: Decimal
    other_contribution: Decimal
    residual: Decimal

    gross_exposure: Decimal
    net_exposure: Decimal

    @property
    def total_contribution(self) -> Decimal:
        return (
            self.trading_contribution
            + self.financing_contribution
            + self.fee_contribution
            + self.other_contribution
        )

    @property
    def attribution_check(self) -> Decimal:
        return (
            self.total_contribution
            + self.residual
            - self.active_return
        )


class AttributionReportBuilder:
    """
    Build period-level attribution reports from daily results.

    Daily returns are compounded rather than summed.

    Contributions are aggregated arithmetically because the
    underlying Part 1.3 contribution values are already expressed
    in return-space.
    """

    def build(
        self,
        records: list[AttributionResult],
    ) -> AttributionPeriodReport:
        if not records:
            raise ValueError(
                "Attribution report requires at least one result"
            )

        ordered = sorted(
            records,
            key=lambda item: item.trade_date,
        )

        strategy_ids = {
            item.strategy_id
            for item in ordered
        }

        if len(strategy_ids) != 1:
            raise ValueError(
                "Attribution report requires a single strategy_id"
            )

        strategy_id = ordered[0].strategy_id

        strategy_return = self._compound_returns(
            [item.strategy_return for item in ordered]
        )

        benchmark_return = self._compound_returns(
            [item.benchmark_return for item in ordered]
        )

        active_return = (
            strategy_return
            - benchmark_return
        )

        trading_contribution = self._sum(
            item.trading_contribution
            for item in ordered
        )

        financing_contribution = self._sum(
            item.financing_contribution
            for item in ordered
        )

        fee_contribution = self._sum(
            item.fee_contribution
            for item in ordered
        )

        other_contribution = self._sum(
            item.other_contribution
            for item in ordered
        )

        residual = (
            active_return
            - trading_contribution
            - financing_contribution
            - fee_contribution
            - other_contribution
        )

        gross_exposure = self._average(
            item.gross_exposure
            for item in ordered
        )

        net_exposure = self._average(
            item.net_exposure
            for item in ordered
        )

        return AttributionPeriodReport(
            strategy_id=strategy_id,
            start_date=ordered[0].trade_date,
            end_date=ordered[-1].trade_date,
            observation_count=len(ordered),
            strategy_return=strategy_return,
            benchmark_return=benchmark_return,
            active_return=active_return,
            trading_contribution=trading_contribution,
            financing_contribution=financing_contribution,
            fee_contribution=fee_contribution,
            other_contribution=other_contribution,
            residual=residual,
            gross_exposure=gross_exposure,
            net_exposure=net_exposure,
        )

    @staticmethod
    def _compound_returns(
        returns,
    ) -> Decimal:
        result = Decimal("1")

        for value in returns:
            result *= Decimal("1") + value

        return result - Decimal("1")

    @staticmethod
    def _sum(values) -> Decimal:
        result = Decimal("0")

        for value in values:
            result += value

        return result

    @staticmethod
    def _average(values) -> Decimal:
        values = list(values)

        if not values:
            return Decimal("0")

        return (
            sum(values, Decimal("0"))
            / Decimal(str(len(values)))
        )
