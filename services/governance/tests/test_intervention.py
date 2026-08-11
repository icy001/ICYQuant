"""Test Intervention — intervention plan execution."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from services.governance.intervention_plan import (
    InterventionPlan, InterventionStep, InterventionStepType,
)
from services.governance.intervention_result import InterventionResult
from services.governance.governance_intervention import GovernanceIntervention
from services.governance.freeze_controller import FreezeController
from services.governance.exposure_controller import ExposureController
from services.governance.revoke_controller import RevokeController


class TestInterventionPlan:
    """Test intervention plan construction."""

    def test_create_plan(self):
        plan = InterventionPlan(
            trigger="DRAWDOWN_BREACH",
            description="Drawdown at 7%",
            severity="HIGH",
        )
        assert plan.state == "DRAFT"
        assert plan.trigger == "DRAWDOWN_BREACH"

    def test_add_steps(self):
        plan = InterventionPlan(trigger="TEST")
        plan.add_step(InterventionStepType.FREEZE, "Freeze all")
        plan.add_step(InterventionStepType.CANCEL, "Cancel pending")
        plan.add_step(InterventionStepType.REDUCE, "Reduce exposure")
        assert len(plan.steps) == 3

    def test_get_next_step(self):
        plan = InterventionPlan(trigger="TEST")
        s1 = plan.add_step(InterventionStepType.FREEZE, "Step 1")
        s2 = plan.add_step(InterventionStepType.VERIFY, "Step 2")
        next_s = plan.get_next_step()
        assert next_s.order == 0

    def test_factory_drawdown_restrict_plan(self):
        plan = InterventionPlan.drawdown_restrict_plan(0.045)
        assert plan.trigger == "Drawdown 4.5%"
        assert len(plan.steps) >= 3

    def test_factory_drawdown_freeze_plan(self):
        plan = InterventionPlan.drawdown_freeze_plan(0.065)
        assert plan.trigger == "Drawdown 6.5%"
        assert len(plan.steps) >= 4

    def test_factory_emergency_plan(self):
        plan = InterventionPlan.emergency_plan("AUDIT_INTEGRITY_FAILURE")
        assert plan.trigger == "AUDIT_INTEGRITY_FAILURE"
        assert len(plan.steps) >= 4
        assert plan.severity == "CRITICAL"


class TestInterventionExecution:
    """Test intervention plan execution via GovernanceIntervention."""

    def test_execute_plan_with_controllers(self):
        fc = FreezeController()
        ec = ExposureController()
        rc = RevokeController()

        gi = GovernanceIntervention(
            freeze_controller=fc,
            exposure_controller=ec,
            revoke_controller=rc,
        )

        plan = InterventionPlan(trigger="TEST")
        plan.add_step(InterventionStepType.FREEZE, "Freeze new risk")
        plan.add_step(InterventionStepType.VERIFY, "Verify")

        result = gi.execute(plan)
        assert result is not None
        assert result.state in ("SUCCESS", "PARTIAL")

    def test_execute_results_recorded(self):
        fc = FreezeController()
        gi = GovernanceIntervention(freeze_controller=fc)

        plan = InterventionPlan(trigger="TEST")
        plan.add_step(InterventionStepType.FREEZE, "Test freeze")
        gi.execute(plan)

        results = gi.get_results()
        assert len(results) >= 1

    def test_metrics(self):
        gi = GovernanceIntervention()
        plan = InterventionPlan(trigger="TEST")
        plan.add_step(InterventionStepType.NOTIFY, "Test notification")
        gi.execute(plan)

        metrics = gi.get_metrics()
        assert metrics["total_interventions"] >= 1


class TestInterventionResult:
    """Test intervention result."""

    def test_success_result(self):
        result = InterventionResult.success_result(
            "PLAN-001", "Test plan", [{"executed": True}]
        )
        assert result.success
        assert result.state == "SUCCESS"

    def test_failure_result(self):
        result = InterventionResult.failure_result(
            "PLAN-002", "Failed plan", ["Error 1", "Error 2"]
        )
        assert not result.success
        assert result.state == "FAILED"
        assert len(result.errors) == 2
