"""RepairManager — orchestrates repair actions.

Repair is NOT SQL UPDATE. Repair goes through:
    Reconciliation → Repair Decision → Command → Aggregate → Event

The RepairManager decides what action to take and generates the
appropriate commands, but does NOT directly mutate order state.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from services.oms.reconciliation.reconciliation_result import ReconciliationResult
from services.oms.reconciliation.reconciliation_status import ReconciliationStatus
from .repair_action import RepairAction, RepairActionType
from .repair_policy import RepairPolicy


class RepairManager:
    """Manages repair actions for reconciliation mismatches.

    The manager:
      1. Receives a ReconciliationResult
      2. Uses RepairPolicy to determine the action
      3. Returns a RepairAction (which the caller executes via commands)
    """

    def __init__(self, policy: Optional[RepairPolicy] = None) -> None:
        self._policy = policy or RepairPolicy.default()
        self._actions: Dict[str, List[RepairAction]] = {}  # order_id → actions
        self._frozen_orders: set = set()

    def evaluate(self, result: ReconciliationResult) -> RepairAction:
        """Evaluate a reconciliation result and determine repair action."""
        action_type = self._policy.determine_action(
            result.status, result.order_id,
        )

        if action_type == RepairActionType.FREEZE_ORDER:
            action = RepairAction.freeze_order(
                result.order_id,
                reason=f"Critical mismatch: {result.status.label}",
            )
            self._frozen_orders.add(result.order_id)
        elif action_type == RepairActionType.REPLAY_EXECUTION:
            # Find missing execution
            exec_id = ""
            for m in result.mismatches:
                if m.execution_value:
                    exec_id = m.execution_value
                    break
            action = RepairAction.replay_execution(
                result.order_id, exec_id,
            )
        elif action_type == RepairActionType.REBUILD_ORDER:
            action = RepairAction.rebuild_order(result.order_id)
        elif action_type == RepairActionType.ESCALATE:
            action = RepairAction.escalate(
                result.order_id,
                reason=f"Escalated: {result.status.label}",
            )
        elif action_type == RepairActionType.RETRY_QUERY:
            action = RepairAction(
                order_id=result.order_id,
                action_type=RepairActionType.RETRY_QUERY,
                reason="Execution state stale — retry query",
            )
        else:
            action = RepairAction.none(result.order_id)

        # Record the action
        if result.order_id not in self._actions:
            self._actions[result.order_id] = []
        self._actions[result.order_id].append(action)

        return action

    def is_frozen(self, order_id: str) -> bool:
        """Check if an order is frozen."""
        return order_id in self._frozen_orders

    def unfreeze(self, order_id: str) -> None:
        """Unfreeze an order (after manual resolution)."""
        self._frozen_orders.discard(order_id)

    def get_actions(self, order_id: str) -> List[RepairAction]:
        """Get all repair actions for an order."""
        return self._actions.get(order_id, [])

    @property
    def frozen_orders(self) -> set:
        return set(self._frozen_orders)
