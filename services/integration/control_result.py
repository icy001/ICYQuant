"""
Control Result — unified result from any gate or stage in the control flow.

Commit 21 Part 1.1: every gate returns a ControlResult with status, reason,
and correlation data for audit.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional


class GateStatus(Enum):
    """Unified gate result status."""

    PASS = auto()       # Gate passed, proceed to next stage
    REJECT = auto()     # Gate rejected, stop the flow
    BLOCK = auto()      # Gate blocked (fail-closed), stop the flow
    FREEZE = auto()     # Governance freeze, stop the flow
    EXPIRED = auto()    # Gate found expired credential
    ERROR = auto()      # Technical error in gate evaluation

    @property
    def is_pass(self) -> bool:
        return self == GateStatus.PASS

    @property
    def is_terminal(self) -> bool:
        """Gate result that stops the flow."""
        return self in (GateStatus.REJECT, GateStatus.BLOCK, GateStatus.FREEZE,
                        GateStatus.EXPIRED, GateStatus.ERROR)

    @property
    def label(self) -> str:
        labels = {
            GateStatus.PASS: "PASS",
            GateStatus.REJECT: "REJECT",
            GateStatus.BLOCK: "BLOCK",
            GateStatus.FREEZE: "FREEZE",
            GateStatus.EXPIRED: "EXPIRED",
            GateStatus.ERROR: "ERROR",
        }
        return labels.get(self, "UNKNOWN")


@dataclass
class ControlResult:
    """Unified result from a gate, stage, or control check."""

    # ── Core ───────────────────────────────────────────────────
    status: GateStatus = GateStatus.PASS
    code: str = ""              # Machine-readable code, e.g. "RISK_EXPOSURE"
    reason: str = ""            # Human-readable reason

    # ── Correlation ────────────────────────────────────────────
    flow_id: str = ""
    decision_id: str = ""
    transition_id: str = ""

    # ── Version ────────────────────────────────────────────────
    policy_version: str = ""
    risk_version: str = ""

    # ── Metadata ───────────────────────────────────────────────
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ── Factory Methods ────────────────────────────────────────

    @classmethod
    def make_pass(cls, flow_id: str = "", reason: str = "", **kwargs) -> "ControlResult":
        return cls(status=GateStatus.PASS, flow_id=flow_id, reason=reason, **kwargs)

    @classmethod
    def make_reject(cls, flow_id: str = "", code: str = "", reason: str = "", **kwargs) -> "ControlResult":
        return cls(status=GateStatus.REJECT, flow_id=flow_id, code=code, reason=reason, **kwargs)

    @classmethod
    def make_block(cls, flow_id: str = "", code: str = "", reason: str = "", **kwargs) -> "ControlResult":
        return cls(status=GateStatus.BLOCK, flow_id=flow_id, code=code, reason=reason, **kwargs)

    @classmethod
    def make_freeze(cls, flow_id: str = "", code: str = "", reason: str = "", **kwargs) -> "ControlResult":
        return cls(status=GateStatus.FREEZE, flow_id=flow_id, code=code, reason=reason, **kwargs)

    @classmethod
    def make_expired(cls, flow_id: str = "", code: str = "", reason: str = "", **kwargs) -> "ControlResult":
        return cls(status=GateStatus.EXPIRED, flow_id=flow_id, code=code, reason=reason, **kwargs)

    @classmethod
    def make_error(cls, flow_id: str = "", code: str = "", reason: str = "", **kwargs) -> "ControlResult":
        return cls(status=GateStatus.ERROR, flow_id=flow_id, code=code, reason=reason, **kwargs)

    # ── Properties ─────────────────────────────────────────────

    @property
    def passed(self) -> bool:
        return self.status == GateStatus.PASS

    @property
    def is_terminal(self) -> bool:
        return self.status.is_terminal

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.name,
            "code": self.code,
            "reason": self.reason,
            "flow_id": self.flow_id,
            "decision_id": self.decision_id,
            "transition_id": self.transition_id,
            "policy_version": self.policy_version,
            "risk_version": self.risk_version,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }
