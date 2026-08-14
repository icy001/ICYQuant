"""Attribution service (Commit 34 Part 1.5).

A thin application-layer wrapper: normalizes plain inputs (str / int / float)
into ``Decimal``-typed ``AttributionInput``, delegates calculation to the
engine, and exposes persistence + query + period-report capabilities built
on the repository and query layer.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from .engine import AttributionEngine
from .models import AttributionInput, AttributionResult
from .query import AttributionQuery, AttributionQueryService
from .report import (
    AttributionPeriodReport,
    AttributionReportBuilder,
)
from .repository import AttributionRepository


class AttributionService:

    def __init__(
        self,
        engine: AttributionEngine | None = None,
        report_builder: AttributionReportBuilder | None = None,
        repository: AttributionRepository | None = None,
    ) -> None:

        self._engine = (
            engine
            or AttributionEngine()
        )

        self._report_builder = (
            report_builder
            or AttributionReportBuilder()
        )

        self._repository = (
            repository
            or AttributionRepository()
        )

        self._query = AttributionQueryService(
            repository=self._repository,
            report_builder=self._report_builder,
        )

    def attribute(
        self,
        *,
        strategy_id: str,
        trade_date: date,
        strategy_return,
        benchmark_return,
        gross_exposure=0,
        net_exposure=0,
        trading_pnl=0,
        financing_pnl=0,
        fee_pnl=0,
        other_pnl=0,
    ) -> AttributionResult:

        input_data = AttributionInput(
            strategy_id=strategy_id,
            trade_date=trade_date,
            strategy_return=Decimal(str(strategy_return)),
            benchmark_return=Decimal(str(benchmark_return)),
            gross_exposure=Decimal(str(gross_exposure)),
            net_exposure=Decimal(str(net_exposure)),
            trading_pnl=Decimal(str(trading_pnl)),
            financing_pnl=Decimal(str(financing_pnl)),
            fee_pnl=Decimal(str(fee_pnl)),
            other_pnl=Decimal(str(other_pnl)),
        )

        return self._engine.calculate(input_data)

    def record(
        self,
        result: AttributionResult,
    ) -> AttributionResult:

        return self._repository.save(result)

    def record_batch(
        self,
        results: list[AttributionResult],
    ) -> list[AttributionResult]:

        return self._repository.save_batch(results)

    def get_daily(
        self,
        *,
        strategy_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[AttributionResult]:

        query = AttributionQuery(
            strategy_id=strategy_id,
            start_date=start_date,
            end_date=end_date,
        )

        return self._query.get_daily(query)

    def build_period_report(
        self,
        records: list[AttributionResult],
    ) -> AttributionPeriodReport:

        return self._report_builder.build(records)

    def get_period_report(
        self,
        *,
        strategy_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> AttributionPeriodReport:

        query = AttributionQuery(
            strategy_id=strategy_id,
            start_date=start_date,
            end_date=end_date,
        )

        return self._query.get_period_report(query)

    def get_latest(
        self,
        strategy_id: str,
    ) -> AttributionResult | None:

        return self._query.get_latest(strategy_id)
