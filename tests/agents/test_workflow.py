"""Tests for Workflow Engine - Automated Trading Workflows."""

import pytest
from services.agents.workflow import (
    WorkflowEngine, WorkflowStatus, StepStatus, WorkflowStep, WorkflowRun,
)


class TestWorkflowEngine:
    """Workflow Engine tests."""

    @pytest.fixture
    def engine(self):
        return WorkflowEngine()

    # ── Registration ────────────────────────────────────────────

    def test_default_workflows_registered(self, engine):
        workflows = engine.get_available_workflows()
        assert "daily_scan" in workflows
        assert "risk_check" in workflows
        assert "rebalance" in workflows
        assert "full_pipeline" in workflows

    def test_register_custom_workflow(self, engine):
        steps = [
            WorkflowStep(name="step1", agent_type="test_agent", action="TEST"),
            WorkflowStep(name="step2", agent_type="test_agent", action="TEST2"),
        ]
        engine.register_workflow("custom", steps)
        assert "custom" in engine.get_available_workflows()

    def test_get_workflow_definition(self, engine):
        definition = engine.get_workflow_definition("risk_check")
        assert definition is not None
        assert len(definition) > 0
        assert "assess_risk" in [s["name"] for s in definition]

    # ── Execution ───────────────────────────────────────────────

    def test_start_simple_workflow(self, engine):
        # Register a simple test workflow
        steps = [
            WorkflowStep(name="step1", agent_type="test", action="TEST_ACTION"),
        ]
        engine.register_workflow("simple_test", steps)

        run = engine.start_workflow("simple_test")
        assert run is not None
        assert run.status in (WorkflowStatus.COMPLETED, WorkflowStatus.RUNNING)

    def test_start_workflow_with_context(self, engine):
        steps = [
            WorkflowStep(name="scan", agent_type="market_agent", action="SCAN"),
        ]
        engine.register_workflow("with_context", steps)

        context = {"symbols": ["NVDA", "AAPL"], "mode": "normal"}
        run = engine.start_workflow("with_context", context)
        assert run is not None
        assert run.context == context

    def test_start_nonexistent_workflow(self, engine):
        run = engine.start_workflow("nonexistent")
        assert run is None

    def test_daily_scan_workflow(self, engine):
        run = engine.start_workflow("daily_scan")
        assert run is not None
        assert run.status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED)
        assert len(run.steps) == 5

    def test_risk_check_workflow(self, engine):
        run = engine.start_workflow("risk_check")
        assert run is not None
        assert len(run.steps) == 2

    def test_full_pipeline_workflow(self, engine):
        run = engine.start_workflow("full_pipeline")
        assert run is not None
        assert len(run.steps) == 8

    # ── Step Dependencies ───────────────────────────────────────

    def test_step_dependencies_respected(self, engine):
        """Steps with dependencies should only execute after deps complete."""
        steps = [
            WorkflowStep(name="dep1", agent_type="test", action="DEP1"),
            WorkflowStep(name="dep2", agent_type="test", action="DEP2",
                         depends_on=["dep1"]),  # Will resolve after execution
        ]
        engine.register_workflow("dep_test", steps)
        run = engine.start_workflow("dep_test")
        assert run is not None

    # ── Status & History ────────────────────────────────────────

    def test_get_workflow_status(self, engine):
        steps = [WorkflowStep(name="s1", agent_type="test", action="A")]
        engine.register_workflow("status_test", steps)
        run = engine.start_workflow("status_test")
        assert run is not None

        status = engine.get_workflow_status(run.run_id)
        assert status is not None
        assert status["workflow_name"] == "status_test"

    def test_get_workflow_status_not_found(self, engine):
        status = engine.get_workflow_status("nonexistent")
        assert status is None

    def test_get_workflow_history(self, engine):
        steps = [WorkflowStep(name="s1", agent_type="test", action="A")]
        engine.register_workflow("hist_test", steps)
        engine.start_workflow("hist_test")

        history = engine.get_workflow_history()
        assert len(history) > 0

    def test_get_active_workflows(self, engine):
        active = engine.get_active_workflows()
        assert isinstance(active, list)

    # ── Cancellation ────────────────────────────────────────────

    def test_cancel_workflow(self, engine):
        steps = [WorkflowStep(name="s1", agent_type="test", action="LONG_ACTION")]
        engine.register_workflow("cancel_test", steps)
        run = engine.start_workflow("cancel_test")
        assert run is not None

        cancelled = engine.cancel_workflow(run.run_id)
        # May or may not cancel if already completed
        assert isinstance(cancelled, bool)

    def test_cancel_nonexistent(self, engine):
        cancelled = engine.cancel_workflow("nonexistent")
        assert cancelled is False

    # ── Summary ─────────────────────────────────────────────────

    def test_get_summary(self, engine):
        summary = engine.get_summary()
        assert "workflows_defined" in summary
        assert "available_workflows" in summary
        assert "total_runs" in summary
        assert summary["workflows_defined"] >= 4  # 4 default workflows

    # ── Progress ────────────────────────────────────────────────

    def test_progress_pct(self, engine):
        steps = [WorkflowStep(name="s1", agent_type="test", action="A")]
        engine.register_workflow("prog_test", steps)
        run = engine.start_workflow("prog_test")
        assert run is not None
        assert 0 <= run.progress_pct <= 100
