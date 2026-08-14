"""Attribution repository (Commit 34 Part 1.5).

In-memory persistence for ``AttributionResult`` records, keyed by
``(strategy_id, trade_date)``. The interface is intentionally
persistence-agnostic so it can later be backed by PostgreSQL,
TimescaleDB, or another analytical store.
"""

from __future__ import annotations

from datetime import date
from threading import RLock

from .models import AttributionResult


class AttributionRepository:
    """
    Repository abstraction for attribution results.

    Current implementation is an in-memory repository.
    The interface is intentionally persistence-agnostic so it
    can later be backed by PostgreSQL, TimescaleDB, or another
    analytical store.
    """

    def __init__(self) -> None:
        self._records: dict[
            tuple[str, date],
            AttributionResult,
        ] = {}

        self._lock = RLock()

    def save(
        self,
        result: AttributionResult,
    ) -> AttributionResult:
        key = (
            result.strategy_id,
            result.trade_date,
        )

        with self._lock:
            self._records[key] = result

        return result

    def save_batch(
        self,
        results: list[AttributionResult],
    ) -> list[AttributionResult]:
        with self._lock:
            for result in results:
                key = (
                    result.strategy_id,
                    result.trade_date,
                )

                self._records[key] = result

        return results

    def get(
        self,
        strategy_id: str,
        trade_date: date,
    ) -> AttributionResult | None:
        key = (
            strategy_id,
            trade_date,
        )

        with self._lock:
            return self._records.get(key)

    def list(
        self,
        strategy_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[AttributionResult]:

        with self._lock:
            records = [
                result
                for result in self._records.values()
                if result.strategy_id == strategy_id
            ]

        if start_date is not None:
            records = [
                result
                for result in records
                if result.trade_date >= start_date
            ]

        if end_date is not None:
            records = [
                result
                for result in records
                if result.trade_date <= end_date
            ]

        return sorted(
            records,
            key=lambda item: item.trade_date,
        )

    def delete(
        self,
        strategy_id: str,
        trade_date: date,
    ) -> bool:
        key = (
            strategy_id,
            trade_date,
        )

        with self._lock:
            if key not in self._records:
                return False

            del self._records[key]
            return True

    def count(
        self,
        strategy_id: str | None = None,
    ) -> int:
        with self._lock:
            if strategy_id is None:
                return len(self._records)

            return sum(
                1
                for result in self._records.values()
                if result.strategy_id == strategy_id
            )

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
