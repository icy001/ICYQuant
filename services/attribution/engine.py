"""Strategy performance attribution engine (Commit 34 Part 1.3).

Decomposition:

.. code-block:: text

    Active Return
    = Trading
    + Financing
    + Fees
    + Other
    + Residual
"""

from __future__ import annotations

from decimal import Decimal

from .models import AttributionInput, AttributionResult


ZERO = Decimal("0")


class AttributionEngine:
    """
    Strategy-level performance attribution engine.

    Decomposition:

        Active Return
        = Trading
        + Financing
        + Fees
        + Other
        + Residual
    """

    def calculate(
        self,
        data: AttributionInput,
    ) -> AttributionResult:
        active_return = (
            data.strategy_return
            - data.benchmark_return
        )

        total_contribution = (
            data.trading_pnl
            + data.financing_pnl
            + data.fee_pnl
            + data.other_pnl
        )

        residual = active_return - total_contribution

        return AttributionResult(
            strategy_id=data.strategy_id,
            trade_date=data.trade_date,
            strategy_return=data.strategy_return,
            benchmark_return=data.benchmark_return,
            active_return=active_return,
            trading_contribution=data.trading_pnl,
            financing_contribution=data.financing_pnl,
            fee_contribution=data.fee_pnl,
            other_contribution=data.other_pnl,
            residual=residual,
            gross_exposure=data.gross_exposure,
            net_exposure=data.net_exposure,
        )

    def calculate_batch(
        self,
        records: list[AttributionInput],
    ) -> list[AttributionResult]:
        return [
            self.calculate(record)
            for record in records
        ]
