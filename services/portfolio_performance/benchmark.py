"""Benchmark performance analytics (Commit 35 Part 1.3).

Provides the benchmark comparison layer:

.. code-block:: text

    Active Return = Portfolio Return - Benchmark Return

``BenchmarkObservation`` carries the daily benchmark return; the calculator
compounds those observations and computes portfolio-relative performance.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


ZERO = Decimal("0")
ONE = Decimal("1")


@dataclass(frozen=True)
class BenchmarkObservation:
    benchmark_id: str
    trade_date: date
    return_pct: Decimal


@dataclass(frozen=True)
class RelativePerformance:
    portfolio_return: Decimal
    benchmark_return: Decimal
    active_return: Decimal

    tracking_difference: Decimal


class BenchmarkPerformanceCalculator:
    """
    Calculate benchmark and portfolio-relative performance.
    """

    def calculate_benchmark_return(
        self,
        observations: list[BenchmarkObservation],
    ) -> Decimal:

        if not observations:
            return ZERO

        ordered = sorted(
            observations,
            key=lambda item: item.trade_date,
        )

        wealth = ONE

        for observation in ordered:
            wealth *= (
                ONE + observation.return_pct
            )

        return wealth - ONE

    def calculate_relative_performance(
        self,
        *,
        portfolio_return: Decimal,
        benchmark_return: Decimal,
    ) -> RelativePerformance:

        active_return = (
            portfolio_return
            - benchmark_return
        )

        tracking_difference = active_return

        return RelativePerformance(
            portfolio_return=portfolio_return,
            benchmark_return=benchmark_return,
            active_return=active_return,
            tracking_difference=tracking_difference,
        )
