"""Tests for MLOps Pipeline — end-to-end integration."""

import time
import pytest
from services.mlops.trainer import TrainingConfig, ContinuousTrainer, TrainingTrigger
from services.mlops.evaluator import EvaluationConfig, ContinuousEvaluator, GateStatus
from services.mlops.deployment import (
    DeploymentConfig, ContinuousDeployment, DeploymentStrategy, DeploymentStatus,
)
from services.mlops.drift_detector import DriftConfig, DriftDetector, DriftSeverity
from services.mlops.champion_challenger import CCConfig, ChampionChallenger
from services.mlops.rollback import RollbackConfig, RollbackManager
from services.mlops.lifecycle import LifecycleConfig, LifecycleManager, LifecycleStage
from services.mlops.scheduler import SchedulerConfig, MLOpsScheduler, ScheduleStatus
from services.mlops.approval import (
    ApprovalConfig, ApprovalManager, ApprovalStage, ApprovalStatus, ApprovalAction,
)
from services.mlops.service import MLOpsService, MLOpsConfig, PipelineStatus


class TestEvaluator:
    """Tests for ContinuousEvaluator."""

    @pytest.fixture
    def evaluator(self):
        config = EvaluationConfig(
            require_walk_forward=False,
            require_out_of_sample=False,
            pass_score=50.0,
            warn_score=30.0,
        )
        return ContinuousEvaluator(config)

    def test_evaluate_pass(self, evaluator):
        metrics = {
            "sharpe": 2.0, "sortino": 1.8, "max_drawdown": 0.15,
            "ic": 0.06, "rank_ic": 0.05, "turnover": 0.3, "win_rate": 0.55,
        }
        result = evaluator.evaluate("Alpha_v39", "1.0.1", metrics)
        assert result.overall_status == GateStatus.PASS
        assert result.composite_score > 0

    def test_evaluate_fail_low_sharpe(self, evaluator):
        metrics = {
            "sharpe": 0.3, "sortino": 0.2, "max_drawdown": 0.6,
            "ic": 0.01, "rank_ic": 0.005, "turnover": 0.8, "win_rate": 0.45,
        }
        result = evaluator.evaluate("Alpha_v39", "1.0.1", metrics)
        assert result.overall_status == GateStatus.FAIL

    def test_evaluate_warn(self, evaluator):
        evaluator.config.pass_score = 80.0
        evaluator.config.warn_score = 30.0
        metrics = {
            "sharpe": 1.2, "sortino": 0.9, "max_drawdown": 0.2,
            "ic": 0.04, "rank_ic": 0.03, "turnover": 0.4, "win_rate": 0.53,
        }
        result = evaluator.evaluate("Alpha_v39", "1.0.1", metrics)
        # Should be WARN (score between 30-80)
        assert result.overall_status == GateStatus.WARN

    def test_compare(self, evaluator):
        metrics_a = {"sharpe": 2.0, "ic": 0.06}
        metrics_b = {"sharpe": 2.5, "ic": 0.07}
        result_a = evaluator.evaluate("Model_A", "1.0.0", metrics_a)
        result_b = evaluator.evaluate("Model_B", "1.0.0", metrics_b)
        comparison = evaluator.compare(result_a, result_b)
        assert comparison["winner"] == "Model_B"

    def test_set_baseline_and_compare(self, evaluator):
        evaluator.set_baseline("Alpha_v38", {"sharpe": 2.0, "ic": 0.06})
        comp = evaluator.compare_to_baseline(
            "Alpha_v38", {"sharpe": 1.5, "ic": 0.04}
        )
        assert comp["model"] == "Alpha_v38"
        assert comp["comparisons"]["sharpe"]["baseline"] == 2.0
        assert comp["comparisons"]["sharpe"]["current"] == 1.5

    def test_get_history(self, evaluator):
        evaluator.evaluate("Alpha_v38", "1.0.0", {"sharpe": 2.0})
        evaluator.evaluate("Alpha_v39", "1.0.1", {"sharpe": 2.5})
        history = evaluator.get_history("Alpha_v38")
        assert len(history) == 1


class TestDeployment:
    """Tests for ContinuousDeployment."""

    @pytest.fixture
    def deployer(self):
        return ContinuousDeployment(DeploymentConfig(require_approval=False))

    def test_direct_deploy(self, deployer):
        job = deployer.deploy(
            "Alpha_v39", "1.0.1",
            strategy=DeploymentStrategy.DIRECT,
        )
        assert job.model_name == "Alpha_v39"
        # Direct deployment completes immediately
        assert job.status == DeploymentStatus.COMPLETED

    def test_canary_deploy(self, deployer):
        job = deployer.deploy(
            "Alpha_v39", "1.0.1",
            strategy=DeploymentStrategy.CANARY,
        )
        assert job.strategy == DeploymentStrategy.CANARY
        assert job.status == DeploymentStatus.CANARY_PROGRESSING

    def test_advance_canary(self, deployer):
        job = deployer.deploy(
            "Alpha_v39", "1.0.1",
            strategy=DeploymentStrategy.CANARY,
        )
        assert deployer.advance_canary(job.job_id) is True
        updated = deployer.get_job(job.job_id)
        assert updated.current_traffic_pct > 0

    def test_advance_to_completion(self, deployer):
        job = deployer.deploy(
            "Alpha_v39", "1.0.1",
            strategy=DeploymentStrategy.CANARY,
        )
        # Advance through all stages
        for _ in range(10):
            if job.status == DeploymentStatus.COMPLETED:
                break
            deployer.advance_canary(job.job_id)
        assert job.status == DeploymentStatus.COMPLETED

    def test_rollback_deployment(self, deployer):
        job = deployer.deploy(
            "Alpha_v39", "1.0.1",
            strategy=DeploymentStrategy.CANARY,
            previous_version="1.0.0",
        )
        result = deployer.rollback(job.job_id, reason="Test rollback")
        assert result is True
        assert job.status == DeploymentStatus.ROLLED_BACK

    def test_get_active_deployments(self, deployer):
        deployer.deploy("Alpha_v39", "1.0.1", strategy=DeploymentStrategy.CANARY)
        active = deployer.get_active_deployments()
        assert len(active) == 1

    def test_health_check(self, deployer):
        job = deployer.deploy(
            "Alpha_v39", "1.0.1",
            strategy=DeploymentStrategy.CANARY,
        )
        result = deployer.check_health(job.job_id)
        assert result is True
        assert job.health_checks_passed == 1

    def test_approval_required(self):
        deployer = ContinuousDeployment(DeploymentConfig(require_approval=True))
        job = deployer.deploy("Alpha_v39", "1.0.1")
        assert job.status == DeploymentStatus.PENDING

        result = deployer.approve(job.job_id, "admin")
        assert result is True
        assert job.approved_by == "admin"

    def test_list_jobs(self, deployer):
        deployer.deploy("Alpha_v38", "1.0.0", strategy=DeploymentStrategy.DIRECT)
        deployer.deploy("Alpha_v39", "1.0.1", strategy=DeploymentStrategy.CANARY)
        jobs = deployer.list_jobs(model_name="Alpha_v38")
        assert len(jobs) == 1


