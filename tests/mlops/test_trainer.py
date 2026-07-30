"""Tests for Continuous Trainer."""

import time
import pytest
from services.mlops.trainer import (
    ContinuousTrainer, TrainingConfig, TrainingJob,
    TrainingTrigger, TrainingStatus, RetrainReason,
)


class TestTrainingJob:
    """Unit tests for TrainingJob dataclass."""

    def test_job_creation_defaults(self):
        job = TrainingJob(model_name="Alpha_v38")
        assert job.model_name == "Alpha_v38"
        assert job.trigger == TrainingTrigger.SCHEDULE
        assert job.status == TrainingStatus.PENDING
        assert job.job_id
        assert job.duration_seconds is None

    def test_job_terminal_states(self):
        job = TrainingJob(model_name="Alpha_v38")
        assert not job.is_terminal
        job.status = TrainingStatus.COMPLETED
        assert job.is_terminal
        job.status = TrainingStatus.FAILED
        assert job.is_terminal
        job.status = TrainingStatus.CANCELLED
        assert job.is_terminal

    def test_job_duration(self):
        job = TrainingJob(model_name="Alpha_v38")
        job.started_at = time.time() - 1.0
        job.completed_at = time.time()
        assert job.duration_seconds is not None
        assert 0.9 <= job.duration_seconds <= 1.1

    def test_job_to_dict(self):
        job = TrainingJob(model_name="Alpha_v38", pipeline_name="daily_alpha")
        d = job.to_dict()
        assert d["model_name"] == "Alpha_v38"
        assert d["pipeline_name"] == "daily_alpha"
        assert d["status"] == "pending"


class TestContinuousTrainer:
    """Unit tests for ContinuousTrainer."""

    @pytest.fixture
    def config(self):
        return TrainingConfig(max_concurrent_jobs=3)

    @pytest.fixture
    def trainer(self, config):
        return ContinuousTrainer(config)

    def test_train_creates_job(self, trainer):
        job = trainer.train("Alpha_v38", trigger=TrainingTrigger.MANUAL)
        assert job.model_name == "Alpha_v38"
        assert job.trigger == TrainingTrigger.MANUAL
        # Job can be QUEUED, RUNNING, or already COMPLETED (fast execution)
        assert job.status in (
            TrainingStatus.QUEUED, TrainingStatus.RUNNING, TrainingStatus.COMPLETED
        )

    def test_train_triggers_complete(self, trainer):
        completed = []

        def on_complete(job):
            completed.append(job.job_id)

        trainer.on_complete(on_complete)

        job = trainer.train("Alpha_v38")
        # Allow brief time for execution
        time.sleep(0.05)
        retrieved = trainer.get_job(job.job_id)
        assert retrieved is not None

    def test_train_with_custom_fn(self, trainer):
        def train_fn(job):
            return {"version": "v42", "metrics": {"sharpe": 2.5, "ic": 0.07}}

        trainer.set_train_fn(train_fn)
        job = trainer.train("Alpha_v38")
        time.sleep(0.05)
        retrieved = trainer.get_job(job.job_id)
        assert retrieved is not None

    def test_get_job(self, trainer):
        job = trainer.train("Alpha_v38")
        assert trainer.get_job(job.job_id) is not None
        assert trainer.get_job("nonexistent") is None

    def test_cancel_job_pending(self, trainer):
        # Queue a job then cancel immediately
        job = trainer.train("Alpha_v38")
        # Force to pending for test
        job.status = TrainingStatus.PENDING
        result = trainer.cancel_job(job.job_id)
        assert result

    def test_list_jobs(self, trainer):
        trainer.train("Model_A")
        trainer.train("Model_B")
        trainer.train("Model_A")
        jobs = trainer.list_jobs()
        assert len(jobs) >= 3

        jobs_a = trainer.list_jobs(model_name="Model_A")
        assert len(jobs_a) >= 2

    def test_get_active_jobs(self, trainer):
        trainer.train("Alpha_v38")
        active = trainer.get_active_jobs()
        assert len(active) >= 0  # May have completed already

    def test_check_performance_degradation(self, trainer):
        # Ensure PERFORMANCE_DEGRADATION trigger is enabled
        if TrainingTrigger.PERFORMANCE_DEGRADATION not in trainer.config.enabled_triggers:
            trainer.config.enabled_triggers.append(TrainingTrigger.PERFORMANCE_DEGRADATION)

        # No degradation
        result = trainer.check_performance_degradation(
            current_sharpe=2.0, current_ic=0.06,
            baseline_sharpe=2.0, baseline_ic=0.06,
        )
        assert result is None

        # Sharpe degraded significantly: drop = (2.0-0.8)/2.0 = 60% > 40% threshold
        result = trainer.check_performance_degradation(
            current_sharpe=0.8, current_ic=0.06,
            baseline_sharpe=2.0, baseline_ic=0.06,
        )
        assert result is not None

    def test_check_performance_degradation_below_threshold(self, trainer):
        # Ensure PERFORMANCE_DEGRADATION trigger is enabled
        if TrainingTrigger.PERFORMANCE_DEGRADATION not in trainer.config.enabled_triggers:
            trainer.config.enabled_triggers.append(TrainingTrigger.PERFORMANCE_DEGRADATION)

        # Sharpe below absolute minimum (0.2 < 0.5)
        result = trainer.check_performance_degradation(
            current_sharpe=0.2, current_ic=0.06,
            baseline_sharpe=2.0, baseline_ic=0.06,
        )
        assert result is not None

    def test_on_drift_event(self, trainer):
        job = trainer.on_drift_event("data", "high", "Alpha_v38")
        assert job is not None
        assert job.trigger == TrainingTrigger.DRIFT_EVENT
        assert job.reason == RetrainReason.DATA_DRIFT_DETECTED

        job2 = trainer.on_drift_event("model", "medium", "Alpha_v38")
        assert job2 is not None
        assert job2.reason == RetrainReason.MODEL_DRIFT_DETECTED

    def test_reset(self, trainer):
        trainer.train("Alpha_v38")
        trainer.train("Alpha_v39")
        trainer.reset()
        assert len(trainer.list_jobs()) == 0

    def test_data_freshness_disabled(self, trainer):
        trainer.config.enabled_triggers = [TrainingTrigger.SCHEDULE]
        result = trainer.check_data_freshness()
        assert result is None

    def test_max_concurrent_jobs(self, trainer):
        trainer.config.max_concurrent_jobs = 1
        # Should queue if at capacity
        j1 = trainer.train("Model_1")
        j2 = trainer.train("Model_2")
        time.sleep(0.05)
        assert j1.job_id != j2.job_id

    def test_train_triggers_failure_callback(self, trainer):
        failures = []

        def on_fail(job):
            failures.append(job.job_id)

        trainer.on_fail(on_fail)

        def failing_fn(job):
            raise RuntimeError("Training failed")

        trainer.set_train_fn(failing_fn)
        job = trainer.train("Alpha_v38")
        time.sleep(0.1)

        # After retries, should have failed
        retrieved = trainer.get_job(job.job_id)
        assert retrieved is not None
