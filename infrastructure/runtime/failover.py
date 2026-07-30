"""
ICYQuant Cloud Native Runtime - Failover Manager

Provides automated failover capabilities with support for:
- Automatic detection of service failures
- Traffic redirection to healthy instances
- Graceful degradation
- Multi-region failover
- Manual failover triggers
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


class FailoverState(str, Enum):
    NORMAL = "NORMAL"
    DEGRADED = "DEGRADED"
    FAILOVER_INITIATED = "FAILOVER_INITIATED"
    FAILOVER_IN_PROGRESS = "FAILOVER_IN_PROGRESS"
    FAILOVER_COMPLETED = "FAILOVER_COMPLETED"
    RESTORED = "RESTORED"
    ROLLBACK = "ROLLBACK"


class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


@dataclass
class ServiceHealth:
    service_id: str
    cluster: str
    status: HealthStatus
    response_time_ms: float = 0.0
    error_rate: float = 0.0
    active_connections: int = 0
    last_check: datetime = field(default_factory=datetime.now)
    message: str = ""

    def to_dict(self) -> Dict:
        return {
            "serviceId": self.service_id,
            "cluster": self.cluster,
            "status": self.status.value,
            "responseTimeMs": self.response_time_ms,
            "errorRate": self.error_rate,
            "activeConnections": self.active_connections,
            "lastCheck": self.last_check.isoformat(),
            "message": self.message,
        }


@dataclass
class FailoverTarget:
    service_id: str
    cluster: str
    priority: int = 1
    weight: int = 100
    active: bool = False

    def to_dict(self) -> Dict:
        return {
            "serviceId": self.service_id,
            "cluster": self.cluster,
            "priority": self.priority,
            "weight": self.weight,
            "active": self.active,
        }


@dataclass
class FailoverEvent:
    id: str
    service: str
    from_cluster: str
    to_cluster: str
    state: FailoverState
    reason: str
    triggered_by: str = "automatic"
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "service": self.service,
            "fromCluster": self.from_cluster,
            "toCluster": self.to_cluster,
            "state": self.state.value,
            "reason": self.reason,
            "triggeredBy": self.triggered_by,
            "timestamp": self.timestamp.isoformat(),
        }


class FailoverManager:
    """
    Failover management for ICYQuant platform.

    Provides:
    - Automated health-based failover
    - Multi-target failover with priority
    - Graceful degradation support
    - Failover event tracking
    - Rollback capability
    """

    def __init__(self):
        self._health: Dict[str, Dict[str, ServiceHealth]] = {}
        self._targets: Dict[str, List[FailoverTarget]] = {}
        self._states: Dict[str, FailoverState] = {}
        self._events: List[FailoverEvent] = []
        self._max_events = 500
        self._failover_threshold = 3
        self._check_interval_seconds = 10
        self._state_changed_callbacks: List = []

    def register_service(
        self,
        service_id: str,
        targets: List[FailoverTarget],
    ):
        if service_id not in self._targets:
            self._targets[service_id] = targets
        else:
            self._targets[service_id].extend(targets)

        if service_id not in self._health:
            self._health[service_id] = {}
        for target in targets:
            key = f"{service_id}:{target.cluster}"
            if key not in self._health[service_id]:
                self._health[service_id][key] = ServiceHealth(
                    service_id=service_id,
                    cluster=target.cluster,
                    status=HealthStatus.UNKNOWN,
                )

        self._states[service_id] = FailoverState.NORMAL

    def update_health(
        self,
        service_id: str,
        cluster: str,
        status: HealthStatus,
        response_time_ms: float = 0.0,
        error_rate: float = 0.0,
        active_connections: int = 0,
    ) -> ServiceHealth:
        if service_id not in self._health:
            self._health[service_id] = {}

        key = f"{service_id}:{cluster}"
        health = ServiceHealth(
            service_id=service_id,
            cluster=cluster,
            status=status,
            response_time_ms=response_time_ms,
            error_rate=error_rate,
            active_connections=active_connections,
        )
        self._health[service_id][key] = health
        self._evaluate_service(service_id)
        return health

    def trigger_failover(
        self,
        service_id: str,
        target_cluster: Optional[str] = None,
        reason: str = "manual",
        triggered_by: str = "operator",
    ) -> Optional[FailoverEvent]:
        if service_id not in self._targets:
            return None

        targets = self._targets[service_id]
        if not target_cluster:
            healthy_targets = [
                t for t in targets
                if self._get_health(service_id, t.cluster).status == HealthStatus.HEALTHY
            ]
            if healthy_targets:
                healthy_targets.sort(key=lambda t: t.priority)
                target_cluster = healthy_targets[0].cluster
            elif targets:
                target_cluster = targets[0].cluster
            else:
                return None

        current_active = next(
            (t for t in targets if t.active),
            None,
        )
        from_cluster = current_active.cluster if current_active else "unknown"

        for target in targets:
            target.active = (target.cluster == target_cluster)

        event = FailoverEvent(
            id=str(uuid.uuid4())[:12],
            service=service_id,
            from_cluster=from_cluster,
            to_cluster=target_cluster,
            state=FailoverState.FAILOVER_COMPLETED,
            reason=reason,
            triggered_by=triggered_by,
        )
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]

        self._states[service_id] = FailoverState.FAILOVER_COMPLETED
        self._notify_state_change(service_id)
        return event

    def rollback(
        self,
        service_id: str,
    ) -> Optional[FailoverEvent]:
        if service_id not in self._targets:
            return None
        self._states[service_id] = FailoverState.ROLLBACK
        self._notify_state_change(service_id)
        return FailoverEvent(
            id=str(uuid.uuid4())[:12],
            service=service_id,
            from_cluster="",
            to_cluster="",
            state=FailoverState.ROLLBACK,
            reason="Manual rollback",
        )

    def get_service_status(self, service_id: str) -> Dict:
        health_statuses = []
        for cluster_health in self._health.get(service_id, {}).values():
            health_statuses.append(cluster_health.to_dict())

        active_target = None
        for target in self._targets.get(service_id, []):
            if target.active:
                active_target = target.to_dict()
                break

        return {
            "serviceId": service_id,
            "state": self._states.get(service_id, FailoverState.NORMAL).value,
            "health": health_statuses,
            "activeTarget": active_target,
            "targets": [t.to_dict() for t in self._targets.get(service_id, [])],
        }

    def get_status(self) -> Dict:
        return {
            "services": list(self._targets.keys()),
            "states": {
                svc: state.value
                for svc, state in self._states.items()
            },
            "recentEvents": [e.to_dict() for e in self._events[-10:]],
        }

    def on_state_change(self, callback):
        self._state_changed_callbacks.append(callback)

    def _evaluate_service(self, service_id: str):
        if service_id not in self._health or service_id not in self._targets:
            return

        clusters = self._health[service_id]
        unhealthy_count = sum(
            1 for h in clusters.values()
            if h.status == HealthStatus.UNHEALTHY
        )
        total = len(clusters)

        targets = self._targets.get(service_id, [])
        active_target = next((t for t in targets if t.active), None)

        should_failover = False

        if unhealthy_count >= self._failover_threshold:
            should_failover = True
        elif active_target and self._get_health(service_id, active_target.cluster).status == HealthStatus.UNHEALTHY:
            should_failover = True

        if should_failover:
            current_state = self._states.get(service_id, FailoverState.NORMAL)
            if current_state in (FailoverState.NORMAL, FailoverState.DEGRADED):
                self._states[service_id] = FailoverState.DEGRADED
                self._notify_state_change(service_id)

                healthy_targets = [
                    t for t in targets
                    if self._get_health(service_id, t.cluster).status == HealthStatus.HEALTHY
                ]
                if healthy_targets:
                    healthy_targets.sort(key=lambda t: t.priority)
                    self.trigger_failover(
                        service_id,
                        target_cluster=healthy_targets[0].cluster,
                        reason=f"Automatic: {unhealthy_count}/{total} clusters unhealthy",
                    )
        elif unhealthy_count > 0:
            current_state = self._states.get(service_id, FailoverState.NORMAL)
            if current_state == FailoverState.NORMAL:
                self._states[service_id] = FailoverState.DEGRADED
                self._notify_state_change(service_id)

    def _get_health(self, service_id: str, cluster: str) -> ServiceHealth:
        key = f"{service_id}:{cluster}"
        if key in self._health.get(service_id, {}):
            return self._health[service_id][key]
        return ServiceHealth(service_id=service_id, cluster=cluster)

    def _notify_state_change(self, service_id: str):
        for callback in self._state_changed_callbacks:
            try:
                callback(service_id, self._states.get(service_id, FailoverState.NORMAL))
            except Exception as e:
                logger.error(f"State change callback error: {e}")