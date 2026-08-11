"""
Tests for approval_step, approval_stage, approval_transition, and approval_route.

Tests the rich step/stage/transition models that complement the existing
ApprovalWorkflow class with detailed step-level tracking.

Covers spec test requirements:
  - Workflow: Sequential, Parallel, Quorum, Conflict, Timeout
"""

import sys, os, unittest, types, importlib.util

# --- Setup virtual package hierarchy ---
_gov_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_services_dir = os.path.dirname(_gov_dir)
_project_root = os.path.dirname(_services_dir)
sys.path.insert(0, _project_root)

_svc = types.ModuleType("services"); _svc.__path__ = [_services_dir]; _svc.__package__ = "services"
sys.modules["services"] = _svc
_gov = types.ModuleType("services.governance"); _gov.__path__ = [_gov_dir]; _gov.__package__ = "services.governance"
sys.modules["services.governance"] = _gov
_s = importlib.util.spec_from_file_location("services.governance.__init__", os.path.join(_gov_dir, "__init__.py"), submodule_search_locations=[_gov_dir])
_m = importlib.util.module_from_spec(_s); _s.loader.exec_module(_m)

from services.governance.approval_step import ApprovalStep, StepType, StepStatus
from services.governance.approval_stage import ApprovalStage, StageType, StageStatus
from services.governance.approval_transition import ApprovalTransition
from services.governance.approval_status import ApprovalStatus
from services.governance.approval_route import ApprovalRouter, RouteResult
from services.governance.approval_threshold import ApprovalThreshold, ThresholdTier


class TestApprovalStep(unittest.TestCase):
    """Individual approval steps."""

    def test_create_step(self):
        step = ApprovalStep(step_id="S1", name="Risk Review", step_type=StepType.APPROVE,
                            required_role="RISK_MANAGER", sequence_order=1)
        self.assertEqual(step.step_id, "S1")
        self.assertEqual(step.status, StepStatus.PENDING)
        self.assertTrue(step.required)

    def test_step_optional(self):
        step = ApprovalStep(step_id="S2", name="Optional Check", required=False)
        self.assertFalse(step.required)
        step.status = StepStatus.SKIPPED
        self.assertTrue(step.can_proceed())  # Optional + SKIPPED → can proceed

    def test_step_quorum(self):
        step = ApprovalStep(step_id="SQ1", name="Committee Vote", step_type=StepType.QUORUM,
                            quorum_minimum=3, quorum_total=5, quorum_mode="MAJORITY")
        self.assertEqual(step.quorum_minimum, 3)
        self.assertEqual(step.quorum_total, 5)

    def test_step_can_proceed(self):
        step = ApprovalStep("S1", "Required Step", required=True)
        self.assertFalse(step.can_proceed())
        step.status = StepStatus.APPROVED
        self.assertTrue(step.can_proceed())
        step.status = StepStatus.REJECTED
        self.assertFalse(step.can_proceed())

    def test_step_timeout(self):
        import time
        step = ApprovalStep("S1", "Timed Step", timeout_seconds=0.1)
        step.status = StepStatus.IN_PROGRESS
        step.started_at = time.time() - 1.0
        self.assertTrue(step.is_expired())


