"""
ICYQuant Kubernetes Operator - Reconciler

Reconciles ICYQuantDeployment resources to maintain desired state.
Implements the reconciliation loop pattern with:
- Observation of current state
- Comparison with desired state
- Action to reconcile differences
- Status updates
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import logging
import copy

logger = logging.getLogger(__name__)


class ReconcileAction(str, Enum):
    NO_ACTION = "NO_ACTION"
    CREATE_DEPLOYMENT = "CREATE_DEPLOYMENT"
    UPDATE_DEPLOYMENT = "UPDATE_DEPLOYMENT"
    SCALE_DEPLOYMENT = "SCALE_DEPLOYMENT"
    ROLLING_UPDATE = "ROLLING_UPDATE"
    CANARY_PROMOTE = "CANARY_PROMOTE"
    ROLLBACK = "ROLLBACK"
    DELETE_RESOURCE = "DELETE_RESOURCE"
    HEALTH_CHECK = "HEALTH_CHECK"
    AUTO_SCALE = "AUTO_SCALE"


@dataclass
class ReconcileResult:
    action: ReconcileAction
    message: str
    changes: Dict = field(default_factory=dict)
    duration_ms: float = 0.0
    next_reconcile: Optional[timedelta] = None


@dataclass
class ClusterState:
    """Represents the current state of a cluster resource."""
    name: str
    namespace: str = "icyquant"
    replicas: int = 0
    ready_replicas: int = 0
    version: str = ""
    image: str = ""
    status: str = "Pending"
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "namespace": self.namespace,
            "replicas": self.replicas,
            "ready_replicas": self.ready_replicas,
            "version": self.version,
            "image": self.image,
            "status": self.status,
            "labels": self.labels,
            "lastUpdated": self.last_updated.isoformat(),
        }


@dataclass
class DesiredState:
    """Represents the desired state of a resource."""
    name: str
    service: str
    replicas: int = 3
    version: str = "latest"
    image: str = ""
    strategy: str = "rolling"
    canary_weight: int = 0
    blue_green_color: str = "blue"
    autoscaling: Optional[Dict] = None
    resources: Optional[Dict] = None
    env: Dict[str, str] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "service": self.service,
            "replicas": self.replicas,
            "version": self.version,
            "image": self.image,
            "strategy": self.strategy,
            "canaryWeight": self.canary_weight,
            "blueGreenColor": self.blue_green_color,
            "autoscaling": self.autoscaling,
            "resources": self.resources,
        }


class Reconciler:
    """
    Kubernetes controller reconciler.

    Implements the reconciliation loop pattern:
    1. Observe current state
    2. Compare with desired state
    3. Determine required actions
    4. Execute actions
    5. Update status
    6. Requeue if needed
    """

    def __init__(self):
        self._cluster_states: Dict[str, ClusterState] = {}
        self._reconcile_history: List[ReconcileResult] = []
        self._max_history = 1000

    def observe(self, name: str, namespace: str = "icyquant") -> ClusterState:
        """Observe current state of a resource."""
        if name not in self._cluster_states:
            self._cluster_states[name] = ClusterState(
                name=name,
                namespace=namespace,
            )
        return copy.deepcopy(self._cluster_states[name])

    def update_state(self, state: ClusterState):
        """Update the observed cluster state."""
        state.last_updated = datetime.now()
        self._cluster_states[state.name] = state

    def reconcile(
        self,
        desired: DesiredState,
        current: Optional[ClusterState] = None,
    ) -> ReconcileResult:
        """
        Reconcile the difference between desired and current state.

        Returns the action taken and the result.
        """
        start_time = datetime.now()

        if current is None:
            current = self.observe(desired.name)

        action = self._determine_action(desired, current)
        result = self._execute_action(action, desired, current)

        duration = (datetime.now() - start_time).total_seconds() * 1000
        result.duration_ms = duration

        self._reconcile_history.append(result)
        if len(self._reconcile_history) > self._max_history:
            self._reconcile_history = self._reconcile_history[-self._max_history:]

        return result

    def reconcile_all(self, desired_states: List[DesiredState]) -> List[ReconcileResult]:
        """Reconcile all desired states."""
        results = []
        for desired in desired_states:
            result = self.reconcile(desired)
            results.append(result)
        return results

    def get_history(self, limit: int = 100) -> List[Dict]:
        """Get reconciliation history."""
        return [
            {
                "action": r.action.value,
                "message": r.message,
                "duration_ms": r.duration_ms,
                "changes": r.changes,
            }
            for r in self._reconcile_history[-limit:]
        ]

    def get_states(self) -> Dict[str, ClusterState]:
        """Get all current cluster states."""
        return dict(self._cluster_states)

    def _determine_action(
        self,
        desired: DesiredState,
        current: ClusterState,
    ) -> ReconcileAction:
        """Determine what action to take."""

        if current.status == "Pending" and current.replicas == 0:
            return ReconcileAction.CREATE_DEPLOYMENT

        if current.version != desired.version and desired.strategy == "canary":
            if desired.canary_weight > 0 and desired.canary_weight < 100:
                return ReconcileAction.CANARY_PROMOTE

        if current.version != desired.version:
            return ReconcileAction.ROLLING_UPDATE

        if current.replicas != desired.replicas:
            return ReconcileAction.SCALE_DEPLOYMENT

        if current.status == "Degraded":
            return ReconcileAction.HEALTH_CHECK

        if desired.autoscaling:
            cpu_usage = desired.autoscaling.get("cpuUsage", 0)
            target_cpu = desired.autoscaling.get("targetCPU", 70)
            if cpu_usage > target_cpu:
                return ReconcileAction.AUTO_SCALE

        return ReconcileAction.NO_ACTION

    def _execute_action(
        self,
        action: ReconcileAction,
        desired: DesiredState,
        current: ClusterState,
    ) -> ReconcileResult:
        """Execute the determined action."""

        if action == ReconcileAction.CREATE_DEPLOYMENT:
            current.replicas = desired.replicas
            current.ready_replicas = 0
            current.version = desired.version
            current.image = desired.image
            current.status = "Deploying"
            self.update_state(current)
            return ReconcileResult(
                action=action,
                message=f"Created deployment {desired.name} with {desired.replicas} replicas",
                changes={"replicas": desired.replicas, "version": desired.version},
                next_reconcile=timedelta(seconds=5),
            )

        elif action == ReconcileAction.ROLLING_UPDATE:
            old_version = current.version
            current.version = desired.version
            current.status = "RollingUpdate"
            self.update_state(current)
            return ReconcileResult(
                action=action,
                message=f"Rolling update {desired.name}: {old_version} -> {desired.version}",
                changes={"from": old_version, "to": desired.version},
                next_reconcile=timedelta(seconds=30),
            )

        elif action == ReconcileAction.SCALE_DEPLOYMENT:
            old_replicas = current.replicas
            current.replicas = desired.replicas
            current.status = "Scaling"
            self.update_state(current)
            return ReconcileResult(
                action=action,
                message=f"Scaled {desired.name}: {old_replicas} -> {desired.replicas}",
                changes={"from": old_replicas, "to": desired.replicas},
                next_reconcile=timedelta(seconds=10),
            )

        elif action == ReconcileAction.CANARY_PROMOTE:
            current.status = "CanaryPromoting"
            self.update_state(current)
            return ReconcileResult(
                action=action,
                message=f"Canary promote {desired.name} to {desired.canary_weight}%",
                changes={"weight": desired.canary_weight},
                next_reconcile=timedelta(seconds=60),
            )

        elif action == ReconcileAction.ROLLBACK:
            current.version = f"{current.version}-rollback"
            current.status = "Rollback"
            self.update_state(current)
            return ReconcileResult(
                action=action,
                message=f"Rolling back {desired.name}",
                changes={"version": current.version},
                next_reconcile=timedelta(seconds=30),
            )

        elif action == ReconcileAction.HEALTH_CHECK:
            current.status = "Running"
            self.update_state(current)
            return ReconcileResult(
                action=action,
                message=f"Health check passed for {desired.name}",
                next_reconcile=timedelta(seconds=60),
            )

        elif action == ReconcileAction.AUTO_SCALE:
            current.replicas = min(current.replicas + 1, 100)
            current.status = "AutoScaling"
            self.update_state(current)
            return ReconcileResult(
                action=action,
                message=f"Auto-scaling {desired.name} to {current.replicas} replicas",
                changes={"replicas": current.replicas},
                next_reconcile=timedelta(seconds=30),
            )

        return ReconcileResult(
            action=action,
            message=f"No action needed for {desired.name}",
            next_reconcile=timedelta(seconds=30),
        )