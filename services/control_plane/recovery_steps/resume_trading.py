"""
RESUME_TRADING step.

#32/#33/#34 — after verification, trading is *not* immediately NORMAL.  It
ramps up through levels:

    LEVEL_0 reduce-only -> LEVEL_1 low-risk -> LEVEL_2 selected strategies
        -> LEVEL_3 normal -> LEVEL_4 full

The final go/no-go still belongs to the policy engine (checked by the
orchestrator) — this step only requests the ramp-up.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from ..recovery.recovery_context import RecoveryContext
from ..recovery.recovery_step import RecoveryAction, RecoveryStep, StepOutcome, StepType
from . import StepExecutor, register_step_executor

Gate = Callable[[RecoveryContext, str], Dict[str, Any]]


@register_step_executor
class ResumeTradingExecutor(StepExecutor):
    """Request a gradual trading ramp-up."""

    step_type = StepType.RESUME_TRADING

    def __init__(self, gate: Optional[Gate] = None) -> None:
        # gate(context, level) -> dict(resumed, ...)
        self.gate = gate

    def execute(self, step: RecoveryStep, context: RecoveryContext) -> StepOutcome:
        level = str(step.input.get("ramp_up_level", "LEVEL_1"))
        detail: Dict[str, Any] = {}
        if self.gate is not None:
            detail = self.gate(context, level) or {}
        output = {
            "ramp_up_level": level,
            "resumed": bool(detail.get("resumed", True)),
            **detail,
        }
        return StepOutcome(
            success=True,
            output=output,
            actions=[
                RecoveryAction(
                    action="RESUME_TRADING",
                    target="TRADING",
                    detail=level,
                    correlation_id=context.correlation_id,
                )
            ],
        )