class TestApprovalStage(unittest.TestCase):
    """Approval stages grouping steps."""

    def setUp(self):
        self.step1 = ApprovalStep("S1", "Step 1", sequence_order=1)
        self.step2 = ApprovalStep("S2", "Step 2", sequence_order=2)

    def test_sequential_stage(self):
        stage = ApprovalStage("ST1", "Sequential Stage", StageType.SEQUENTIAL,
                              steps=[self.step1, self.step2])
        self.assertEqual(stage.stage_type, StageType.SEQUENTIAL)
        self.assertEqual(len(stage.steps), 2)

    def test_parallel_stage(self):
        stage = ApprovalStage("ST2", "Parallel Stage", StageType.PARALLEL,
                              steps=[self.step1, self.step2])
        self.assertEqual(stage.stage_type, StageType.PARALLEL)

    def test_stage_all_completed(self):
        stage = ApprovalStage("ST3", "Stage", steps=[self.step1, self.step2])
        self.assertFalse(stage.all_steps_completed())
        self.step1.status = StepStatus.APPROVED
        self.step2.status = StepStatus.APPROVED
        self.assertTrue(stage.all_steps_completed())

    def test_stage_any_rejected(self):
        stage = ApprovalStage("ST4", "Stage", steps=[self.step1, self.step2])
        self.step1.status = StepStatus.REJECTED
        self.assertTrue(stage.any_step_rejected())

    def test_quorum_evaluation(self):
        members = [
            ApprovalStep(f"M{i}", f"Member {i}", step_type=StepType.QUORUM,
                         quorum_minimum=3, quorum_total=5)
            for i in range(5)
        ]
        stage = ApprovalStage("QST", "Quorum Stage", StageType.QUORUM, steps=members)
        self.assertFalse(stage.evaluate_quorum())
        for i in range(3):
            members[i].status = StepStatus.APPROVED
        self.assertTrue(stage.evaluate_quorum())

    def test_any_step_expired(self):
        import time
        step = ApprovalStep("SE", "Expiring", timeout_seconds=0.1)
        step.status = StepStatus.IN_PROGRESS
        step.started_at = time.time() - 1.0
        stage = ApprovalStage("ST", "Stage", steps=[step])
        self.assertTrue(stage.any_step_expired())


class TestApprovalTransition(unittest.TestCase):
    """State transition validation."""

    def test_valid_transition(self):
        self.assertTrue(ApprovalTransition.can_transition(
            ApprovalStatus.DRAFT, ApprovalStatus.SUBMITTED
        ))

    def test_invalid_transition(self):
        self.assertFalse(ApprovalTransition.can_transition(
            ApprovalStatus.EXECUTED, ApprovalStatus.APPROVED
        ))

    def test_terminal(self):
        transition = ApprovalTransition(
            approval_id="A1",
            from_status=ApprovalStatus.EXECUTABLE,
            to_status=ApprovalStatus.EXECUTED,
        )
        self.assertTrue(transition.is_valid())
        self.assertTrue(transition.is_terminal())

    def test_valid_transitions_from(self):
        transitions = ApprovalTransition.valid_transitions_from(ApprovalStatus.DRAFT)
        self.assertIn(ApprovalStatus.SUBMITTED, transitions)
        self.assertIn(ApprovalStatus.CANCELLED, transitions)
        self.assertNotIn(ApprovalStatus.EXECUTED, transitions)


class TestApprovalRouting(unittest.TestCase):
    """ApprovalRouter — routing to approvers."""

    def test_route_no_threshold(self):
        router = ApprovalRouter()
        result = router.route("REQ-001", "UNKNOWN", 10_000_000)
        self.assertFalse(result.approval_required)

    def test_route_with_threshold(self):
        router = ApprovalRouter()
        t = ApprovalThreshold("TH", "Test", "CAP", tiers=[
            ThresholdTier("Review", 20_000_000, ["RISK_MANAGER"]),
        ])
        router.register_threshold(t)
        result = router.route("REQ-001", "CAP", 15_000_000)
        self.assertTrue(result.approval_required)
        self.assertEqual(len(result.targets), 1)
        self.assertEqual(result.targets[0].role, "RISK_MANAGER")

    def test_route_autonomous(self):
        router = ApprovalRouter()
        t = ApprovalThreshold("TH", "Test", "CAP", tiers=[
            ThresholdTier("Auto", 5_000_000, []),
            ThresholdTier("Review", 20_000_000, ["RISK_MANAGER"]),
        ])
        router.register_threshold(t)
        result = router.route("REQ-001", "CAP", 3_000_000)
        self.assertFalse(result.approval_required)
        self.assertEqual(len(result.targets), 0)


if __name__ == "__main__":
    unittest.main()
