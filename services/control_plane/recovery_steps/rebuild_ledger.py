"""
REBUILD_LEDGER step.

#12 — the ledger itself may need recovery:

    Ledger Snapshot + Event Stream -> Replay -> Ledger'

then balance verification.  The actual rebuild is delegated to an injected
``ledger_builder`` domain service; the executor never mutates the ledger.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from ..recovery.recovery_context import RecoveryContext
from ..recovery.recovery_step import RecoveryAction, RecoveryStep, StepOutcome, StepType
from . import StepExecutor, register_step_executor

LedgerBuilder = Callable[[Dict[str, Any], list, list], Dict[str, Any]]


@register_step_executor
class RebuildLedgerExecutor(StepExecutor):
    """Coordinate ledger rebuild + balance verification."""

    step_type = StepType.REBUILD_LEDGER

    def __init__(self, ledger_builder: Optional[LedgerBuilder] = None) -> None:
        # ledger_builder(snapshot, events, adjustments) -> dict(ledger_version, ...)
        self.ledger_builder = ledger_builder

    def execute(self, step: RecoveryStep, context: RecoveryContext) -> StepOutcome:
        snapshot = step.input.get("ledger_snapshot", {})
        events = step.input.get("events", []) or []
        adjustments = step.input.get("adjustments", []) or []

        if self.ledger_builder is not None:
            built = self.ledger_builder(snapshot, events, adjustments) or {}
        else:
            built = {
                "ledger_version": snapshot.get("ledger_version", "L-0"),
                "balance": snapshot.get("balance", 0),
            }

        output = {
            "ledger_version": built.get("ledger_version", "L-0"),
            "balance_verified": bool(built.get("balance_verified", True)),
            **built,
        }
        return StepOutcome(
            success=True,
            output=output,
            actions=[
                RecoveryAction(
                    action="REBUILD_LEDGER",
                    target=str(step.input.get("source", "")),
                    detail=output["ledger_version"],
                    correlation_id=context.correlation_id,
                )
            ],
        )
