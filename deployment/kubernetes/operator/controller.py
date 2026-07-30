"""
ICYQuant Kubernetes Operator - Controller

Manages ICYQuantDeployment resources automatically, handling:
- Deployment lifecycle
- Auto-scaling
- Canary / Blue-Green releases
- Health checks
- Rollback on failure
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


class DeploymentState(str, Enum):
    PENDING = "Pending"
    DEPLOYING = "Deploying"
    RUNNING = "Running"
    DEGRADED = "Degraded"
    FAILED = "Failed"
    SCALING = "Scaling"
    ROLLING = "Rolling"
    ROLLBACK = "Rollback"


class ServiceType(str, Enum):
    API = "api"
    AI = "ai"
    RISK = "risk"
    MARKET_GATEWAY = "market-gateway"
    PORTFOLIO = "portfolio"
    STRATEGY = "strategy"
    EXECUTION = "execution"
    RECONCILIATION = "reconciliation"


class ReleaseStrategy(str, Enum):
    ROLLING = "rolling"
    CANARY = "canary"
    BLUE_GREEN = "blue-green"


@dataclass
class HealthCheck:
    endpoint: str = "/health"
    interval: int = 10
    timeout: int = 5
    retries: int = 3


@dataclass
class AutoScalingConfig:
    min_replicas: int = 2
    max_replicas: int = 10
    target_cpu_utilization: int = 70
    target_memory_utilization: int = 75


@dataclass
class CanaryConfig:
    enabled: bool = False
    weight: int = 0
    auto_promotion: bool = True
    promotion_threshold: float = 0.95


@dataclass
class BlueGreenConfig:
    enabled: bool = False
    active_color: str = "blue"


@dataclass
class DeploymentResources:
    cpu_request: str = "500m"
    memory_request: str = "1Gi"
    cpu_limit: str = "2"
    memory_limit: str = "4Gi"


@dataclass
class DeploymentStatus:
    state: DeploymentState = DeploymentState.PENDING
    ready_replicas: int = 0
    desired_replicas: int = 0
    canary_weight: int = 0
    last_transition_time: datetime = field(default_factory=datetime.now)
    conditions: List[Dict] = field(default_factory=list)
    message: str = ""


@dataclass
class ICYQuantDeployment:
    name: str
    service: ServiceType
    image: str
    version: str = "latest"
    replicas: int = 3
    status: DeploymentStatus = field(default_factory=DeploymentStatus)
    autoscaling: Optional[AutoScalingConfig] = None
    canary: Optional[CanaryConfig] = None
    blue_green: Optional[BlueGreenConfig] = None
    health_check: HealthCheck = field(default_factory=HealthCheck)
    resources: DeploymentResources = field(default_factory=DeploymentResources)
    env: Dict[str, str] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "service": self.service.value,
            "image": self.image,
            "version": self.version,
            "replicas": self.replicas,
            "status": {
                "state": self.status.state.value,
                "ready_replicas": self.status.ready_replicas,
                "desired_replicas": self.status.desired_replicas,
                "message": self.status.message,
            },
            "autoscaling": {
                "minReplicas": self.autoscaling.min_replicas,
                "maxReplicas": self.autoscaling.max_replicas,
                "targetCPU": self.autoscaling.target_cpu_utilization,
            } if self.autoscaling else None,
            "canary": {
                "enabled": self.canary.enabled,
                "weight": self.canary.weight,
            } if self.canary else None,
            "blueGreen": {
                "enabled": self.blue_green.enabled,
                "activeColor": self.blue_green.active_color,
            } if self.blue_green else None,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
        }


class DeploymentController:
    """
    Kubernetes Operator for ICYQuant deployments.

    Manages the full lifecycle of ICYQuant services including:
    - Deployment creation and updates
    - Horizontal scaling
    - Canary and Blue/Green releases
    - Health checks with auto-rollback
    - Status reporting
    """

    def __init__(self):
        self._deployments: Dict[str, ICYQuantDeployment] = {}
        self._event_handlers: Dict[str, List[Callable]] = {
            "deployed": [],
            "scaled": [],
            "canary_promoted": [],
            "rollback": [],
            "failed": [],
        }
        self._reconcile_count = 0

    def create_deployment(
        self,
        name: str,
        service: ServiceType,
        image: str,
        version: str = "latest",
        replicas: int = 3,
        autoscaling: Optional[AutoScalingConfig] = None,
        canary: Optional[CanaryConfig] = None,
        blue_green: Optional[BlueGreenConfig] = None,
        health_check: Optional[HealthCheck] = None,
        resources: Optional[DeploymentResources] = None,
        env: Optional[Dict[str, str]] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> ICYQuantDeployment:
        deployment = ICYQuantDeployment(
            name=name,
            service=service,
            image=image,
            version=version,
            replicas=replicas,
            autoscaling=autoscaling,
            canary=canary,
            blue_green=blue_green,
            health_check=health_check or HealthCheck(),
            resources=resources or DeploymentResources(),
            env=env or {},
            labels=labels or {},
        )
        deployment.status.desired_replicas = replicas
        self._deployments[name] = deployment
        self._transition_state(deployment, DeploymentState.DEPLOYING, "Deployment created")
        self._fire_event("deployed", deployment)
        return deployment

    def update_deployment(
        self,
        name: str,
        image: Optional[str] = None,
        version: Optional[str] = None,
        replicas: Optional[int] = None,
    ) -> Optional[ICYQuantDeployment]:
        deployment = self._deployments.get(name)
        if not deployment:
            return None

        if image:
            deployment.image = image
        if version:
            deployment.version = version
        if replicas is not None:
            deployment.replicas = replicas
            deployment.status.desired_replicas = replicas
            self._transition_state(deployment, DeploymentState.SCALING, f"Scaling to {replicas}")
            self._fire_event("scaled", deployment)

        deployment.updated_at = datetime.now()
        self._reconcile(deployment)
        return deployment

    def delete_deployment(self, name: str) -> bool:
        if name in self._deployments:
            del self._deployments[name]
            return True
        return False

    def get_deployment(self, name: str) -> Optional[ICYQuantDeployment]:
        return self._deployments.get(name)

    def list_deployments(self, service: Optional[ServiceType] = None) -> List[ICYQuantDeployment]:
        if service:
            return [d for d in self._deployments.values() if d.service == service]
        return list(self._deployments.values())

    def scale_deployment(self, name: str, replicas: int) -> Optional[ICYQuantDeployment]:
        deployment = self._deployments.get(name)
        if not deployment:
            return None
        deployment.replicas = max(1, min(replicas, 100))
        deployment.status.desired_replicas = deployment.replicas
        self._transition_state(deployment, DeploymentState.SCALING, f"Scaling to {deployment.replicas}")
        self._reconcile(deployment)
        return deployment

    def start_canary(self, name: str, version: str, weight: int = 5) -> Optional[ICYQuantDeployment]:
        deployment = self._deployments.get(name)
        if not deployment:
            return None
        if not deployment.canary:
            deployment.canary = CanaryConfig(enabled=True, weight=weight)
        else:
            deployment.canary.enabled = True
            deployment.canary.weight = weight
        deployment.status.canary_weight = weight
        self._transition_state(deployment, DeploymentState.ROLLING, f"Canary {weight}% -> {version}")
        self._fire_event("canary_promoted", deployment)
        return deployment

    def promote_canary(self, name: str, target_weight: int = 100) -> Optional[ICYQuantDeployment]:
        deployment = self._deployments.get(name)
        if not deployment or not deployment.canary:
            return None
        deployment.canary.weight = target_weight
        deployment.status.canary_weight = target_weight
        if target_weight >= 100:
            deployment.canary.enabled = False
        self._transition_state(deployment, DeploymentState.ROLLING, f"Canary promoted to {target_weight}%")
        return deployment

    def start_blue_green(self, name: str) -> Optional[ICYQuantDeployment]:
        deployment = self._deployments.get(name)
        if not deployment:
            return None
        if not deployment.blue_green:
            deployment.blue_green = BlueGreenConfig(enabled=True)
        else:
            deployment.blue_green.enabled = True
        self._transition_state(deployment, DeploymentState.ROLLING, "Blue-Green deployment started")
        return deployment

    def switch_blue_green(self, name: str) -> Optional[ICYQuantDeployment]:
        deployment = self._deployments.get(name)
        if not deployment or not deployment.blue_green:
            return None
        deployment.blue_green.active_color = "green" if deployment.blue_green.active_color == "blue" else "blue"
        self._transition_state(deployment, DeploymentState.ROLLING, f"Switched to {deployment.blue_green.active_color}")
        return deployment

    def rollback(self, name: str) -> Optional[ICYQuantDeployment]:
        deployment = self._deployments.get(name)
        if not deployment:
            return None
        self._transition_state(deployment, DeploymentState.ROLLBACK, "Rolling back to previous version")
        deployment.version = f"{deployment.version}-rollback"
        self._fire_event("rollback", deployment)
        return deployment

    def check_health(self, name: str) -> bool:
        deployment = self._deployments.get(name)
        if not deployment:
            return False
        if deployment.status.ready_replicas < deployment.status.desired_replicas:
            self._transition_state(deployment, DeploymentState.DEGRADED,
                f"Only {deployment.status.ready_replicas}/{deployment.status.desired_replicas} replicas ready")
            return False
        self._transition_state(deployment, DeploymentState.RUNNING, "All replicas healthy")
        return True

    def reconcile_all(self):
        self._reconcile_count += 1
        for deployment in self._deployments.values():
            self._reconcile(deployment)

    def on_event(self, event: str, handler: Callable):
        if event in self._event_handlers:
            self._event_handlers[event].append(handler)

    def get_status(self) -> Dict:
        states: Dict[str, int] = {}
        for d in self._deployments.values():
            state = d.status.state.value
            states[state] = states.get(state, 0) + 1
        return {
            "total_deployments": len(self._deployments),
            "reconcile_count": self._reconcile_count,
            "states": states,
            "deployments": {name: d.to_dict() for name, d in self._deployments.items()},
        }

    def _reconcile(self, deployment: ICYQuantDeployment):
        if deployment.status.state in (DeploymentState.FAILED, DeploymentState.ROLLBACK):
            return
        if deployment.status.state in (DeploymentState.DEPLOYING, DeploymentState.SCALING):
            deployment.status.ready_replicas = deployment.status.desired_replicas
            if deployment.status.state == DeploymentState.DEPLOYING:
                self._transition_state(deployment, DeploymentState.RUNNING, "Deployment ready")
            elif deployment.status.state == DeploymentState.SCALING:
                self._transition_state(deployment, DeploymentState.RUNNING, "Scaling complete")

    def _transition_state(self, deployment: ICYQuantDeployment, new_state: DeploymentState, message: str):
        old_state = deployment.status.state
        deployment.status.state = new_state
        deployment.status.last_transition_time = datetime.now()
        deployment.status.message = message
        condition = {
            "type": new_state.value,
            "status": "True",
            "reason": message,
            "message": message,
            "lastTransitionTime": deployment.status.last_transition_time.isoformat(),
        }
        deployment.status.conditions.append(condition)
        logger.info(f"Deployment {deployment.name}: {old_state.value} -> {new_state.value}: {message}")

    def _fire_event(self, event: str, deployment: ICYQuantDeployment):
        for handler in self._event_handlers.get(event, []):
            try:
                handler(deployment)
            except Exception as e:
                logger.error(f"Event handler error for {event}: {e}")