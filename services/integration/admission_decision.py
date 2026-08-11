"""AdmissionDecision — internal decision object produced during admission.

Represents the final go/no-go decision after all admission checks complete,
before the result is converted to an external AdmissionResult.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class AdmissionDecisionType(Enum):
    """Internal admission decision type."""
    ADMIT = auto()
    REJECT = auto()
    BLOCK = auto()
    EXPIRE = auto()
    DUPLICATE = auto()

    @property
    def label(self) -> str:
        _labels = {
            AdmissionDecisionType.ADMIT: "ADMIT",
            AdmissionDecisionType.REJECT: "REJECT",
            AdmissionDecisionType.BLOCK: "BLOCK",
            AdmissionDecisionType.EXPIRE: "EXPIRE",
            AdmissionDecisionType.DUPLICATE: "DUPLICATE",
        }
        return _labels.get(self, "UNKNOWN")


@dataclass
class AdmissionCheckResult:
    """Result of a single admission check."""
    name: str = ""
    passed: bool = False
    code: str = ""
    message: str = ""
    evidence: Optional[Dict[str, Any]] = None


@dataclass
class AdmissionDecision:
    """Aggregated admission decision after all checks.

    Produced internally by the admission boundary before converting to
    an external AdmissionResult.
    """

    decision: AdmissionDecisionType = AdmissionDecisionType.BLOCK
    reason_code: str = ""
    reason_message: str = ""

    flow_id: str = ""
    intent_id: str = ""

    # Detailed check results for auditability
    checks: List[AdmissionCheckResult] = field(default_factory=list)

    @classmethod
    def admit(cls, flow_id: str = "", intent_id: str = "") -> "AdmissionDecision":
        return cls(
            decision=AdmissionDecisionType.ADMIT,
            reason_code="ALL_CHECKS_PASSED",
            reason_message="All admission checks passed",
            flow_id=flow_id,
            intent_id=intent_id,
        )

    @classmethod
    def reject(cls, code: str, message: str, flow_id: str = "",
               intent_id: str = "") -> "AdmissionDecision":
        return cls(
            decision=AdmissionDecisionType.REJECT,
            reason_code=code,
            reason_message=message,
            flow_id=flow_id,
            intent_id=intent_id,
        )

    @classmethod
    def block(cls, code: str, message: str, flow_id: str = "",
              intent_id: str = "") -> "AdmissionDecision":
        return cls(
            decision=AdmissionDecisionType.BLOCK,
            reason_code=code,
            reason_message=message,
            flow_id=flow_id,
            intent_id=intent_id,
        )

    def add_check(self, name: str, passed: bool, code: str = "",
                  message: str = "", evidence: Optional[Dict[str, Any]] = None) -> "AdmissionDecision":
        self.checks.append(
            AdmissionCheckResult(
                name=name, passed=passed, code=code, message=message, evidence=evidence,
            )
        )
        return self

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks) if self.checks else False

    @property
    def is_admit(self) -> bool:
        return self.decision == AdmissionDecisionType.ADMIT

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.name,
            "reason_code": self.reason_code,
            "reason_message": self.reason_message,
            "flow_id": self.flow_id,
            "intent_id": self.intent_id,
            "checks": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "code": c.code,
                    "message": c.message,
                    "evidence": c.evidence,
                }
                for c in self.checks
            ],
        }

    def __repr__(self) -> str:
        return (
            f"AdmissionDecision({self.decision.label}, code={self.reason_code}, "
            f"checks_passed={sum(1 for c in self.checks if c.passed)}/{len(self.checks)})"
        )
