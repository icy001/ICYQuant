"""
Tests for ICYQuant Release Manager and Deployment Manager.
"""

import pytest
from datetime import datetime

from infrastructure.runtime.deployment_manager import (
    DeploymentManager,
    DeploymentConfig,
    DeploymentStrategy,
    ServiceType,
    DeploymentRecord,
    DeploymentStatus,
    HealthCheckConfig,
    ResourceConfig,
)
from infrastructure.runtime.release_manager import (
    ReleaseManager,
    Release,
    ReleaseStrategy,
    ReleaseStatus,
    ReleaseQuality,
)


class TestDeploymentManager:
    """Test deployment lifecycle management."""

    def test_deploy_service(self):
        manager = DeploymentManager()
        config = DeploymentConfig(
            name="test-api",
            service_type=ServiceType.API,
            image="ghcr.io/icyquant/api:v0.1",
            version="v0.1",
            replicas=3,
        )
        record = manager.deploy(config)
        assert record.id is not None
        assert record.status in (DeploymentStatus.DEPLOYING, DeploymentStatus.RUNNING)

    def test_deploy_with_strategy(self):
        manager = DeploymentManager()
        config = DeploymentConfig(
            name="test-api",
            service_type=ServiceType.API,
            image="img:v1",
            strategy=DeploymentStrategy.CANARY,
            canary_weight=5,
            replicas=5,
        )
        record = manager.deploy(config)
        assert record.config.strategy == DeploymentStrategy.CANARY

    def test_update_deployment(self):
        manager = DeploymentManager()
        config = DeploymentConfig(
            name="test-api",
            service_type=ServiceType.API,
            image="img:v1",
            version="v0.1",
        )
        record = manager.deploy(config)
        updated = manager.update(record.id, new_version="v0.2")
        assert updated.config.version == "v0.2"

    def test_scale_deployment(self):
        manager = DeploymentManager()
        config = DeploymentConfig(
            name="test-api",
            service_type=ServiceType.API,
            image="img:v1",
            replicas=3,
        )
        record = manager.deploy(config)
        scaled = manager.scale(record.id, 10)
        assert scaled.config.replicas == 10

    def test_rollback(self):
        manager = DeploymentManager()
        config = DeploymentConfig(
            name="test-api",
            service_type=ServiceType.API,
            image="img:v1",
            version="v0.1",
        )
        record = manager.deploy(config)
        manager.update(record.id, new_version="v0.2")
        rolled_back = manager.rollback(record.id)
        assert rolled_back is not None

    def test_list_deployments(self):
        manager = DeploymentManager()
        manager.deploy(DeploymentConfig("api-1", ServiceType.API, "img:v1"))
        manager.deploy(DeploymentConfig("ai-1", ServiceType.AI, "img:v1"))
        all_deployments = manager.list_deployments()
        assert len(all_deployments) == 2

    def test_filter_deployments(self):
        manager = DeploymentManager()
        manager.deploy(DeploymentConfig("api-1", ServiceType.API, "img:v1"))
        manager.deploy(DeploymentConfig("ai-1", ServiceType.AI, "img:v1"))
        api_only = manager.list_deployments(service_type=ServiceType.API)
        assert len(api_only) == 1

    def test_get_cluster_status(self):
        manager = DeploymentManager()
        manager.deploy(DeploymentConfig("api-1", ServiceType.API, "img:v1", cluster="prod"))
        status = manager.get_cluster_status("prod")
        assert status["cluster"] == "prod"
        assert status["total_deployments"] == 1

    def test_get_status(self):
        manager = DeploymentManager()
        manager.deploy(DeploymentConfig("api-1", ServiceType.API, "img:v1"))
        status = manager.get_status()
        assert "total_deployments" in status

    def test_canary_promotion(self):
        manager = DeploymentManager()
        config = DeploymentConfig(
            name="test-api",
            service_type=ServiceType.API,
            image="img:v1",
            strategy=DeploymentStrategy.CANARY,
            canary_weight=5,
        )
        record = manager.deploy(config)
        promoted = manager.promote_canary(record.id, target_weight=50)
        assert promoted.config.canary_weight == 50
        assert promoted.id is not None

    def test_deployment_to_dict(self):
        manager = DeploymentManager()
        config = DeploymentConfig(
            name="test-api",
            service_type=ServiceType.API,
            image="img:v1",
            resources=ResourceConfig(cpu_request="1", memory_request="2Gi"),
        )
        record = manager.deploy(config)
        d = record.to_dict()
        assert d["id"] is not None
        assert d["config"]["serviceType"] == "api"


