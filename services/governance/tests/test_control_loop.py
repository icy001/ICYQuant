"""Test Control Loop — continuous control loop behavior."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import pytest

from services.governance.control_state import GovernanceStateType
from services.governance.control_loop import ControlLoop, LoopPhase, LoopCycle
from services.governance.control_trigger import ControlTrigger, TriggerType, Severity
from services.governance.control_decision import ControlDecision


class TestControlLoop:
    """Test control loop lifecycle."""

    def test_start_and_complete_cycle(self):
        loop = ControlLoop()
        cycle = loop.start_cycle(GovernanceStateType.NORMAL)
        assert loop.running
        assert cycle.state_before == GovernanceStateType.NORMAL

        loop.complete_cycle(GovernanceStateType.NORMAL, success=True)
        assert not loop.running
        assert loop.total_cycles == 1

    def test_record_phases(self):
        loop = ControlLoop()
        loop.start_cycle(GovernanceStateType.NORMAL)

        loop.record_phase(LoopPhase.OBSERVE, {"count": 0})
        loop.record_phase(LoopPhase.DETECT, {"count": 2})
        loop.record_phase(LoopPhase.EVALUATE, {"count": 1})

        cycle = loop.complete_cycle(GovernanceStateType.WATCH)
        assert len(cycle.phases_executed) == 3

    def test_detect_triggers(self):
        loop = ControlLoop()
        loop.start_cycle(GovernanceStateType.NORMAL)

        triggers = [
            ControlTrigger(
                trigger_type=TriggerType.DRAWDOWN_BREACH,
                severity=Severity.HIGH,
                value=0.07,
                threshold=0.06,
            ),
            ControlTrigger(
                trigger_type=TriggerType.VAR_BREACH,
                severity=Severity.MEDIUM,
                value=0.03,
                threshold=0.025,
            ),
        ]
        loop.detect_triggers(triggers)

        cycle = loop.complete_cycle(GovernanceStateType.FROZEN)
        assert len(cycle.triggers_detected) == 2

    def test_record_decisions(self):
        loop = ControlLoop()
        loop.start_cycle(GovernanceStateType.NORMAL)
        d1 = ControlDecision.warn("Test warning.")
        d2 = ControlDecision.freeze("Test freeze.")
        loop.record_decision(d1)
        loop.record_decision(d2)

        cycle = loop.complete_cycle(GovernanceStateType.FROZEN)
        assert len(cycle.decisions_made) == 2

    def test_record_interventions(self):
        loop = ControlLoop()
        loop.start_cycle(GovernanceStateType.NORMAL)
        loop.record_intervention({"action": "FREEZE", "result": "OK"})

        cycle = loop.complete_cycle(GovernanceStateType.FROZEN)
        assert len(cycle.interventions) == 1

    def test_state_change_detected(self):
        loop = ControlLoop()
        loop.start_cycle(GovernanceStateType.NORMAL)
        cycle = loop.complete_cycle(GovernanceStateType.FROZEN)
        assert cycle.state_changed

    def test_cycle_duration(self):
        loop = ControlLoop()
        loop.start_cycle(GovernanceStateType.NORMAL)
        time.sleep(0.01)
        cycle = loop.complete_cycle(GovernanceStateType.NORMAL)
        assert cycle.duration_ms > 0

    def test_loop_phase_next(self):
        assert LoopPhase.OBSERVE.next_phase == LoopPhase.DETECT
        assert LoopPhase.AUDIT.next_phase == LoopPhase.OBSERVE

    def test_multiple_cycles(self):
        loop = ControlLoop()
        for i in range(5):
            loop.start_cycle(GovernanceStateType.NORMAL)
            loop.complete_cycle(GovernanceStateType.NORMAL)

        assert loop.total_cycles == 5
        assert len(loop.get_recent_cycles(3)) == 3

    def test_metrics(self):
        loop = ControlLoop()
        loop.start_cycle(GovernanceStateType.NORMAL)
        loop.detect_triggers([ControlTrigger(
            trigger_type=TriggerType.POLICY_BREACH,
            severity=Severity.LOW,
        )])
        loop.record_decision(ControlDecision.warn("test"))
        loop.record_intervention({"action": "WARN"})
        loop.complete_cycle(GovernanceStateType.WATCH)

        metrics = loop.get_metrics()
        assert metrics["total_cycles"] == 1
        assert metrics["total_triggers"] == 1
        assert metrics["total_decisions"] == 1
        assert metrics["total_interventions"] == 1
