"""
Tests for ICYQuant Kubernetes Operator - DeploymentController and Reconciler.
"""

import pytest
from datetime import datetime

from deployment.kubernetes.operator.controller import (
    DeploymentController,
    ICYQuantDeployment,
    DeploymentState,
    ServiceType,
    ReleaseStrategy,
    AutoScalingConfig,
    CanaryConfig,
    BlueGreenConfig,
    HealthCheck,
    DeploymentStatus,
)
from deployment.kubernetes.operator.reconciler import (
    Reconciler,
    ClusterState,
    DesiredState,
    ReconcileAction,
    ReconcileResult,
)


class TestDeploymentController:
    """Test Kubernetes operator deployment controller."""

    def test_create_deployment(self):
        controller = DeploymentController()
        deployment = controller.create_deployment(
            name="test-api",
            service=ServiceType.API,
            image="ghcr.io/icyquant/api:v0.1",
            version="v0.1",
            replicas=3,
        )
        assert deployment.name == "test-api"
        assert deployment.service == ServiceType.API
        assert deployment.status.state == DeploymentState.DEPLOYING
        assert deployment.status.desired_replicas == 3

    def test_update_deployment(self):
        controller = DeploymentController()
        controller.create_deployment(
            name="test-api",
            service=ServiceType.API,
            image="ghcr.io/icyquant/api:v0.1",
        )
        updated = controller.update_deployment(
            name="test-api",
            version="v0.2",
        )
        assert updated.version == "v0.2"

    def test_scale_deployment(self):
        controller = DeploymentController()
        controller.create_deployment(
            name="test-api",
            service=ServiceType.API,
            image="ghcr.io/icyquant/api:v0.1",
            replicas=3,
        )
        scaled = controller.scale_deployment("test-api", 10)
        assert scaled.replicas == 10
        assert scaled.status.state == DeploymentState.RUNNING

    def test_start_canary(self):
        controller = DeploymentController()
        controller.create_deployment(
            name="test-api",
            service=ServiceType.API,
            image="ghcr.io/icyquant/api:v0.1",
        )
        result = controller.start_canary("test-api", "v0.2", weight=5)
        assert result.canary.enabled is True
        assert result.canary.weight == 5

    def test_promote_canary(self):
        controller = DeploymentController()
        controller.create_deployment(
            name="test-api",
            service=ServiceType.API,
            image="ghcr.io/icyquant/api:v0.1",
        )
        controller.start_canary("test-api", "v0.2", weight=5)
        result = controller.promote_canary("test-api", target_weight=100)
        assert result.canary.weight == 100

    def test_blue_green_deployment(self):
        controller = DeploymentController()
        controller.create_deployment(
            name="test-api",
            service=ServiceType.API,
            image="ghcr.io/icyquant/api:v0.1",
        )
        controller.start_blue_green("test-api")
        result = controller.switch_blue_green("test-api")
        assert result.blue_green.active_color in ("blue", "green")

    def test_rollback(self):
        controller = DeploymentController()
        controller.create_deployment(
            name="test-api",
            service=ServiceType.API,
            image="ghcr.io/icyquant/api:v0.1",
            version="v0.1",
        )
        controller.update_deployment("test-api", version="v0.2")
        result = controller.rollback("test-api")
        assert result.status.state == DeploymentState.ROLLBACK

    def test_check_health(self):
        controller = DeploymentController()
        deployment = controller.create_deployment(
            name="test-api",
            service=ServiceType.API,
            image="ghcr.io/icyquant/api:v0.1",
            replicas=3,
        )
        controller.reconcile_all()
        healthy = controller.check_health("test-api")
        assert healthy is True
        deployment = controller.get_deployment("test-api")
        assert deployment.status.state == DeploymentState.RUNNING

    def test_list_deployments(self):
        controller = DeploymentController()
        controller.create_deployment("api-1", ServiceType.API, "img:v1")
        controller.create_deployment("ai-1", ServiceType.AI, "img:v1")
        all_deployments = controller.list_deployments()
        assert len(all_deployments) == 2
        api_deployments = controller.list_deployments(service=ServiceType.API)
        assert len(api_deployments) == 1

    def test_get_status(self):
        controller = DeploymentController()
        controller.create_deployment("api-1", ServiceType.API, "img:v1")
        status = controller.get_status()
        assert status["total_deployments"] == 1
        assert "states" in status

    def test_reconcile_all(self):
        controller = DeploymentController()
        deployment = controller.create_deployment("api-1", ServiceType.API, "img:v1", replicas=3)
        assert deployment.status.state == DeploymentState.DEPLOYING
        controller.reconcile_all()
        deployment = controller.get_deployment("api-1")
        assert deployment.status.state == DeploymentState.RUNNING

    def test_event_handlers(self):
        controller = DeploymentController()
        events = []
        controller.on_event("deployed", lambda d: events.append(d.name))
        controller.create_deployment("api-1", ServiceType.API, "img:v1")
        assert "api-1" in events

    def test_deployment_to_dict(self):
        controller = DeploymentController()
        deployment = controller.create_deployment(
            name="test-api",
            service=ServiceType.API,
            image="ghcr.io/icyquant/api:v0.1",
            autoscaling=AutoScalingConfig(min_replicas=5, max_replicas=50),
        )
        d = deployment.to_dict()
        assert d["name"] == "test-api"
        assert d["service"] == "api"
        assert d["autoscaling"] is not None


