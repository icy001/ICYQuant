"""
Tests for ICYQuant Disaster Recovery Manager.
"""

import pytest

from infrastructure.runtime.disaster_recovery import (
    DisasterRecoveryManager,
    RegionConfig,
    FailoverPlan,
    RPOConfig,
    RTOConfig,
    BackupConfig,
    RestorePoint,
    DRState,
    ReplicationMode,
)


class TestDisasterRecovery:
    """Test disaster recovery management."""

    def test_add_region(self):
        dr = DisasterRecoveryManager()
        region = dr.add_region(
            region_id="us-east-1",
            name="US East",
            endpoint="https://us-east-1.icyquant.io",
            role="primary",
        )
        assert region.id == "us-east-1"
        assert region.role == "primary"

    def test_create_failover_plan(self):
        dr = DisasterRecoveryManager()
        plan = dr.create_failover_plan(
            name="production-dr",
            primary_region="us-east-1",
            standby_regions=["us-west-2", "eu-west-1"],
            rpo_config=RPOConfig(target_seconds=300),
            rto_config=RTOConfig(target_seconds=900),
        )
        assert plan.name == "production-dr"
        assert plan.primary_region == "us-east-1"

    def test_rpo_compliance_check(self):
        dr = DisasterRecoveryManager()
        plan = dr.create_failover_plan(
            name="dr-plan",
            primary_region="us-east-1",
            standby_regions=["us-west-2"],
            rpo_config=RPOConfig(target_seconds=300),
        )
        dr.update_replication_lag(plan.id, lag_seconds=120)
        result = dr.check_rpo_compliance(plan.id)
        assert result["compliant"] is True

    def test_rpo_non_compliance(self):
        dr = DisasterRecoveryManager()
        plan = dr.create_failover_plan(
            name="dr-plan",
            primary_region="us-east-1",
            standby_regions=["us-west-2"],
            rpo_config=RPOConfig(target_seconds=300),
        )
        dr.update_replication_lag(plan.id, lag_seconds=2000)
        result = dr.check_rpo_compliance(plan.id)
        assert result["compliant"] is False
        assert result["status"] == "critical"

    def test_initiate_failover(self):
        dr = DisasterRecoveryManager()
        dr.add_region("us-east-1", "US East", "https://us-east-1.io", "primary")
        dr.add_region("us-west-2", "US West", "https://us-west-2.io", "standby")
        plan = dr.create_failover_plan(
            name="dr-plan",
            primary_region="us-east-1",
            standby_regions=["us-west-2"],
        )
        result = dr.initiate_failover(plan.id, target_region="us-west-2")
        assert result.primary_region == "us-west-2"
        assert result.last_failover is not None

    def test_restore_primary(self):
        dr = DisasterRecoveryManager()
        dr.add_region("us-east-1", "US East", "https://us-east-1.io", "primary")
        dr.add_region("us-west-2", "US West", "https://us-west-2.io", "standby")
        plan = dr.create_failover_plan(
            name="dr-plan",
            primary_region="us-east-1",
            standby_regions=["us-west-2"],
        )
        dr.initiate_failover(plan.id, target_region="us-west-2")
        result = dr.restore_primary(plan.id)
        assert result is not None

    def test_create_restore_point(self):
        dr = DisasterRecoveryManager()
        point = dr.create_restore_point("us-east-1", size_gb=100.0, point_type="full")
        assert point.id is not None
        assert point.size_gb == 100.0

    def test_get_restore_points(self):
        dr = DisasterRecoveryManager()
        dr.create_restore_point("us-east-1", size_gb=50.0, point_type="incremental")
        points = dr.get_restore_points("us-east-1")
        assert len(points) == 1

    def test_get_available_restore_points(self):
        dr = DisasterRecoveryManager()
        dr.create_restore_point("us-east-1", size_gb=50.0)
        dr.create_restore_point("us-west-2", size_gb=30.0)
        available = dr.get_available_restore_points()
        assert len(available) == 2

    def test_test_dr_plan(self):
        dr = DisasterRecoveryManager()
        plan = dr.create_failover_plan(
            name="dr-plan",
            primary_region="us-east-1",
            standby_regions=["us-west-2"],
        )
        result = dr.test_dr_plan(plan.id)
        assert result["success"] is True

    def test_get_status(self):
        dr = DisasterRecoveryManager()
        dr.add_region("us-east-1", "US East", "https://us-east-1.io", "primary")
        plan = dr.create_failover_plan(
            name="dr-plan",
            primary_region="us-east-1",
            standby_regions=["us-west-2"],
        )
        status = dr.get_status()
        assert "state" in status
        assert "regions" in status
        assert "plans" in status

    def test_failover_nonexistent_plan(self):
        dr = DisasterRecoveryManager()
        result = dr.initiate_failover("nonexistent")
        assert result is None

    def test_rpo_config_values(self):
        rpo = RPOConfig()
        assert rpo.target_seconds == 300
        assert rpo.warning_threshold_seconds == 600
        assert rpo.critical_threshold_seconds == 1800

    def test_rto_config_values(self):
        rto = RTOConfig()
        assert rto.target_seconds == 300
        assert rto.maximum_seconds == 900