class TestReleaseManager:
    """Test release lifecycle management."""

    def test_create_release(self):
        manager = ReleaseManager()
        release = manager.create_release(
            version="v0.4.1",
            service="api",
            image="ghcr.io/icyquant/api:v0.4.1",
        )
        assert release.version == "v0.4.1"
        assert release.status == ReleaseStatus.PREPARING

    def test_start_release(self):
        manager = ReleaseManager()
        release = manager.create_release("v0.4.1", "api", "img:v0.4.1")
        started = manager.start_release(release.id)
        assert started.status == ReleaseStatus.DEPLOYING

    def test_promote_stage(self):
        manager = ReleaseManager()
        release = manager.create_release(
            "v0.4.1", "api", "img:v0.4.1",
            stages=[5, 20, 50, 100],
        )
        manager.start_release(release.id)
        promoted = manager.promote_stage(release.id)
        assert promoted.current_stage == 1
        assert promoted.canary_weight == 20

    def test_complete_release(self):
        manager = ReleaseManager()
        release = manager.create_release("v0.4.1", "api", "img:v0.4.1")
        manager.start_release(release.id)
        completed = manager.complete_release(release.id)
        assert completed.status == ReleaseStatus.COMPLETED

    def test_rollback_release(self):
        manager = ReleaseManager()
        release = manager.create_release("v0.4.1", "api", "img:v0.4.1")
        manager.start_release(release.id)
        rolled_back = manager.rollback_release(release.id, reason="Test rollback")
        assert rolled_back.status == ReleaseStatus.ROLLING_BACK

    def test_cancel_release(self):
        manager = ReleaseManager()
        release = manager.create_release("v0.4.1", "api", "img:v0.4.1")
        cancelled = manager.cancel_release(release.id)
        assert cancelled.status == ReleaseStatus.CANCELLED

    def test_quality_gate_pass(self):
        manager = ReleaseManager()
        release = manager.create_release("v0.4.1", "api", "img:v0.4.1")
        metrics = ReleaseQuality(
            error_rate=0.1,
            p95_latency_ms=100,
            cpu_utilization=50,
            memory_utilization=60,
            risk_events=0,
        )
        result = manager.evaluate_quality_gate(release.id, metrics)
        assert result.quality_metrics.passed is True

    def test_quality_gate_fail(self):
        manager = ReleaseManager()
        release = manager.create_release("v0.4.1", "api", "img:v0.4.1")
        metrics = ReleaseQuality(
            error_rate=5.0,
            p95_latency_ms=1000,
            cpu_utilization=90,
            memory_utilization=95,
            risk_events=5,
        )
        result = manager.evaluate_quality_gate(release.id, metrics)
        assert result.quality_metrics.passed is False

    def test_list_releases(self):
        manager = ReleaseManager()
        manager.create_release("v0.1", "api", "img:v0.1")
        manager.create_release("v0.2", "ai", "img:v0.2")
        all_releases = manager.list_releases()
        assert len(all_releases) == 2

    def test_get_status(self):
        manager = ReleaseManager()
        manager.create_release("v0.1", "api", "img:v0.1")
        status = manager.get_status()
        assert "activeReleases" in status