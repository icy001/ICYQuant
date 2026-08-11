"""
Intervention Result — structured intervention execution results.

Part 1.5: records the outcome of each intervention plan execution,
including step-level results and verification status.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class InterventionResult:
    """The result of executing an intervention plan."""

    result_id: str = ""
    plan_id: str = ""
    plan_description: str = ""

    # Overall status
    success: bool = False
    state: str = "UNKNOWN"  # SUCCESS / PARTIAL / FAILED / TIMEOUT

    # Steps
    steps_executed: int = 0
    steps_failed: int = 0
    total_steps: int = 0

    # Timing
    started_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    duration_ms: float = 0.0

    # Details
    step_results: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    correlation_id: str = ""

    # Verification
    verified: bool = False
    verification_results: Optional[Dict[str, Any]] = None

    # Audit
    audit_recorded: bool = False

    @property
    def is_partial(self) -> bool:
        return self.state == "PARTIAL"

    @property
    def is_complete(self) -> bool:
        return self.state == "SUCCESS"

    def complete(
        self,
        success: bool,
        step_results: List[Dict[str, Any]],
        verification: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.completed_at = time.time()
        self.duration_ms = (self.completed_at - self.started_at) * 1000
        self.success = success
        self.step_results = step_results
        self.steps_executed = len([s for s in step_results if s.get("executed")])
        self.steps_failed = len([s for s in step_results if s.get("error")])
        self.total_steps = len(step_results)

        if verification:
            self.verified = True
            self.verification_results = verification

        if success:
            self.state = "SUCCESS"
        elif self.steps_executed > 0:
            self.state = "PARTIAL"
        else:
            self.state = "FAILED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "plan_id": self.plan_id,
            "plan_description": self.plan_description,
            "success": self.success,
            "state": self.state,
            "steps_executed": self.steps_executed,
            "steps_failed": self.steps_failed,
            "total_steps": self.total_steps,
            "duration_ms": self.duration_ms,
            "errors": self.errors,
            "verified": self.verified,
            "verification": self.verification_results,
            "audit_recorded": self.audit_recorded,
        }

    # ── Success test ──

    @classmethod
    def success_result(
        cls,
        plan_id: str,
        description: str,
        steps: List[Dict[str, Any]],
        duration_ms: float = 0.0,
    ) -> "InterventionResult":
        result = cls(
            result_id=plan_id,
            plan_id=plan_id,
            plan_description=description,
            state="SUCCESS",
            success=True,
        )
        result.complete(True, steps)
        return result

    @classmethod
    def failure_result(
        cls,
        plan_id: str,
        description: str,
        errors: List[str],
        steps: Optional[List[Dict[str, Any]]] = None,
    ) -> "InterventionResult":
        result = cls(
            result_id=plan_id,
            plan_id=plan_id,
            plan_description=description,
            state="FAILED",
            success=False,
        )
        result.errors = errors
        result.complete(False, steps or [])
        return result
