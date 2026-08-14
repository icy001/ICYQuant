"""Portfolio return analytics (Commit 35 Part 1.2).

Provides the two core return measures:

TWR:
    Measures investment performance independent
    of external cash-flow timing.

MWR:
    Measures investor-level return based on
    actual cash-flow timing.
"""

from __future__ import annotations

from decimal import Decimal


ZERO = Decimal("0")
ONE = Decimal("1")


class PortfolioReturnCalculator:
    """
    Portfolio return analytics.

    TWR:
        Measures investment performance independent
        of external cash-flow timing.

    MWR:
        Measures investor-level return based on
        actual cash-flow timing.
    """

    def calculate_twr(
        self,
        period_returns: list[Decimal],
    ) -> Decimal:

        if not period_returns:
            return ZERO

        wealth = ONE

        for period_return in period_returns:
            wealth *= ONE + period_return

        return wealth - ONE

    def calculate_subperiod_return(
        self,
        *,
        beginning_equity: Decimal,
        ending_equity: Decimal,
        external_cash_flow: Decimal = ZERO,
    ) -> Decimal:

        if beginning_equity <= ZERO:
            raise ValueError(
                "beginning_equity must be greater than zero"
            )

        return (
            ending_equity
            - external_cash_flow
            - beginning_equity
        ) / beginning_equity

    def calculate_mwr(
        self,
        cash_flows: list[Decimal],
        *,
        tolerance: Decimal = Decimal("0.0000000001"),
        max_iterations: int = 100,
    ) -> Decimal:

        if len(cash_flows) < 2:
            raise ValueError(
                "MWR requires at least two cash flows"
            )

        return self._irr(
            cash_flows,
            tolerance=tolerance,
            max_iterations=max_iterations,
        )

    def _irr(
        self,
        cash_flows: list[Decimal],
        *,
        tolerance: Decimal,
        max_iterations: int,
    ) -> Decimal:

        has_positive = any(
            value > ZERO
            for value in cash_flows
        )

        has_negative = any(
            value < ZERO
            for value in cash_flows
        )

        if not has_positive or not has_negative:
            raise ValueError(
                "MWR requires both positive and negative cash flows"
            )

        rate = Decimal("0.10")

        for _ in range(max_iterations):
            npv = ZERO
            derivative = ZERO

            for index, cash_flow in enumerate(
                cash_flows
            ):
                denominator = (
                    ONE + rate
                ) ** index

                npv += (
                    cash_flow
                    / denominator
                )

                if index > 0:
                    derivative -= (
                        Decimal(index)
                        * cash_flow
                        / (
                            ONE + rate
                        ) ** (index + 1)
                    )

            if abs(npv) <= tolerance:
                return rate

            if derivative == ZERO:
                break

            next_rate = (
                rate
                - npv / derivative
            )

            if next_rate <= Decimal("-0.999999"):
                break

            rate = next_rate

        raise ValueError(
            "MWR calculation failed to converge"
        )
