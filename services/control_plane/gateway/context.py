"""
ControlContext / ControlRequest — what the gateway needs to know about the
trading request it is evaluating (spec sections 7 and 19).

For an order:

    strategy  = alpha_nvidia
    account   = ACC001
    symbol    = NVDA
    venue     = NASDAQ

the gateway can answer: is there a GLOBAL control? an ACCOUNT control? a
STRATEGY control? a SYMBOL control? a VENUE control?

``ControlRequest`` is the unified request envelope that Order Engine, Risk
Engine and Execution Engine will send through the gateway in later parts.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from ..controls.scope import ControlScope


@dataclass(frozen=True)
class ControlContext:

    account_id: str | None = None

    portfolio_id: str | None = None

    strategy_id: str | None = None

    symbol: str | None = None

    venue: str | None = None

    order_id: UUID | None = None

    correlation_id: UUID | None = None

    def target(self, scope: ControlScope) -> str | None:
        """The context value that addresses the given scope, if present."""
        return {
            ControlScope.ACCOUNT: self.account_id,
            ControlScope.PORTFOLIO: self.portfolio_id,
            ControlScope.STRATEGY: self.strategy_id,
            ControlScope.SYMBOL: self.symbol,
            ControlScope.VENUE: self.venue,
        }.get(scope)


@dataclass(frozen=True)
class ControlRequest:

    context: ControlContext

    action: str

    is_new_order: bool = True

    quantity: float | None = None
