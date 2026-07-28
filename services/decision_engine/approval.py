from datetime import datetime
from typing import Dict, List, Optional

from .decision import Decision


class ApprovalWorkflow:
    """Human-in-the-loop approval workflow for AI-generated decisions.

    State machine: PENDING -> APPROVED / REJECTED -> EXECUTED
    """

    def __init__(self, require_approval: bool = True):
        self.require_approval = require_approval
        self._pending: Dict[str, Decision] = {}
        self._history: List[Decision] = []

    def submit(self, decision: Decision) -> Decision:
        """Submit a decision for approval."""
        decision.status = "PENDING"
        self._pending[decision.decision_id or decision.symbol] = decision
        return decision

    def approve(self, decision: Decision) -> Decision:
        """Approve a pending decision."""
        decision.approve()
        self._record(decision)
        return decision

    def reject(self, decision: Decision, reason: str = "") -> Decision:
        """Reject a pending decision with an optional reason."""
        decision.reject(reason)
        self._record(decision)
        return decision

    def auto_approve(self, decision: Decision, threshold: float = 0.7) -> Decision:
        """Auto-approve if score exceeds threshold, else leave pending."""
        if decision.score >= threshold:
            return self.approve(decision)
        return self.submit(decision)

    def execute(self, decision: Decision) -> Decision:
        """Mark an approved decision as executed."""
        if decision.status != "APPROVED":
            raise ValueError(
                f"Cannot execute decision in status '{decision.status}'. "
                "Must be APPROVED first."
            )
        decision.execute()
        self._record(decision)
        return decision

    def get_pending(self) -> List[Decision]:
        """Get all pending decisions awaiting approval."""
        return [d for d in self._pending.values() if d.status == "PENDING"]

    def get_history(self) -> List[Decision]:
        """Get full approval history."""
        return list(self._history)

    def _record(self, decision: Decision) -> None:
        """Record decision in history."""
        self._history.append(decision)
        key = decision.decision_id or decision.symbol
        self._pending.pop(key, None)

    def summary(self) -> dict:
        approved = sum(1 for d in self._history if d.status == "APPROVED")
        rejected = sum(1 for d in self._history if d.status == "REJECTED")
        executed = sum(1 for d in self._history if d.status == "EXECUTED")
        return {
            "total_decisions": len(self._history),
            "approved": approved,
            "rejected": rejected,
            "executed": executed,
            "pending": len(self.get_pending()),
        }
