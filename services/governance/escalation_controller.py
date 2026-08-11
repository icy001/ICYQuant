"""
Escalation Controller — manages governance escalation with timeout.

Part 1.5: escalates issues that cannot be automatically resolved, with
timeout-based escalation levels and audit trail.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional


class EscalationLevel:
    """Pre-defined escalation levels."""

    NONE = 0
    RISK_MANAGER = 1
    PORTFOLIO_MANAGER = 2
    INVESTMENT_COMMITTEE = 3
    EMERGENCY_CONTROLLER = 4

    @classmethod
    def label(cls, level: int) -> str:
        labels = {
            0: "None",
            1: "Risk Manager",
            2: "Portfolio Manager",
            3: "Investment Committee",
            4: "Emergency Controller",
        }
        return labels.get(level, f"Level {level}")


class EscalationController:
    """Manages governance escalation with timeout-based level progression.

    If an issue cannot be resolved at one level within the timeout,
    it escalates to the next level automatically.
    """

    def __init__(self):
        self._escalations: Dict[str, Dict[str, Any]] = {}  # escalation_id → details
        self._timeout_seconds: Dict[int, float] = {
            EscalationLevel.RISK_MANAGER: 300.0,      # 5 minutes
            EscalationLevel.PORTFOLIO_MANAGER: 600.0,  # 10 minutes
            EscalationLevel.INVESTMENT_COMMITTEE: 1800.0,  # 30 minutes
        }
        self._escalation_count: int = 0

    def escalate(
        self,
        decision: Any = None,
        reason: str = "",
        level: int = EscalationLevel.RISK_MANAGER,
        correlation_id: str = "",
        trigger_type: str = "",
    ) -> Dict[str, Any]:
        """Escalate a governance issue.

        Args:
            decision: The ControlDecision that triggered escalation
            reason: Escalation reason
            level: Starting escalation level
            correlation_id: Audit correlation ID
            trigger_type: Type of trigger that caused escalation

        Returns:
            Escalation record.
        """
        esc_id = f"ESC-{uuid.uuid4().hex[:12].upper()}"
        now = time.time()

        # Determine timeout based on level
        timeout = self._timeout_seconds.get(level, 300.0)

        record = {
            "escalation_id": esc_id,
            "level": level,
            "level_label": EscalationLevel.label(level),
            "reason": reason,
            "trigger_type": trigger_type,
            "decision_id": decision.decision_id if decision else "",
            "correlation_id": correlation_id or f"CORR-{uuid.uuid4().hex[:8].upper()}",
            "escalated_at": now,
            "timeout_seconds": timeout,
            "expires_at": now + timeout,
            "resolved": False,
            "resolved_at": 0.0,
            "resolution": "",
        }

        self._escalations[esc_id] = record
        self._escalation_count += 1

        return record

    def check_timeouts(self) -> List[Dict[str, Any]]:
        """Check for escalations that have timed out.

        Returns list of escalations that need to be bumped up.
        """
        now = time.time()
        timed_out = []

        for esc_id, record in self._escalations.items():
            if record["resolved"]:
                continue
            if now > record["expires_at"]:
                timed_out.append(record)

        return timed_out

    def auto_escalate(self) -> List[Dict[str, Any]]:
        """Automatically escalate timed-out issues to the next level."""
        timed_out = self.check_timeouts()
        results = []

        for record in timed_out:
            next_level = min(record["level"] + 1, EscalationLevel.EMERGENCY_CONTROLLER)
            new_record = self.escalate(
                decision=None,
                reason=f"AUTO-ESCALATE from {EscalationLevel.label(record['level'])}: timeout after {int(record['timeout_seconds'])}s",
                level=next_level,
                correlation_id=record["correlation_id"],
                trigger_type=record.get("trigger_type", ""),
            )
            # Mark old as resolved
            record["resolved"] = True
            record["resolved_at"] = time.time()
            record["resolution"] = f"Auto-escalated to {EscalationLevel.label(next_level)}"
            results.append(new_record)

        return results

    def resolve(self, escalation_id: str, resolution: str = "") -> Dict[str, Any]:
        """Mark an escalation as resolved."""
        if escalation_id not in self._escalations:
            return {"success": False, "error": f"Escalation {escalation_id} not found."}

        record = self._escalations[escalation_id]
        record["resolved"] = True
        record["resolved_at"] = time.time()
        record["resolution"] = resolution

        return {"success": True, "escalation_id": escalation_id, "resolved_at": record["resolved_at"]}

    def get_pending(self) -> List[Dict[str, Any]]:
        """Get all unresolved escalations."""
        return [r for r in self._escalations.values() if not r["resolved"]]

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "total_escalations": self._escalation_count,
            "pending": len(self.get_pending()),
            "timed_out": len(self.check_timeouts()),
            "levels": {
                str(level): EscalationLevel.label(level)
                for level in range(1, 5)
            },
        }