class TestLifecycle:
    """Tests for LifecycleManager."""

    @pytest.fixture
    def lifecycle(self):
        return LifecycleManager(LifecycleConfig())

    def test_create_and_transition(self, lifecycle):
        lifecycle.create("Alpha_v39", "1.0.1")
        assert lifecycle.get_stage("Alpha_v39") == LifecycleStage.CREATED

        lifecycle.transition("Alpha_v39", LifecycleStage.TRAINING, triggered_by="test")
        assert lifecycle.get_stage("Alpha_v39") == LifecycleStage.TRAINING

    def test_full_lifecycle(self, lifecycle):
        lifecycle.create("Alpha_v39", "1.0.1")

        stages = [
            LifecycleStage.TRAINING,
            LifecycleStage.TRAINED,
            LifecycleStage.VALIDATING,
            LifecycleStage.VALIDATED,
            LifecycleStage.REGISTERED,
            LifecycleStage.STAGING,
            LifecycleStage.CANARY,
            LifecycleStage.PRODUCTION,
        ]
        for stage in stages:
            assert lifecycle.transition("Alpha_v39", stage) is True

        assert lifecycle.get_stage("Alpha_v39") == LifecycleStage.PRODUCTION

    def test_invalid_transition(self, lifecycle):
        lifecycle.create("Alpha_v39", "1.0.1")
        with pytest.raises(ValueError):
            lifecycle.transition("Alpha_v39", LifecycleStage.PRODUCTION)

    def test_audit_trail(self, lifecycle):
        lifecycle.create("Alpha_v39", "1.0.1")
        lifecycle.transition("Alpha_v39", LifecycleStage.TRAINING)
        lifecycle.transition("Alpha_v39", LifecycleStage.TRAINED)

        trail = lifecycle.get_audit_trail("Alpha_v39")
        assert len(trail) == 3

    def test_record_metrics(self, lifecycle):
        lifecycle.create("Alpha_v39", "1.0.1")
        lifecycle.record_metrics(
            "Alpha_v39", {"sharpe": 2.0, "ic": 0.06},
            stage=LifecycleStage.TRAINED,
        )
        record = lifecycle.get_record("Alpha_v39")
        assert record.training_metrics["sharpe"] == 2.0

    def test_get_metric_history(self, lifecycle):
        lifecycle.create("Alpha_v39", "1.0.1")
        lifecycle.record_metrics("Alpha_v39", {"sharpe": 2.0}, stage=LifecycleStage.TRAINED)
        lifecycle.record_metrics("Alpha_v39", {"sharpe": 2.1}, stage=LifecycleStage.TRAINED)

        history = lifecycle.get_metric_history("Alpha_v39")
        assert len(history) == 2

    def test_list_models_by_stage(self, lifecycle):
        lifecycle.create("Model_A", "1.0.0")
        lifecycle.transition("Model_A", LifecycleStage.TRAINING)
        lifecycle.transition("Model_A", LifecycleStage.TRAINED)

        lifecycle.create("Model_B", "1.0.0")
        lifecycle.transition("Model_B", LifecycleStage.TRAINING)

        trained = lifecycle.list_models_by_stage(LifecycleStage.TRAINED)
        assert len(trained) == 1
        assert trained[0].model_name == "Model_A"

    def test_statistics(self, lifecycle):
        lifecycle.create("Model_A", "1.0.0")
        lifecycle.create("Model_B", "1.0.0")
        stats = lifecycle.get_statistics()
        assert stats["total_models"] == 2

    def test_get_production_models(self, lifecycle):
        lifecycle.create("Model_A", "1.0.0")
        lifecycle.transition("Model_A", LifecycleStage.TRAINING)
        lifecycle.transition("Model_A", LifecycleStage.TRAINED)
        lifecycle.transition("Model_A", LifecycleStage.VALIDATING)
        lifecycle.transition("Model_A", LifecycleStage.VALIDATED)
        lifecycle.transition("Model_A", LifecycleStage.REGISTERED)
        lifecycle.transition("Model_A", LifecycleStage.STAGING)
        lifecycle.transition("Model_A", LifecycleStage.CANARY)
        lifecycle.transition("Model_A", LifecycleStage.PRODUCTION)

        prod = lifecycle.get_production_models()
        assert len(prod) == 1


class TestApproval:
    """Tests for ApprovalManager."""

    @pytest.fixture
    def approval(self):
        return ApprovalManager(ApprovalConfig(require_dual_approval=False))

    def test_submit(self, approval):
        req = approval.submit(
            "Alpha_v39", "1.0.1", "researcher",
            evaluation_score=85.0,
        )
        assert req.model_name == "Alpha_v39"
        assert req.overall_status == ApprovalStatus.PENDING

    def test_approve_workflow(self, approval):
        req = approval.submit("Alpha_v39", "1.0.1", "researcher", evaluation_score=85.0)
        # Approve through stages
        approval.approve(req.request_id, "risk_mgr", ApprovalStage.RISK_REVIEW)
        approval.approve(req.request_id, "lead", ApprovalStage.RESEARCH_REVIEW)

        updated = approval.get_request(req.request_id)
        assert updated is not None

    def test_reject(self, approval):
        req = approval.submit("Alpha_v39", "1.0.1", "researcher")
        result = approval.reject(req.request_id, "reviewer", "Not ready")
        assert result is True
        assert req.overall_status == ApprovalStatus.REJECTED

    def test_final_approve(self, approval):
        req = approval.submit("Alpha_v39", "1.0.1", "researcher", evaluation_score=85.0)
        result = approval.final_approve(req.request_id, ["admin"])
        assert result is True
        assert req.overall_status == ApprovalStatus.APPROVED

    def test_dual_approval_required(self):
        approval = ApprovalManager(ApprovalConfig(require_dual_approval=True))
        req = approval.submit("Alpha_v39", "1.0.1", "researcher")
        # Single approver should fail
        result = approval.final_approve(req.request_id, ["admin"])
        assert result is False

        # Two approvers should succeed
        result = approval.final_approve(req.request_id, ["admin", "lead"])
        assert result is True

    def test_list_pending(self, approval):
        approval.submit("Alpha_v39", "1.0.1", "researcher")
        approval.submit("Beta_v2", "1.0.0", "researcher")
        pending = approval.list_requests(status=ApprovalStatus.PENDING)
        assert len(pending) == 2

    def test_cancel_request(self, approval):
        req = approval.submit("Alpha_v39", "1.0.1", "researcher")
        assert approval.cancel_request(req.request_id) is True

    def test_request_changes(self, approval):
        req = approval.submit("Alpha_v39", "1.0.1", "researcher")
        result = approval.request_changes(req.request_id, "reviewer", "Need more tests")
        assert result is True

    def test_auto_approve(self):
        approval = ApprovalManager(ApprovalConfig(
            auto_approve_on_evaluation_pass=True,
            auto_approve_score_threshold=80.0,
        ))
        req = approval.submit(
            "Alpha_v39", "1.0.1", "researcher",
            evaluation_score=90.0,
        )
        assert req.overall_status == ApprovalStatus.APPROVED


