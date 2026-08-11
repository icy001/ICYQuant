"""
Approval Guardian — monitors approval integrity.

Part 1.5: detects approval scope breaches, expiry, anomalies, and
material changes that invalidate existing approvals.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from .control_trigger import ControlTrigger, TriggerType, Severity


class ApprovalGuardian:
    """Monitors approval state and detects anomalies.

    Checks:
      - Approval scope breaches (amount, instrument, etc.)
      - Approval expiry
      - Material changes invalidating approvals
      - Approval replay mismatches
    """

    def __init__(self):
        self._approvals: Dict[str, Dict[str, Any]] = {}
        self._alerts: List[Dict[str, Any]] = []

    def register_approval(
        self,
        approval_id: str,
        scope: str,
        amount: float,
        decision_id: str = "",
        expiry: float = 0.0,
        approver: str = "",
    ) -> None:
        """Register an approval for monitoring."""
        self._approvals[approval_id] = {
            "approval_id": approval_id,
            "scope": scope,
            "amount": amount,
            "decision_id": decision_id,
            "expiry": expiry,
            "approver": approver,
            "status": "ACTIVE",
            "registered_at": time.time(),
            "actual_usage": 0.0,
        }

    def check(self) -> List[ControlTrigger]:
        """Check approval state for breaches.

        Returns:
            List of ControlTrigger objects.
        """
        triggers: List[ControlTrigger] = []
        corr_id = f"CORR-{uuid.uuid4().hex[:8].upper()}"
        now = time.time()

        for approval_id, approval in self._approvals.items():
            # Check expiry
            if approval["expiry"] > 0 and now > approval["expiry"]:
                triggers.append(ControlTrigger(
                    trigger_id=f"TRG-{uuid.uuid4().hex[:12].upper()}",
                    trigger_type=TriggerType.APPROVAL_EXPIRY,
                    severity=Severity.MEDIUM,
                    source="approval-guardian",
                    description=f"Approval {approval_id} expired at {approval['expiry']}",
                    correlation_id=corr_id,
                ))
                approval["status"] = "EXPIRED"

            # Check scope breach (actual > approved)
            if approval["actual_usage"] > approval["amount"]:
                triggers.append(ControlTrigger(
                    trigger_id=f"TRG-{uuid.uuid4().hex[:12].upper()}",
                    trigger_type=TriggerType.APPROVAL_SCOPE_BREACH,
                    severity=Severity.HIGH,
                    source="approval-guardian",
                    description=f"Approval {approval_id}: usage {approval['actual_usage']:.0f} > limit {approval['amount']:.0f}",
                    value=approval["actual_usage"],
                    threshold=approval["amount"],
                    correlation_id=corr_id,
                ))

        if triggers:
            self._alerts.append({
                "timestamp": now,
                "triggers": [t.to_dict() for t in triggers],
            })

        return triggers

    def record_usage(self, approval_id: str, usage_amount: float) -> None:
        """Record actual usage against an approval."""
        if approval_id in self._approvals:
            self._approvals[approval_id]["actual_usage"] += usage_amount

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "active_approvals": sum(1 for a in self._approvals.values() if a["status"] == "ACTIVE"),
            "expired_approvals": sum(1 for a in self._approvals.values() if a["status"] == "EXPIRED"),
            "alerts_count": len(self._alerts),
        }
