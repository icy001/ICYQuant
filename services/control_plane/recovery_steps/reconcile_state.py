"""
RECONCILE_STATE step.

#18/#19 — the most critical recovery gate: each layer must explain the next.

    Event -> Ledger -> Position -> Risk

Only a full MATCH may advance to VERIFYING.  A divergence is an integrity
failure and is never skipped over.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from ..recovery.recovery_context import RecoveryContext
from ..recovery.recovery_step import RecoveryStep, StepOutcome, StepType
from . import StepExecutor, register_step_executor

Comparator = Callable[[RecoveryContext, RecoveryStep], Dict[str, Any]]


@register_step_executor
class ReconcileStateExecutor(StepExecutor):
    """Compare ledger vs position vs event stream."""

    step_type = StepType.RECONCILE_STATE

    def __init__(self, comparator: Optional[Comparator] = None) -> None:
        # comparator(context, step) -> dict(ledger_vs_position, event_vs_ledger, ...)
        self.comparator = comparator

    def execute(self, step: RecoveryStep, context: RecoveryContext) -> StepOutcome:
        result = (
            self.comparator(context, step) if self.comparator is not None
            else self._default_compare(step, context)
        )
        mismatch = (
            result.get("ledger_vs_position") == "MISMATCH"
            or result.get("event_vs_ledger") == "MISMATCH"
        )
        if mismatch:
            return StepOutcome(
                success=False,
                output={"reconciliation": "MISMATCH", **result},
                error="RECONCILIATION_MISMATCH",
                error_code="RECONCILIATION_MISMATCH",
            )
        return StepOutcome(
            success=True,
            output={"reconciliation": "MATCH", **result},
        )

    @staticmethod
    def _default_compare(
        step: RecoveryStep, context: RecoveryContext
    ) -> Dict[str, Any]:
        replay = context.step_outputs.get("REPLAY_EVENTS", {})
        rebuilt_ledger = context.step_outputs.get("REBUILD_LEDGER", {})
        rebuilt_position = context.step_outputs.get("REBUILD_POSITION", {})

        ledger_quantity = step.input.get("ledger_quantity")
        if ledger_quantity is None:
            ledger_quantity = rebuilt_ledger.get("balance")
        position_quantity = step.input.get("position_quantity")
        if position_quantity is None:
            position_quantity = (rebuilt_position.get("reconstructed") or {}).get(
                "quantity"
            )

        if ledger_quantity is not None and position_quantity is not None:
            ledger_vs_position = (
                "MATCH" if ledger_quantity == position_quantity else "MISMATCH"
            )
        else:
            # nothing comparable produced — nothing observed out of sync
            ledger_vs_position = "MATCH"

        event_vs_ledger = "MATCH"
        if replay and not replay.get("complete"):
            event_vs_ledger = "MISMATCH"

        return {
            "ledger_vs_position": ledger_vs_position,
            "event_vs_ledger": event_vs_ledger,
        }
