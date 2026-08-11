"""RepairPolicy — determines which repair actions are allowed."""
from __future__ import annotations

from dataclasses import dataclass

from services.oms.reconciliation.reconciliation_status import ReconciliationStatus
from .repair_action import RepairActionType


@dataclass
class RepairPolicy:
    """Policy for determining repair actions.

    Defines which reconciliation statuses allow automatic repair
    vs require manual escalation.
    """

    auto_repair_enabled: bool = True
    freeze_on_critical: bool = True
    escalate_on_state_mismatch: bool = True

    @classmethod
    def default(cls) -> "RepairPolicy":
        return cls()

    @classmethod
    def conservative(cls) -> "RepairPolicy":
        """No auto-repair — everything escalates."""
        return cls(
            auto_repair_enabled=False,
            freeze_on_critical=True,
            escalate_on_state_mismatch=True,
        )

    @classmethod
    def aggressive(cls) -> "RepairPolicy":
        """Auto-repair everything except critical."""
        return cls(
            auto_repair_enabled=True,
            freeze_on_critical=True,
            escalate_on_state_mismatch=False,
        )

    def determine_action(self,
                         status: ReconciliationStatus,
                         order_id: str = "") -> RepairActionType:
        """Determine the repair action for a reconciliation status."""
        from .repair_action import RepairAction

        if status == ReconciliationStatus.CONSISTENT:
            return RepairActionType.NONE

        if status == ReconciliationStatus.CRITICAL:
            if self.freeze_on_critical:
                return RepairActionType.FREEZE_ORDER
            return RepairActionType.ESCALATE

        if status == ReconciliationStatus.STATE_MISMATCH:
            if self.escalate_on_state_mismatch:
                return RepairActionType.ESCALATE
            return RepairActionType.FREEZE_ORDER

        if status == ReconciliationStatus.QUANTITY_MISMATCH:
            return RepairActionType.ESCALATE

        if status == ReconciliationStatus.OMS_STALE:
            if self.auto_repair_enabled:
                return RepairActionType.REPLAY_EXECUTION
            return RepairActionType.ESCALATE

        if status == ReconciliationStatus.EXECUTION_STALE:
            return RepairActionType.RETRY_QUERY

        if status == ReconciliationStatus.MISSING_EXECUTION:
            if self.auto_repair_enabled:
                return RepairActionType.REPLAY_EXECUTION
            return RepairActionType.ESCALATE

        if status == ReconciliationStatus.DUPLICATE_EXECUTION:
            return RepairActionType.ESCALATE

        return RepairActionType.ESCALATE
