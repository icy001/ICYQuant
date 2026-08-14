"""Strategy performance attribution models (Commit 34 Part 1.3).

``AttributionInput`` carries the standardized strategy / benchmark returns and
PnL components; ``AttributionResult`` is the queryable attribution output whose
core identity is fixed as:

.. code-block:: text

    Active Return
        = Trading Contribution
        + Financing Contribution
        + Fee Contribution
        + Other Contribution
        + Residual
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class AttributionInput:
    strategy_id: str
    trade_date: date
    strategy_return: Decimal
    benchmark_return: Decimal
    gross_exposure: Decimal = Decimal("0")
    net_exposure: Decimal = Decimal("0")
    trading_pnl: Decimal = Decimal("0")
    financing_pnl: Decimal = Decimal("0")
    fee_pnl: Decimal = Decimal("0")
    other_pnl: Decimal = Decimal("0")


@dataclass(frozen=True)
class AttributionResult:
    strategy_id: str
    trade_date: date

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
