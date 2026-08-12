"""
EffectiveControlResolver — merge every control layer into a single effective
verdict (Commit 26 Part 1.5, spec section 23).

所有控制层最终统一：

    Global
    AND
    Portfolio
    AND
    Strategy
    AND
    Execution
    AND
    Venue
    AND
    Risk
    AND
    Admission

对于 New Order：

    effective_new_order =
        global.allow_new_orders
        AND portfolio.allow_new_orders
        AND strategy.allow_new_orders
        AND execution.allow_new_orders
        AND venue.allow_new_orders
        AND risk.allow_new_order
        AND admission.allowed

对于 Reduce：

    effective_reduce =
        global.allow_reduce
        AND portfolio.allow_reduce
        AND strategy.allow_reduce
        AND execution.allow_reduce
        AND venue.allow_reduce

New Risk 路径与 Risk Reduction 路径（Cancel / Reduce / Flatten）必须分开计算：
Kill Switch 不是 "STOP EVERYTHING"，而是
"STOP RISK CREATION, PRESERVE RISK REDUCTION"。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..admission.decision import (
    AdmissionDecision,
    OrderAdmissionDecision,
)
from ..admission.risk import RiskDecision, RiskResult
from ..execution.decision import ExecutionControlDecision
from ..global_control.decision import GlobalControlDecision
from ..portfolio.decision import PortfolioControlDecision
from ..strategy.decision import StrategyControlDecision
from ..venue.decision import VenueControlDecision


@dataclass(frozen=True)
class EffectiveControlDecision:

    allow_new_risk: bool

    allow_new_orders: bool

    allow_reduce_orders: bool

    allow_cancel_orders: bool

    allow_emergency_flatten: bool

    reason: str


class EffectiveControlResolver:

    def resolve(
        self,
        *,
        global_decision: GlobalControlDecision,
        portfolio_decision: PortfolioControlDecision,
        strategy_decision: StrategyControlDecision,
        execution_decision: ExecutionControlDecision,
        venue_decision: VenueControlDecision,
        risk_result: RiskResult | RiskDecision | None = None,
        admission_decision: (
            OrderAdmissionDecision | None
        ) = None,
    ) -> EffectiveControlDecision:

        allow_new_risk = (
            global_decision.allow_new_risk
            and portfolio_decision.allow_new_risk
        )

        allow_new_orders = (
            global_decision.allow_new_orders
            and portfolio_decision.allow_new_orders
            and strategy_decision.allow_new_orders
            and execution_decision.allow_new_orders
            and venue_decision.allow_new_orders
            and self._risk_allows_new_order(
                risk_result,
            )
            and self._admission_allows_new_order(
                admission_decision,
            )
        )

        allow_reduce_orders = (
            global_decision.allow_reduce_orders
            and portfolio_decision.allow_reduce_orders
            and strategy_decision.allow_reduce_orders
            and execution_decision.allow_reduce_orders
            and venue_decision.allow_reduce_orders
        )

        allow_cancel_orders = (
            global_decision.allow_cancel_orders
            and execution_decision.allow_cancel_orders
            and venue_decision.allow_cancel_orders
        )

        allow_emergency_flatten = (
            global_decision.allow_emergency_flatten
            and execution_decision.allow_emergency_flatten
            and venue_decision.allow_emergency_flatten
        )

        return EffectiveControlDecision(
            allow_new_risk=allow_new_risk,
            allow_new_orders=allow_new_orders,
            allow_reduce_orders=allow_reduce_orders,
            allow_cancel_orders=allow_cancel_orders,
            allow_emergency_flatten=(
                allow_emergency_flatten
            ),
            reason=self._build_reason(
                global_decision,
                portfolio_decision,
                strategy_decision,
                execution_decision,
                venue_decision,
            ),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _risk_allows_new_order(
        risk_result: RiskResult | RiskDecision | None,
    ) -> bool:
        if risk_result is None:
            return True
        result = RiskResult.of(risk_result)
        return result.decision is RiskDecision.APPROVED

    @staticmethod
    def _admission_allows_new_order(
        admission_decision: OrderAdmissionDecision | None,
    ) -> bool:
        if admission_decision is None:
            return True
        return (
            admission_decision.decision
            is AdmissionDecision.ACCEPTED
        )

    @staticmethod
    def _build_reason(
        global_decision: GlobalControlDecision,
        portfolio_decision: PortfolioControlDecision,
        strategy_decision: StrategyControlDecision,
        execution_decision: ExecutionControlDecision,
        venue_decision: VenueControlDecision,
    ) -> str:
        return (
            f"global={global_decision.reason};"
            f"portfolio={portfolio_decision.reason};"
            f"strategy={strategy_decision.reason};"
            f"execution={execution_decision.reason};"
            f"venue={venue_decision.reason}"
        )