class TestScheduler:
    """Tests for MLOpsScheduler."""

    @pytest.fixture
    def scheduler(self):
        return MLOpsScheduler(SchedulerConfig())

    def test_schedule_training(self, scheduler):
        entry = scheduler.schedule_training("Alpha_v38", interval_hours=24)
        assert entry.pipeline_type == "training"
        assert entry.target_model == "Alpha_v38"
        assert entry.next_run_at is not None

    def test_schedule_evaluation(self, scheduler):
        entry = scheduler.schedule_evaluation("Alpha_v38")
        assert entry.pipeline_type == "evaluation"

    def test_schedule_drift_check(self, scheduler):
        entry = scheduler.schedule_drift_check("Alpha_v38")
        assert entry.pipeline_type == "drift_check"

    def test_run_now(self, scheduler):
        entry = scheduler.schedule_training("Alpha_v38")
        result = scheduler.run_now(entry.entry_id)
        assert result is True

    def test_pause_resume(self, scheduler):
        entry = scheduler.schedule_training("Alpha_v38")
        assert scheduler.pause_entry(entry.entry_id) is True
        assert entry.status == ScheduleStatus.PAUSED
        assert scheduler.resume_entry(entry.entry_id) is True
        assert entry.status == ScheduleStatus.ACTIVE

    def test_delete_entry(self, scheduler):
        entry = scheduler.schedule_training("Alpha_v38")
        assert scheduler.delete_entry(entry.entry_id) is True
        assert scheduler.get_entry(entry.entry_id) is None

    def test_list_entries(self, scheduler):
        scheduler.schedule_training("Alpha_v38")
        scheduler.schedule_evaluation("Alpha_v38")
        entries = scheduler.list_entries(pipeline_type="training")
        assert len(entries) == 1

    def test_get_next_runs(self, scheduler):
        scheduler.schedule_training("Alpha_v38", interval_hours=24)
        scheduler.schedule_evaluation("Alpha_v38", interval_hours=12)
        next_runs = scheduler.get_next_runs(limit=2)
        assert len(next_runs) >= 1


class TestMLOpsService:
    """Integration tests for MLOpsService."""

    @pytest.fixture
    def mlops(self):
        return MLOpsService(MLOpsConfig())

    def test_service_creation(self, mlops):
        assert mlops.trainer is not None
        assert mlops.evaluator is not None
        assert mlops.deployer is not None
        assert mlops.drift_detector is not None
        assert mlops.champion_challenger is not None
        assert mlops.rollback_manager is not None
        assert mlops.lifecycle is not None
        assert mlops.scheduler is not None
        assert mlops.approval is not None

    def test_train_delegation(self, mlops):
        job = mlops.train("Alpha_v38")
        assert job.model_name == "Alpha_v38"

    def test_evaluate_delegation(self, mlops):
        # Disable walk-forward/OOS requirements and lower pass score for test
        mlops.evaluator.config.require_walk_forward = False
        mlops.evaluator.config.require_out_of_sample = False
        mlops.evaluator.config.pass_score = 50.0
        metrics = {"sharpe": 2.0, "sortino": 1.8, "max_drawdown": 0.15,
                   "ic": 0.06, "rank_ic": 0.05, "turnover": 0.3, "win_rate": 0.55}
        result = mlops.evaluate("Alpha_v39", "1.0.1", metrics)
        assert result.overall_status == GateStatus.PASS

    def test_health_check(self, mlops):
        health = mlops.health_check()
        assert health["status"] == "healthy"
        assert "components" in health

    def test_setup_default_schedules(self, mlops):
        entries = mlops.setup_default_schedules("Alpha_v38")
        assert len(entries) == 4  # training, evaluation, drift, champion

    def test_reset(self, mlops):
        mlops.train("Alpha_v38")
        mlops.reset()
        health = mlops.health_check()
        assert health["components"]["trainer"]["total_jobs"] == 0
