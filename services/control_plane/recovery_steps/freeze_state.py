"""
FREEZE_STATE step.

#8/#9 — once isolated, the recovery baseline is frozen: position, ledger and a
recovery snapshot are pinned so the baseline cannot keep moving while rebuilds
run.  A snapshot id is produced so later steps know where recovery starts.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from ..recovery.recovery_context import RecoveryContext
from ..recovery.recovery_step import RecoveryAction, RecoveryStep, StepOutcome, StepType
from . import StepExecutor, register_step_executor

Freezer = Callable[[RecoveryContext], Dict[str, Any]]


@register_step_executor
class FreezeStateExecutor(StepExecutor):
    """Freeze the recovery baseline (position / ledger / snapshot)."""

    step_type = StepType.FREEZE_STATE

    def __init__(self, freezer: Optional[Freezer] = None) -> None:
        self.freezer = freezer

    def execute(self, step: RecoveryStep, context: RecoveryContext) -> StepOutcome:
        detail: Dict[str, Any] = {}
        if self.freezer is not None:
            detail = self.freezer(context) or {}

        snapshot_id = detail.get("snapshot_id") or f"SNAP-{context.recovery_id}"
        output = {"frozen": True, "snapshot_id": snapshot_id, **detail}
        return StepOutcome(
            success=True,
            output=output,
            actions=[
                RecoveryAction(
                    action="FREEZE_STATE",
                    target=str(step.input.get("target", "")),
                    detail=snapshot_id,
                    correlation_id=context.correlation_id,
                )
            ],
        )