class TestReconciler:
    """Test reconciler reconciliation loop."""

    def test_create_action(self):
        reconciler = Reconciler()
        desired = DesiredState(
            name="test-svc",
            service="api",
            replicas=3,
            version="v0.1",
            image="img:v1",
        )
        result = reconciler.reconcile(desired)
        assert result.action.value == "CREATE_DEPLOYMENT"

    def test_no_action_when_matching(self):
        reconciler = Reconciler()
        current = ClusterState(
            name="test-svc",
            replicas=3,
            version="v0.1",
            image="img:v1",
            status="Running",
            ready_replicas=3,
        )
        desired = DesiredState(
            name="test-svc",
            service="api",
            replicas=3,
            version="v0.1",
            image="img:v1",
        )
        reconciler.update_state(current)
        result = reconciler.reconcile(desired)
        assert result.action.value == "NO_ACTION"

    def test_scaling_detection(self):
        reconciler = Reconciler()
        current = ClusterState(
            name="test-svc",
            replicas=3,
            version="v0.1",
            image="img:v1",
            status="Running",
            ready_replicas=3,
        )
        desired = DesiredState(
            name="test-svc",
            service="api",
            replicas=10,
            version="v0.1",
            image="img:v1",
        )
        reconciler.update_state(current)
        result = reconciler.reconcile(desired)
        assert result.action.value in ("SCALE_DEPLOYMENT", "ROLLING_UPDATE")

    def test_canary_promote_action(self):
        reconciler = Reconciler()
        current = ClusterState(
            name="test-svc",
            version="v0.1",
            status="Running",
        )
        desired = DesiredState(
            name="test-svc",
            service="api",
            version="v0.2",
            strategy="canary",
            canary_weight=50,
            replicas=3,
        )
        reconciler.update_state(current)
        result = reconciler.reconcile(desired)
        assert result.action.value == "CANARY_PROMOTE"

    def test_reconcile_history(self):
        reconciler = Reconciler()
        desired = DesiredState(
            name="test-svc",
            service="api",
            replicas=3,
            version="v0.1",
            image="img:v1",
        )
        reconciler.reconcile(desired)
        history = reconciler.get_history()
        assert len(history) > 0

    def test_observe_and_update_state(self):
        reconciler = Reconciler()
        state = reconciler.observe("test-svc")
        assert state.name == "test-svc"
        state.replicas = 5
        reconciler.update_state(state)
        updated = reconciler.observe("test-svc")
        assert updated.replicas == 5

    def test_reconcile_multiple(self):
        reconciler = Reconciler()
        desired_states = [
            DesiredState(name="svc-a", service="api", replicas=3, version="v1", image="a:v1"),
            DesiredState(name="svc-b", service="ai", replicas=2, version="v1", image="b:v1"),
        ]
        results = reconciler.reconcile_all(desired_states)
        assert len(results) == 2
        assert all(r.action.value != "NO_ACTION" for r in results)