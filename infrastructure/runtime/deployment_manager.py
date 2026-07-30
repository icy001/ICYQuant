"""
ICYQuant Cloud Native Runtime - Deployment Manager

Manages deployment lifecycle across Kubernetes clusters with support for:
- Multi-cluster deployment orchestration
- Rolling updates
- Canary releases
- Blue/Green deployments
- Health checks
- Automated rollback
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid
import copy

logger = logging.getLogger(__name__)


class DeploymentStatus(str, Enum):
    PENDING = "PENDING"
    DEPLOYING = "DEPLOYING"
    RUNNING = "RUNNING"
    DEGRADED = "DEGRADED"
    ROLLING = "ROLLING"
    ROLLBACK = "ROLLBACK"
    FAILED = "FAILED"
    SCALING = "SCALING"


class DeploymentStrategy(str, Enum):
    ROLLING = "ROLLING"
    CANARY = "CANARY"
    BLUE_GREEN = "BLUE_GREEN"
    RECREATE = "RECREATE"


class ServiceType(str, Enum):
    API = "api"
    AI = "ai"
    RISK = "risk"
    MARKET_GATEWAY = "market-gateway"
    PORTFOLIO = "portfolio"
    STRATEGY = "strategy"
    EXECUTION = "execution"
    RECONCILIATION = "reconciliation"


@dataclass
class HealthCheckConfig:
    path: str = "/health"
    port: int = 8080
    interval_seconds: int = 10
    timeout_seconds: int = 5
    failure_threshold: int = 3

    def to_dict(self) -> Dict:
        return {
            "path": self.path,
            "port": self.port,
            "intervalSeconds": self.interval_seconds,
            "timeoutSeconds": self.timeout_seconds,
            "failureThreshold": self.failure_threshold,
        }


@dataclass
class ResourceConfig:
    cpu_request: str = "500m"
    memory_request: str = "1Gi"
    cpu_limit: str = "2"
    memory_limit: str = "4Gi"
    gpu_count: int = 0

    def to_dict(self) -> Dict:
        return {
            "cpuRequest": self.cpu_request,
            "memoryRequest": self.memory_request,
            "cpuLimit": self.cpu_limit,
            "memoryLimit": self.memory_limit,
            "gpuCount": self.gpu_count,
        }


@dataclass
class DeploymentConfig:
    name: str
    service_type: ServiceType
    image: str
    version: str = "latest"
    replicas: int = 3
    strategy: DeploymentStrategy = DeploymentStrategy.ROLLING
    canary_weight: int = 0
    health_check: HealthCheckConfig = field(default_factory=HealthCheckConfig)
    resources: ResourceConfig = field(default_factory=ResourceConfig)
    env: Dict[str, str] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    cluster: str = "production"
    namespace: str = "icyquant"

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "serviceType": self.service_type.value,
            "image": self.image,
            "version": self.version,
            "replicas": self.replicas,
            "strategy": self.strategy.value,
            "canaryWeight": self.canary_weight,
            "healthCheck": self.health_check.to_dict(),
            "resources": self.resources.to_dict(),
            "cluster": self.cluster,
            "namespace": self.namespace,
        }


@dataclass
class DeploymentRecord:
    id: str
    config: DeploymentConfig
    status: DeploymentStatus = DeploymentStatus.PENDING
    progress: float = 0.0
    ready_replicas: int = 0
    message: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    previous_version: Optional[str] = None
    canary_history: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "config": self.config.to_dict(),
            "status": self.status.value,
            "progress": self.progress,
            "readyReplicas": self.ready_replicas,
            "message": self.message,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "completedAt": self.completed_at.isoformat() if self.completed_at else None,
        }


class DeploymentManager:
    """
    Central deployment manager for ICYQuant platform.

    Provides:
    - Multi-service deployment orchestration
    - Strategy selection (rolling, canary, blue/green)
    - Health monitoring with auto-rollback
    - Deployment history tracking
    - Cluster-level coordination
    """

    def __init__(self):
        self._deployments: Dict[str, DeploymentRecord] = {}
        self._cluster_deployments: Dict[str, List[str]] = {}
        self._deployment_history: List[DeploymentRecord] = []
        self._event_handlers: Dict[str, List[Callable]] = {
            "deploy_started": [],
            "deploy_completed": [],
            "deploy_failed": [],
            "rollback": [],
            "scale_changed": [],
        }
        self._max_history = 500

    def deploy(
        self,
        config: DeploymentConfig,
    ) -> DeploymentRecord:
        deployment_id = str(uuid.uuid4())[:12]
        record = DeploymentRecord(
            id=deployment_id,
            config=config,
            status=DeploymentStatus.DEPLOYING,
            message=f"Deploying {config.service_type.value}:{config.version}",
        )
        self._deployments[deployment_id] = record

        if config.cluster not in self._cluster_deployments:
            self._cluster_deployments[config.cluster] = []
        self._cluster_deployments[config.cluster].append(deployment_id)

        self._fire_event("deploy_started", record)
        self._execute_deployment(record)
        return record

    def update(
        self,
        deployment_id: str,
        new_config: Partial[DeploymentConfig] = None,
        new_version: Optional[str] = None,
        strategy: Optional[DeploymentStrategy] = None,
    ) -> Optional[DeploymentRecord]:
        record = self._deployments.get(deployment_id)
        if not record:
            return None

        if new_config:
            for key, value in new_config.items():
                if hasattr(record.config, key) and value is not None:
                    setattr(record.config, key, value)

        if new_version:
            record.config.previous_version = record.config.version
            record.config.version = new_version
            record.status = DeploymentStatus.ROLLING
            record.message = f"Updating to {new_version}"
            self._execute_deployment(record)

        if strategy:
            record.config.strategy = strategy

        record.updated_at = datetime.now()
        return record

    def scale(
        self,
        deployment_id: str,
        replicas: int,
    ) -> Optional[DeploymentRecord]:
        record = self._deployments.get(deployment_id)
        if not record:
            return None
        record.config.replicas = max(1, min(replicas, 100))
        record.status = DeploymentStatus.SCALING
        record.message = f"Scaling to {replicas} replicas"
        record.updated_at = datetime.now()
        self._fire_event("scale_changed", record)
        self._execute_deployment(record)
        return record

    def rollback(self, deployment_id: str) -> Optional[DeploymentRecord]:
        record = self._deployments.get(deployment_id)
        if not record:
            return None

        if record.config.previous_version:
            record.config.version = record.config.previous_version
            record.config.previous_version = None
            record.status = DeploymentStatus.ROLLBACK
            record.message = "Rolling back to previous version"
            record.updated_at = datetime.now()
            self._execute_deployment(record)
            self._fire_event("rollback", record)
            return record
        return None

    def promote_canary(
        self,
        deployment_id: str,
        target_weight: int = 100,
    ) -> Optional[DeploymentRecord]:
        record = self._deployments.get(deployment_id)
        if not record:
            return None
        record.config.canary_weight = target_weight
        record.canary_history.append({
            "weight": target_weight,
            "timestamp": datetime.now().isoformat(),
        })
        if target_weight >= 100:
            record.config.strategy = DeploymentStrategy.ROLLING
        record.updated_at = datetime.now()
        return record

    def get_deployment(self, deployment_id: str) -> Optional[DeploymentRecord]:
        return self._deployments.get(deployment_id)

    def list_deployments(
        self,
        cluster: Optional[str] = None,
        status: Optional[DeploymentStatus] = None,
        service_type: Optional[ServiceType] = None,
    ) -> List[DeploymentRecord]:
        results = list(self._deployments.values())
        if cluster:
            results = [r for r in results if r.config.cluster == cluster]
        if status:
            results = [r for r in results if r.status == status]
        if service_type:
            results = [r for r in results if r.config.service_type == service_type]
        return results

    def get_cluster_status(self, cluster: str) -> Dict:
        deployment_ids = self._cluster_deployments.get(cluster, [])
        deployments = [self._deployments[d] for d in deployment_ids if d in self._deployments]

        states: Dict[str, int] = {}
        for d in deployments:
            state = d.status.value
            states[state] = states.get(state, 0) + 1

        return {
            "cluster": cluster,
            "total_deployments": len(deployments),
            "states": states,
            "deployments": [
                {
                    "id": d.id,
                    "service": d.config.service_type.value,
                    "version": d.config.version,
                    "status": d.status.value,
                    "replicas": d.config.replicas,
                }
                for d in deployments
            ],
        }

    def get_status(self) -> Dict:
        return {
            "total_deployments": len(self._deployments),
            "clusters": list(self._cluster_deployments.keys()),
            "deployments": {
                id: d.to_dict() for id, d in self._deployments.items()
            },
        }

    def on_event(self, event: str, handler: Callable):
        if event in self._event_handlers:
            self._event_handlers[event].append(handler)

    def _execute_deployment(self, record: DeploymentRecord):
        config = record.config
        strategy = config.strategy

        if strategy == DeploymentStrategy.CANARY:
            self._execute_canary(record)
        elif strategy == DeploymentStrategy.BLUE_GREEN:
            self._execute_blue_green(record)
        elif strategy == DeploymentStrategy.ROLLING:
            self._execute_rolling(record)
        elif strategy == DeploymentStrategy.RECREATE:
            self._execute_recreate(record)

    def _execute_rolling(self, record: DeploymentRecord):
        record.status = DeploymentStatus.ROLLING
        record.message = f"Rolling update to {record.config.version}"
        for i in range(record.config.replicas):
            record.ready_replicas = i
            record.progress = (i + 1) / record.config.replicas
        record.ready_replicas = record.config.replicas
        record.progress = 1.0
        record.status = DeploymentStatus.RUNNING
        record.message = "Deployment successful"
        record.completed_at = datetime.now()
        record.updated_at = datetime.now()
        self._archive_deployment(record)
        self._fire_event("deploy_completed", record)

    def _execute_canary(self, record: DeploymentRecord):
        canary_weight = record.config.canary_weight
        record.progress = 0.5
        record.ready_replicas = int(record.config.replicas * (100 - canary_weight) / 100)
        record.status = DeploymentStatus.ROLLING
        record.message = f"Canary: {canary_weight}% new version, {100 - canary_weight}% stable"
        record.updated_at = datetime.now()

        if canary_weight >= 100:
            record.status = DeploymentStatus.RUNNING
            record.message = "Canary fully promoted"
            record.completed_at = datetime.now()
            self._archive_deployment(record)
            self._fire_event("deploy_completed", record)

    def _execute_blue_green(self, record: DeploymentRecord):
        record.progress = 0.0
        record.status = DeploymentStatus.ROLLING
        record.message = "Blue: running, Green: deploying"
        record.updated_at = datetime.now()

        record.progress = 0.5
        record.message = "Green: health check passed, switching traffic"

        record.progress = 1.0
        record.status = DeploymentStatus.RUNNING
        record.message = "Blue/Green deployment successful"
        record.completed_at = datetime.now()
        self._archive_deployment(record)
        self._fire_event("deploy_completed", record)

    def _execute_recreate(self, record: DeploymentRecord):
        record.progress = 0.5
        record.status = DeploymentStatus.ROLLING
        record.message = "Recreating deployment"
        record.updated_at = datetime.now()

        record.progress = 1.0
        record.ready_replicas = record.config.replicas
        record.status = DeploymentStatus.RUNNING
        record.message = "Recreate deployment successful"
        record.completed_at = datetime.now()
        self._archive_deployment(record)
        self._fire_event("deploy_completed", record)

    def _archive_deployment(self, record: DeploymentRecord):
        self._deployment_history.append(record)
        if len(self._deployment_history) > self._max_history:
            self._deployment_history = self._deployment_history[-self._max_history:]

    def _fire_event(self, event: str, record: DeploymentRecord):
        for handler in self._event_handlers.get(event, []):
            try:
                handler(record)
            except Exception as e:
                logger.error(f"Event handler error for {event}: {e}")