"""
Control Loop — the continuous Observe → Detect → Evaluate → Decide →
Intervene → Verify → Audit loop of the autonomous governance control plane.

Part 1.5: implements the closed-loop governance cycle.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from .control_state import GovernanceStateType
from .control_action import ControlActionType
from .control_decision import ControlDecision
from .control_trigger import ControlTrigger, Severity


class LoopPhase(Enum):
    """Phases of the control loop."""

    OBSERVE = auto()
    DETECT = auto()
    EVALUATE = auto()
    DECIDE = auto()
    INTERVENE = auto()
    VERIFY = auto()
    AUDIT = auto()

    @property
    def next_phase(self) -> "LoopPhase":
        phases = {
            LoopPhase.OBSERVE: LoopPhase.DETECT,
            LoopPhase.DETECT: LoopPhase.EVALUATE,
            LoopPhase.EVALUATE: LoopPhase.DECIDE,
            LoopPhase.DECIDE: LoopPhase.INTERVENE,
            LoopPhase.INTERVENE: LoopPhase.VERIFY,
            LoopPhase.VERIFY: LoopPhase.AUDIT,
            LoopPhase.AUDIT: LoopPhase.OBSERVE,
        }
        return phases[self]


@dataclass
class LoopCycle:
    """A single iteration of the control loop."""

    cycle_id: str = field(default_factory=lambda: f"LOOP-{uuid.uuid4().hex[:12].upper()}")
    started_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    phases_executed: List[Dict[str, Any]] = field(default_factory=list)
    triggers_detected: List[ControlTrigger] = field(default_factory=list)
    decisions_made: List[ControlDecision] = field(default_factory=list)
    interventions: List[Dict[str, Any]] = field(default_factory=list)
    state_before: GovernanceStateType = GovernanceStateType.NORMAL
    state_after: GovernanceStateType = GovernanceStateType.NORMAL
    correlation_id: str = ""
    success: bool = True

    @property
    def duration_ms(self) -> float:
        if self.completed_at > 0:
            return (self.completed_at - self.started_at) * 1000
        return (time.time() - self.started_at) * 1000

    @property
    def state_changed(self) -> bool:
        return self.state_before != self.state_after

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "triggers_count": len(self.triggers_detected),
            "decisions_count": len(self.decisions_made),
            "interventions_count": len(self.interventions),
            "state_before": self.state_before.name,
            "state_after": self.state_after.name,
            "state_changed": self.state_changed,
            "success": self.success,
        }


class ControlLoop:
    """The continuous autonomous governance control loop.

    Runs the Observe → Detect → Evaluate → Decide → Intervene → Verify → Audit
    cycle, driving the control plane's autonomous behavior.
    """

    def __init__(self):
        self._cycles: List[LoopCycle] = []
        self._max_cycles = 10000
        self._running = False
        self._current_cycle: Optional[LoopCycle] = None

        # Counters
        self._total_cycles: int = 0
        self._total_triggers: int = 0
        self._total_decisions: int = 0
        self._total_interventions: int = 0

    @property
    def running(self) -> bool:
        return self._running

    @property
    def total_cycles(self) -> int:
        return self._total_cycles

    def start_cycle(
        self,
        current_state: GovernanceStateType,
        correlation_id: str = "",
    ) -> LoopCycle:
        """Begin a new loop cycle."""
        cid = correlation_id or f"CORR-{uuid.uuid4().hex[:8].upper()}"
        cycle = LoopCycle(
            state_before=current_state,
            correlation_id=cid,
        )
        self._current_cycle = cycle
        self._running = True
        return cycle

    def record_phase(self, phase: LoopPhase, result: Dict[str, Any]) -> None:
        """Record a phase execution result."""
        if self._current_cycle:
            self._current_cycle.phases_executed.append({
                "phase": phase.name,
                "result": result,
                "timestamp": time.time(),
            })

    def detect_triggers(self, triggers: List[ControlTrigger]) -> None:
        """Record triggers detected in the DETECT phase."""
        if self._current_cycle:
            self._current_cycle.triggers_detected.extend(triggers)
            self._total_triggers += len(triggers)

    def record_decision(self, decision: ControlDecision) -> None:
        """Record a decision made in the DECIDE phase."""
        if self._current_cycle:
            self._current_cycle.decisions_made.append(decision)
            self._total_decisions += 1

    def record_intervention(self, intervention: Dict[str, Any]) -> None:
        """Record an intervention executed in the INTERVENE phase."""
        if self._current_cycle:
            self._current_cycle.interventions.append(intervention)
            self._total_interventions += 1

    def complete_cycle(self, final_state: GovernanceStateType, success: bool = True) -> LoopCycle:
        """Complete the current loop cycle."""
        if self._current_cycle:
            self._current_cycle.completed_at = time.time()
            self._current_cycle.state_after = final_state
            self._current_cycle.success = success

            cycle = self._current_cycle
            self._cycles.append(cycle)
            self._total_cycles += 1

            # Trim history
            if len(self._cycles) > self._max_cycles:
                self._cycles = self._cycles[-self._max_cycles:]

            self._current_cycle = None
            self._running = False
            return cycle

        raise RuntimeError("No active cycle to complete.")

    def get_recent_cycles(self, limit: int = 100) -> List[LoopCycle]:
        return list(reversed(self._cycles[-limit:]))

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "total_cycles": self._total_cycles,
            "total_triggers": self._total_triggers,
            "total_decisions": self._total_decisions,
            "total_interventions": self._total_interventions,
            "running": self._running,
            "current_cycle": self._current_cycle.to_dict() if self._current_cycle else None,
            "recent_cycles": [c.to_dict() for c in self.get_recent_cycles(10)],
        }
