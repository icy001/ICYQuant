"""Attribution query layer (Commit 34 Part 1.5).

Introduces an ``AttributionQuery`` object and an
``AttributionQueryService`` so business layers never touch the
repository directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .models import AttributionResult
from .report import AttributionPeriodReport, AttributionReportBuilder
from .repository import AttributionRepository


@dataclass(frozen=True)
class AttributionQuery:
    strategy_id: str
    start_date: date | None = None
    end_date: date | None = None


class AttributionQueryService:

    def __init__(
        self,
        repository: AttributionRepository,
        report_builder: AttributionReportBuilder | None = None,
    ) -> None:
        self._repository = repository
        self._report_builder = (
            report_builder
            or AttributionReportBuilder()
        )

    def get_daily(
        self,
        query: AttributionQuery,
    ) -> list[AttributionResult]:

        return self._repository.list(
            strategy_id=query.strategy_id,
            start_date=query.start_date,
            end_date=query.end_date,
        )

    def get_period_report(
        self,
        query: AttributionQuery,
    ) -> AttributionPeriodReport:

        records = self.get_daily(query)

        if not records:
            raise ValueError(
                "No attribution records found for query"
            )

        return self._report_builder.build(records)

    def get_latest(
        self,
        strategy_id: str,
    ) -> AttributionResult | None:

        records = self._repository.list(
            strategy_id=strategy_id,
        )

        if not records:
            return None

        return records[-1]
