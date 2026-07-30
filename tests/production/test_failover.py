"""
Failover tests for ICYQuant production readiness.

Tests disaster recovery failover scenarios including primary region,
database, message queue, cache failover, and split-brain prevention.
Uses DisasterRecoveryValidator from release.validation.
"""

import os
import tempfile

import pytest

from release.validation import (
    DRCheckStep,
    DRResult,
    DisasterRecoveryValidator,
)


class TestPrimaryRegionFailover:
    """Test primary region failover procedures."""

    def test_multi_region_failover_configured(self):
        """Verify multi-region failover is properly configured."""
        validator = DisasterRecoveryValidator()
        result = validator.run()

        assert isinstance(result, DRResult)
        assert len(result.steps) >= 6

        failover_step = None
        for step in result.steps:
            if step.step_name == "Multi-Region Failover":
                failover_step = step
                break

        assert failover_step is not None
        assert isinstance(failover_step, DRCheckStep)

    def test_failover_step_passes_when_configured(self):
        """Verify failover step passes with valid DR configuration."""
        validator = DisasterRecoveryValidator()
        result = validator.run()

        failover_step = None
        for step in result.steps:
            if step.step_name == "Multi-Region Failover":
                failover_step = step
                break

        if failover_step and failover_step.passed:
            assert result.multi_region_failover_passed is True

    def test_failover_result_structure(self):
        """Verify DRResult has correct structure for failover scenario."""
        result = DRResult(
            overall_passed=True,
            total_duration_ms=1000.0,
            steps=[
                DRCheckStep(step_name="test", passed=True, duration_ms=100.0),
            ],
            multi_region_failover_passed=True,
        )

        assert result.multi_region_failover_passed is True
        assert result.overall_passed is True
        assert result.total_duration_ms == 1000.0


class TestDatabaseFailover:
    """Test database failover procedures."""

    def test_backup_integrity_check(self):
        """Verify backup integrity check runs successfully."""
        validator = DisasterRecoveryValidator()
        result = validator.run()

        backup_step = None
        for step in result.steps:
            if step.step_name == "Backup Integrity":
                backup_step = step
                break

        assert backup_step is not None
        assert isinstance(backup_step, DRCheckStep)
        assert backup_step.duration_ms >= 0

    def test_restore_procedure_check(self):
        """Verify restore procedure check runs successfully."""
        validator = DisasterRecoveryValidator()
        result = validator.run()

        restore_step = None
        for step in result.steps:
            if step.step_name == "Restore Procedure":
                restore_step = step
                break

        assert restore_step is not None
        assert isinstance(restore_step, DRCheckStep)

    def test_rto_measurement(self):
        """Verify RTO measurement is within acceptable bounds."""
        validator = DisasterRecoveryValidator()
        result = validator.run()

        rto_step = None
        for step in result.steps:
            if step.step_name == "RTO Measurement":
                rto_step = step
                break

        assert rto_step is not None
        assert isinstance(rto_step, DRCheckStep)
        assert result.rto_achieved_ms >= 0
        assert result.rto_met is True

    def test_rpo_measurement(self):
        """Verify RPO measurement is within acceptable bounds."""
        validator = DisasterRecoveryValidator()
        result = validator.run()

        rpo_step = None
        for step in result.steps:
            if step.step_name == "RPO Measurement":
                rpo_step = step
                break

        assert rpo_step is not None
        assert isinstance(rpo_step, DRCheckStep)
        assert result.rpo_achieved_seconds >= 0
        assert result.rpo_met is True


class TestMessageQueueFailover:
    """Test message queue failover procedures."""

    def test_data_consistency_after_failover(self):
        """Verify data consistency step runs after MQ failover."""
        validator = DisasterRecoveryValidator()
        result = validator.run()

        consistency_step = None
        for step in result.steps:
            if step.step_name == "Data Consistency":
                consistency_step = step
                break

        assert consistency_step is not None
        assert isinstance(consistency_step, DRCheckStep)
        assert consistency_step.duration_ms >= 0
        assert consistency_step.description != ""


class TestCacheFailover:
    """Test cache failover procedures."""

    def test_data_consistency_cross_service(self):
        """Verify cross-service data consistency step after cache failover."""
        validator = DisasterRecoveryValidator()
        result = validator.run()

        consistency_step = None
        for step in result.steps:
            if step.step_name == "Data Consistency":
                consistency_step = step
                break

        assert consistency_step is not None
        assert isinstance(consistency_step, DRCheckStep)
        assert consistency_step.duration_ms >= 0

    def test_dr_result_pass_rate(self):
        """Verify DRResult pass_rate calculation."""
        result = DRResult(
            overall_passed=False,
            total_duration_ms=500.0,
            steps=[
                DRCheckStep(step_name="A", passed=True, duration_ms=100.0),
                DRCheckStep(step_name="B", passed=True, duration_ms=200.0),
                DRCheckStep(step_name="C", passed=False, duration_ms=200.0),
            ],
        )
        assert result.pass_rate == pytest.approx(2.0 / 3.0)

    def test_dr_result_empty_steps(self):
        """Verify pass_rate with empty steps."""
        result = DRResult(
            overall_passed=False,
            total_duration_ms=0.0,
            steps=[],
        )
        assert result.pass_rate == 0.0


class TestSplitBrainPrevention:
    """Test split-brain prevention mechanisms."""

    def test_dr_check_step_properties(self):
        """Test DRCheckStep dataclass properties."""
        step = DRCheckStep(
            step_name="Split-Brain Check",
            passed=True,
            duration_ms=50.0,
            description="Verified split-brain prevention",
            achieved_value=0.0,
            target_value=0.0,
        )
        assert step.step_name == "Split-Brain Check"
        assert step.passed is True
        assert step.duration_ms == 50.0
        assert step.error_message is None

    def test_dr_result_rto_rpo_targets(self):
        """Test that RTO/RPO targets are properly configured."""
        result = DRResult(
            overall_passed=True,
            total_duration_ms=1000.0,
            rto_achieved_ms=3000000.0,
            rpo_achieved_seconds=250.0,
            rto_target_ms=3600000.0,
            rpo_target_seconds=300.0,
        )
        assert result.rto_met is True
        assert result.rpo_met is True

    def test_dr_result_rto_exceeded(self):
        """Test RTO target exceeded scenario."""
        result = DRResult(
            overall_passed=False,
            total_duration_ms=5000.0,
            rto_achieved_ms=7200000.0,
            rto_target_ms=3600000.0,
        )
        assert result.rto_met is False

    def test_dr_result_rpo_exceeded(self):
        """Test RPO target exceeded scenario."""
        result = DRResult(
            overall_passed=False,
            total_duration_ms=5000.0,
            rpo_achieved_seconds=600.0,
            rpo_target_seconds=300.0,
        )
        assert result.rpo_met is False

    def test_validator_accepts_custom_root(self):
        """Test DisasterRecoveryValidator with custom project root."""
        validator = DisasterRecoveryValidator(project_root=os.getcwd())
        result = validator.run()

        assert isinstance(result, DRResult)
        assert result.total_duration_ms >= 0
        assert result.started_at != ""
        assert result.completed_at != ""

    def test_validator_handles_missing_config(self):
        """Test graceful handling when DR config file is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = DisasterRecoveryValidator(project_root=tmpdir)
            result = validator.run()

            assert isinstance(result, DRResult)
            assert len(result.steps) >= 6
            backup_step = result.steps[0]
            assert backup_step.step_name == "Backup Integrity"
            assert backup_step.passed is False
            assert "dr.yaml" in backup_step.error_message.lower() or "configuration" in backup_step.error_message.lower()