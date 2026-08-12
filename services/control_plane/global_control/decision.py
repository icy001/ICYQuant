"""Global control decisions (Commit 26 Part 1.5, spec section 4)."""

from dataclasses import dataclass

from .state import GlobalControlState


@dataclass(frozen=True)
class GlobalControlDecision:

    """Outcome of evaluating the global control state.

    allow_new_risk        新增风险（新仓位 / 新信号）。
    allow_new_orders      新增订单。
    allow_cancel_orders   撤单。
    allow_reduce_orders   减仓。
    allow_emergency_flatten 紧急平仓。
    allow_recovery        是否允许进入/推进恢复流程。
    """

    state: GlobalControlState

    allow_new_risk: bool

    allow_new_orders: bool

    allow_cancel_orders: bool

    allow_reduce_orders: bool

    allow_emergency_flatten: bool

    allow_recovery: bool

    reason: str
