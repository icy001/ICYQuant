"""Risk gate: the boundary between Risk Engine and Order Engine
(Commit 37 Part 1.5).

The Risk Engine never places orders; it only answers *"may this order request
enter the Order Engine?"*:

.. code-block:: text

    ALLOW  -> order forwarded to the Order Engine
    REDUCE -> order forwarded with an adjusted quantity
    REVIEW -> order withheld, routed to manual / approval flow
    REJECT -> order withheld, rejected outright
"""

from __future__ import annotations

from dataclasses import dataclass

from services.risk.application.pre_trade import (
    PreTradeRiskChecker,
    PreTradeRiskContext,
)
from services.risk.domain.decision import RiskDecision


@dataclass(frozen=True)
class RiskGateResult:
    decision: RiskDecision
    order: object | None = None


class RiskGate:
    """
    Boundary between Risk Engine and Order Engine.
    """

    def __init__(
        self,
        checker: PreTradeRiskChecker,
    ) -> None:
        self._checker = checker

    def evaluate(
        self,
        order: object,
        *,
        portfolio: object | None = None,
        market: object | None = None,
        account: object | None = None,
    ) -> RiskGateResult:

        context = PreTradeRiskContext(
            order=order,
            portfolio=portfolio,
            market=market,
            account=account,
        )

        decision = self._checker.check(context)

        if decision.allowed:
            return RiskGateResult(
                decision=decision,
                order=order,
            )

        if decision.reduced:
            return RiskGateResult(
                decision=decision,
                order=order,
            )

        return RiskGateResult(
            decision=decision,
            order=None,
        )
