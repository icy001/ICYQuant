"""
REBUILD_POSITION step.

#11 — a corrupted position is never zeroed; it is reconstructed:

    Ledger + Trade Events + Corporate Actions + Adjustments -> Position'

then compared against the frozen position snapshot.  The rebuild itself is
delegated to an injected ``position_builder`` domain service.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from ..recovery.recovery_context import RecoveryContext
from ..recovery.recovery_step import RecoveryAction, RecoveryStep, StepOutcome, StepType
from . import StepExecutor, register_step_executor

PositionBuilder = Callable[[Dict[str, Any], list, list], Dict[str, Any]]

_COMPARE_KEYS = ("quantity", "average_price", "cash_balance", "margin")


def _positions_match(rebuilt: Dict[str, Any], snapshot: Dict[str, Any]) -> bool:
    """Whether the rebuilt position agrees with the frozen snapshot."""
    if not snapshot:
        return True
    for key in _COMPARE_KEYS:
        if key in snapshot and key in rebuilt:
            if snapshot[key] != rebuilt[key]:
                return False
    return True


@register_step_executor
class RebuildPositionExecutor(StepExecutor):
    """Coordinate position reconstruction + snapshot comparison."""

    step_type = StepType.REBUILD_POSITION

    def __init__(self, position_builder: Optional[PositionBuilder] = None) -> None:
        # position_builder(ledger, events, adjustments) -> dict(position_version, ...)
        self.position_builder = position_builder

    def execute(self, step: RecoveryStep, context: RecoveryContext) -> StepOutcome:
        ledger = step.input.get("ledger", {})
        position_snapshot = step.input.get("position_snapshot", {})
        events = step.input.get("events", []) or []
        adjustments = step.input.get("adjustments", []) or []

        if self.position_builder is not None:
            rebuilt = self.position_builder(ledger, events, adjustments) or {}
        else:
            rebuilt = {
                "position_version": "P-0",
                "quantity": ledger.get("quantity", 0),
            }

        match = _positions_match(rebuilt, position_snapshot)
        output = {
            "position_version": rebuilt.get("position_version", ""),
            "reconstructed": dict(rebuilt),
            "snapshot": dict(position_snapshot),
            "match": match,
        }
        return StepOutcome(
            success=True,
            output=output,
            actions=[
                RecoveryAction(
                    action="REBUILD_POSITION",
                    target=str(step.input.get("source", "")),
                    detail=output["position_version"],
                    correlation_id=context.correlation_id,
                )
            ],
        )
