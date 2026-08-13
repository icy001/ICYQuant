"""Trading recovery checklist and gate (Commit 27 Part 1.5, spec sections 24-25).

统一 Recovery Checklist（RB-RECOVERY-001 对应项）:

    ☐ Service health
    ☐ Event Bus healthy
    ...
    ☐ Resume trading

恢复的基本规则:

    Required Checks
           │
           ▼
    All Passed?
       │       │
      NO      YES
       │       │
       ▼       ▼
    BLOCK    APPROVE
"""

from __future__ import annotations

from .checklist import Checklist, ChecklistItem

#: spec section 24: 统一 Recovery Checklist（RB-RECOVERY-001）。
RECOVERY_CHECKLIST_ITEMS = (
    ChecklistItem(
        item_id="service_health",
        description="Service health",
    ),
    ChecklistItem(
        item_id="event_bus",
        description="Event Bus healthy",
    ),
    ChecklistItem(
        item_id="ledger",
        description="Ledger healthy",
    ),
    ChecklistItem(
        item_id="position",
        description="Position healthy",
    ),
    ChecklistItem(
        item_id="risk",
        description="Risk healthy",
    ),
    ChecklistItem(
        item_id="oms",
        description="OMS healthy",
    ),
    ChecklistItem(
        item_id="execution",
        description="Execution healthy",
    ),
    ChecklistItem(
        item_id="venue",
        description="Venue connected",
    ),
    ChecklistItem(
        item_id="no_critical_alerts",
        description="No unresolved critical alerts",
    ),
    ChecklistItem(
        item_id="reconciliation",
        description="Reconciliation passed",
    ),
    ChecklistItem(
        item_id="risk_validation",
        description="Risk validation passed",
    ),
    ChecklistItem(
        item_id="open_order_validation",
        description="Open order validation passed",
    ),
    ChecklistItem(
        item_id="position_validation",
        description="Position validation passed",
    ),
    ChecklistItem(
        item_id="recovery_approval",
        description="Recovery approval",
    ),
    ChecklistItem(
        item_id="resume_trading",
        description="Resume trading",
    ),
)


def build_recovery_checklist() -> Checklist:

    return Checklist(RECOVERY_CHECKLIST_ITEMS)


class RecoveryGate:
    """恢复交易之前的确定性闸门。

    任一 required 项未完成 -> 抛出 RuntimeError 阻塞恢复。
    """

    def validate(
        self,
        checklist: Checklist,
    ) -> bool:

        if not checklist.all_required_completed():
            pending = ", ".join(
                item.item_id
                for item in checklist.pending_items
                if item.required
            )
            raise RuntimeError(
                f"recovery checklist incomplete: "
                f"missing required items: {pending}"
            )

        return True
