"""
RecoveryStrategy — decides *how* a recovery proceeds.

Different incident classes need different step sequences:

    position  -> isolate, freeze, replay events, rebuild ledger, rebuild
                 position, reconcile, verify, ramp up
    ledger    -> isolate, freeze, replay events, rebuild ledger, reconcile,
                 verify, ramp up
    events    -> isolate, freeze, replay events, reconcile, verify, ramp up
    global    -> full pipeline

A strategy only builds the plan; it never executes anything.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Optional

from .recovery_context import RecoveryContext, RecoveryScope
from .recovery_plan import RecoveryPlan
from .recovery_step import StepType, make_step


def _base_steps(context: RecoveryContext, extra: Dict[str, object]) -> list:
    """Common leading steps shared by every recovery plan."""
    return [
        make_step(
            StepType.ISOLATE_TRADING,
            trading_state=context.trading_state.value,
            scope=context.scope.value,
        ),
        make_step(
            StepType.FREEZE_STATE,
            recovery_id=context.recovery_id,
            **extra,
        ),
    ]


class RecoveryStrategy(ABC):
    """Base class for recovery plan builders."""

    strategy_id: str = "base"

    @abstractmethod
    def build_plan(self, context: RecoveryContext) -> RecoveryPlan:
        """Build the step sequence for the given context."""


class PositionRecoveryStrategy(RecoveryStrategy):
    """Rebuild a corrupted position from ledger + event history."""

    strategy_id = "position"

    def build_plan(self, context: RecoveryContext) -> RecoveryPlan:
        plan = RecoveryPlan(context.recovery_id)
        plan.with_steps(*_base_steps(context, {"target": "POSITION"}))
        plan.add_step(
            make_step(
                StepType.REPLAY_EVENTS,
                event_cursor=context_to_cursor(context),
            )
        )
        plan.add_step(make_step(StepType.REBUILD_LEDGER, source="SNAPSHOT"))
        plan.add_step(make_step(StepType.REBUILD_POSITION, source="LEDGER"))
        plan.add_step(make_step(StepType.RECONCILE_STATE))
        plan.add_step(make_step(StepType.VERIFY_INTEGRITY))
        plan.add_step(
            make_step(
                StepType.RESUME_TRADING,
                ramp_up_level="LEVEL_1",
            )
        )
        return plan


class LedgerRecoveryStrategy(RecoveryStrategy):
    """Rebuild a corrupted ledger from snapshot + event stream."""

    strategy_id = "ledger"

    def build_plan(self, context: RecoveryContext) -> RecoveryPlan:
        plan = RecoveryPlan(context.recovery_id)
        plan.with_steps(*_base_steps(context, {"target": "LEDGER"}))
        plan.add_step(
            make_step(StepType.REPLAY_EVENTS, event_cursor=context_to_cursor(context))
        )
        plan.add_step(make_step(StepType.REBUILD_LEDGER, source="SNAPSHOT"))
        plan.add_step(make_step(StepType.RECONCILE_STATE))
        plan.add_step(make_step(StepType.VERIFY_INTEGRITY))
        plan.add_step(
            make_step(StepType.RESUME_TRADING, ramp_up_level="LEVEL_1")
        )
        return plan


class EventRecoveryStrategy(RecoveryStrategy):
    """Re-validate the event stream (replay + reconciliation only)."""

    strategy_id = "events"

    def build_plan(self, context: RecoveryContext) -> RecoveryPlan:
        plan = RecoveryPlan(context.recovery_id)
        plan.with_steps(*_base_steps(context, {"target": "EVENTS"}))
        plan.add_step(
            make_step(StepType.REPLAY_EVENTS, event_cursor=context_to_cursor(context))
        )
        plan.add_step(make_step(StepType.RECONCILE_STATE))
        plan.add_step(make_step(StepType.VERIFY_INTEGRITY))
        plan.add_step(make_step(StepType.RESUME_TRADING, ramp_up_level="LEVEL_1"))
        return plan


class GlobalRecoveryStrategy(RecoveryStrategy):
    """Full pipeline for global integrity failures."""

    strategy_id = "global"

    def build_plan(self, context: RecoveryContext) -> RecoveryPlan:
        plan = RecoveryPlan(context.recovery_id)
        plan.with_steps(*_base_steps(context, {"target": "GLOBAL"}))
        plan.add_step(
            make_step(StepType.REPLAY_EVENTS, event_cursor=context_to_cursor(context))
        )
        plan.add_step(make_step(StepType.REBUILD_LEDGER, source="SNAPSHOT"))
        plan.add_step(make_step(StepType.REBUILD_POSITION, source="LEDGER"))
        plan.add_step(make_step(StepType.RECONCILE_STATE))
        plan.add_step(make_step(StepType.VERIFY_INTEGRITY))
        plan.add_step(make_step(StepType.RESUME_TRADING, ramp_up_level="LEVEL_1"))
        return plan


#: Registry of every built-in strategy.
STRATEGIES: Dict[str, RecoveryStrategy] = {
    s.strategy_id: s
    for s in (
        PositionRecoveryStrategy(),
        LedgerRecoveryStrategy(),
        EventRecoveryStrategy(),
        GlobalRecoveryStrategy(),
    )
}


def get_strategy(strategy_id: str) -> RecoveryStrategy:
    if strategy_id not in STRATEGIES:
        raise KeyError(f"Unknown recovery strategy: {strategy_id!r}")
    return STRATEGIES[strategy_id]


def strategy_for_trigger(trigger: str, scope: RecoveryScope) -> RecoveryStrategy:
    """Pick a strategy from the incident trigger / scope."""
    key = (trigger or "").lower()
    if "global" in key or scope is RecoveryScope.GLOBAL:
        return STRATEGIES["global"]
    if "ledger" in key:
        return STRATEGIES["ledger"]
    if "event" in key or "replay" in key:
        return STRATEGIES["events"]
    return STRATEGIES["position"]


def context_to_cursor(context: RecoveryContext) -> int:
    """Extract the event replay cursor from the context (defaults to 0)."""
    return getattr(context, "event_cursor", 0) or 0


def build_plan(strategy_id: str, context: RecoveryContext) -> RecoveryPlan:
    return get_strategy(strategy_id).build_plan(context)


__all__ = [
    "RecoveryStrategy",
    "PositionRecoveryStrategy",
    "LedgerRecoveryStrategy",
    "EventRecoveryStrategy",
    "GlobalRecoveryStrategy",
    "STRATEGIES",
    "get_strategy",
    "strategy_for_trigger",
    "build_plan",
]
