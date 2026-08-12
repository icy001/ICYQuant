"""
ISOLATE_TRADING step.

#7 — before any rebuild may start, trading must be restricted / halted so the
recovery baseline cannot be mutated by new activity.  If trading is already
halted or degraded the step succeeds immediately.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from ..recovery.recovery_context import RecoveryContext
from ..recovery.recovery_step import RecoveryAction, RecoveryStep, StepOutcome, StepType
from . import StepExecutor, register_step_executor

Isolator = Callable[[RecoveryContext], Dict[str, Any]]


@register_step_executor
class IsolateTradingExecutor(StepExecutor):
    """Isolate trading before any state rebuild."""

    step_type = StepType.ISOLATE_TRADING

    def __init__(self, isolator: Optional[Isolator] = None) -> None:
        self.isolator = isolator

    def execute(self, step: RecoveryStep, context: RecoveryContext) -> StepOutcome:
        trading_state = step.input.get("trading_state") or getattr(
            context.trading_state, "value", "TRADING_READY"
        )
        already_isolated = _is_isolated(str(trading_state))

        detail: Dict[str, Any] = {}
        if self.isolator is not None:
            detail = self.isolator(context) or {}

        isolated = bool(detail.get("isolated", already_isolated))
        actions = []
        if not isolated:
            actions.append(
                RecoveryAction(
                    action="ISOLATE_TRADING",
                    target=str(step.input.get("scope", "")),
                    detail="halt trading before recovery",
                    correlation_id=context.correlation_id,
                )
            )
        return StepOutcome(
            success=True,
            output={
                "isolated": isolated,
                "trading_state": trading_state,
                **detail,
            },
            actions=actions,
        )


def _is_isolated(trading_state: str) -> bool:
    upper = trading_state.upper()
    return "HALTED" in upper or "DISABLED" in upper or "DEGRADED" in upper
