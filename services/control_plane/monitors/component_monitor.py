"""
ComponentMonitor — composes every health signal for one component.

The monitor is the *observation* layer. It:

    * records heartbeats (idempotent by component + instance + sequence)
    * judges heartbeat timeouts (HeartbeatMonitor)
    * evaluates readiness (dependencies / freshness / consumer lag)
    * evaluates health (HealthEvaluator → status + score)
    * applies failure hysteresis (N misses → UNHEALTHY)
    * applies recovery hysteresis (N healthy evaluations → HEALTHY)
    * maintains the HealthIncident lifecycle
    * emits HEALTH_STATUS_CHANGED / HEARTBEAT_MISSED / COMPONENT_UNRESPONSIVE

It does NOT restart, halt trading, or start recovery. Those decisions belong
to the Control Plane / Policy Engine:

    HeartbeatMonitor → Health Event → Control Plane → Policy Engine → Trading Gate
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from ..events.component_unresponsive import ComponentUnresponsive
from ..events.health_status_changed import HealthStatusChanged
from ..events.heartbeat_missed import HeartbeatMissed
from ..health.health_check import HealthCheck
from ..health.health_evaluator import HealthEvaluation, HealthEvaluator
from ..health.health_incident import (
    HealthIncident,
    HealthIncidentState,
    incident_severity_for_criticality,
)
from ..health.health_profile import HealthProfile
from ..health.health_status import HealthStatus
from ..health.heartbeat import Heartbeat, utcnow
from ..health.liveness import LivenessStatus
from ..health.readiness import (
    DataFreshness,
    DependencyStatus,
    evaluate_readiness,
)
from .heartbeat_monitor import HeartbeatDecision, HeartbeatMonitor


def _default_profile(component_id: str) -> HealthProfile:
    return HealthProfile(component_id=component_id)


@dataclass
class ComponentMonitor:
    """Per-component health monitor with hysteresis and incident tracking."""

    heartbeat_monitor: HeartbeatMonitor = field(default_factory=HeartbeatMonitor)
    health_evaluator: HealthEvaluator = field(default_factory=HealthEvaluator)
    profiles: Dict[str, HealthProfile] = field(default_factory=dict)
    failure_threshold: int = 3
    recovery_confirmation_count: int = 3
    on_event: Optional[Callable[[Any], None]] = None

    # -- internal state ------------------------------------------------- #
    _seen_sequences: Dict[Tuple[str, str], int] = field(default_factory=dict)
    _last_heartbeats: Dict[Tuple[str, str], Heartbeat] = field(default_factory=dict)
    _started_at: Dict[str, datetime] = field(default_factory=dict)
    _last_updates: Dict[str, datetime] = field(default_factory=dict)
    _miss_counts: Dict[str, int] = field(default_factory=dict)
    _success_counts: Dict[str, int] = field(default_factory=dict)
    _statuses: Dict[str, HealthStatus] = field(default_factory=dict)
    _incidents: Dict[str, HealthIncident] = field(default_factory=dict)
    _incident_seq: int = 0
    _events: List[Any] = field(default_factory=list)

    # -- configuration -------------------------------------------------- #

    def register_profile(self, profile: HealthProfile) -> "ComponentMonitor":
        self.profiles[profile.component_id] = profile
        return self

    def profile(self, component_id: str) -> HealthProfile:
        return self.profiles.get(component_id) or _default_profile(component_id)

    def mark_started(self, component_id: str, at: Optional[datetime] = None) -> None:
        """Record when a component (re)started; feeds the startup grace period."""
        self._started_at[component_id] = at or utcnow()

    def record_data_update(self, component_id: str, at: Optional[datetime] = None) -> None:
        """Record when a component last updated its data (freshness input)."""
        self._last_updates[component_id] = at or utcnow()

    # -- heartbeat ingestion -------------------------------------------- #

    def record_heartbeat(self, heartbeat: Heartbeat) -> bool:
        """Store a heartbeat. Idempotent: duplicates / out-of-order sequences
        return False and never advance state."""
        key = (heartbeat.component_id, heartbeat.instance_id)
        last_seq = self._seen_sequences.get(key)
        if last_seq is not None and heartbeat.sequence <= last_seq:
            return False
        self._seen_sequences[key] = heartbeat.sequence
        self._last_heartbeats[key] = heartbeat
        self._miss_counts[heartbeat.component_id] = 0
        return True

    def last_heartbeat(self, component_id: str) -> Optional[Heartbeat]:
        """Most recent heartbeat across all instances of a component."""
        best: Optional[Heartbeat] = None
        for (cid, _instance), hb in self._last_heartbeats.items():
            if cid == component_id and (best is None or hb.sequence > best.sequence):
                best = hb
        return best

    # -- queries --------------------------------------------------------- #

    def health_status(self, component_id: str) -> HealthStatus:
        return self._statuses.get(component_id, HealthStatus.UNKNOWN)

    def miss_count(self, component_id: str) -> int:
        return self._miss_counts.get(component_id, 0)

    def success_count(self, component_id: str) -> int:
        return self._success_counts.get(component_id, 0)

    def incident(self, component_id: str) -> Optional[HealthIncident]:
        return self._incidents.get(component_id)

    @property
    def events(self) -> List[Any]:
        return list(self._events)

    # -- evaluation ------------------------------------------------------- #

    def evaluate(
        self,
        component_id: str,
        now: Optional[datetime] = None,
        started_at: Optional[datetime] = None,
        liveness: Optional[LivenessStatus] = None,
        dependencies: Optional[Sequence[DependencyStatus]] = None,
        freshness: Optional[DataFreshness] = None,
        consumer_lag: Optional[int] = None,
        checks: Optional[Sequence[HealthCheck]] = None,
    ) -> HealthEvaluation:
        """Run one full evaluation cycle for a component."""
        now = now or utcnow()
        profile = self.profile(component_id)
        started_at = started_at if started_at is not None else self._started_at.get(
            component_id
        )

        heartbeat = self.last_heartbeat(component_id)
        miss_count = self._miss_counts.get(component_id, 0)
        decision = self.heartbeat_monitor.evaluate(
            heartbeat, now=now, started_at=started_at, miss_count=miss_count
        )
        if not decision.component_id:
            decision.component_id = component_id
            decision.instance_id = heartbeat.instance_id if heartbeat else ""

        missed_this_tick = decision.missed
        if missed_this_tick:
            miss_count += 1
        else:
            miss_count = 0
        self._miss_counts[component_id] = miss_count

        # Liveness (from heartbeat unless an external probe result is given).
        if liveness is None:
            if heartbeat is None:
                liveness = (
                    LivenessStatus.DEAD
                    if decision.decision is HeartbeatDecision.UNHEALTHY
                    else LivenessStatus.UNKNOWN
                )
            else:
                liveness = LivenessStatus.ALIVE

        # Freshness (explicit value wins; otherwise from recorded data update).
        if freshness is None and profile.freshness_policy is not None:
            freshness = profile.freshness_policy.evaluate(
                self._last_updates.get(component_id), now=now
            )

        if dependencies is None:
            dependencies = [
                DependencyStatus(dep, HealthStatus.UNKNOWN, "not provided")
                for dep in profile.required_dependencies
            ]

        readiness_eval = evaluate_readiness(
            component_id,
            dependencies=list(dependencies),
            freshness=freshness or DataFreshness.UNKNOWN,
            consumer_lag=consumer_lag,
            consumer_lag_warning=profile.consumer_lag_warning,
            consumer_lag_critical=profile.consumer_lag_critical,
            now=now,
        )

        evaluation = self.health_evaluator.evaluate(
            component_id,
            liveness=liveness,
            readiness=readiness_eval.status,
            heartbeat=heartbeat,
            heartbeat_age=decision.elapsed if heartbeat else None,
            dependencies=list(dependencies),
            checks=list(checks or []),
            warning_timeout=self.heartbeat_monitor.warning_timeout,
            critical_timeout=self.heartbeat_monitor.critical_timeout,
            criticality=profile.criticality,
            now=now,
        )

        # Carry the granular readiness reasons (DATA_STALE, CONSUMER_LAG_*,
        # DEPENDENCY_*) into the health evaluation for observability.
        for reason in readiness_eval.reasons:
            if reason not in evaluation.reasons:
                evaluation.reasons.append(reason)

        previous = self._statuses.get(component_id, HealthStatus.UNKNOWN)
        desired = evaluation.status

        # Failure hysteresis: sustained misses force UNHEALTHY.
        if (
            miss_count >= self.failure_threshold
            and desired is not HealthStatus.UNHEALTHY
        ):
            desired = HealthStatus.UNHEALTHY
            evaluation.status = desired
            if "FAILURE_HYSTERESIS" not in evaluation.reasons:
                evaluation.reasons.append("FAILURE_HYSTERESIS")

        # Recovery hysteresis: N consecutive healthy evaluations to recover.
        if desired is HealthStatus.HEALTHY:
            successes = self._success_counts.get(component_id, 0) + 1
            self._success_counts[component_id] = successes
            if (
                previous in (HealthStatus.DEGRADED, HealthStatus.UNHEALTHY)
                and successes < self.recovery_confirmation_count
            ):
                desired = previous
                evaluation.status = desired
        else:
            self._success_counts[component_id] = 0

        self._statuses[component_id] = desired

        # -- events ------------------------------------------------------ #
        new_events: List[Any] = []

        if decision.missed:
            new_events.append(
                HeartbeatMissed(
                    component_id=component_id,
                    instance_id=decision.instance_id,
                    last_sequence=decision.last_sequence,
                    last_seen=decision.last_seen,
                    detected_at=now,
                    miss_count=miss_count,
                    reason=decision.reason,
                )
            )

        if miss_count == self.failure_threshold:
            new_events.append(
                ComponentUnresponsive(
                    component_id=component_id,
                    instance_id=decision.instance_id,
                    previous_health=previous,
                    current_health=desired,
                    reason=decision.reason,
                    detected_at=now,
                )
            )

        if desired != previous:
            new_events.append(
                HealthStatusChanged(
                    component_id=component_id,
                    previous_status=previous,
                    current_status=desired,
                    reason="; ".join(evaluation.reasons) or decision.reason,
                    health_score=evaluation.score,
                    detected_at=now,
                )
            )

        self._manage_incident(
            component_id=component_id,
            desired=desired,
            missed_this_tick=missed_this_tick,
            miss_count=miss_count,
            now=now,
            reason=decision.reason,
        )

        for event in new_events:
            self._emit(event)

        return evaluation

    # -- incidents -------------------------------------------------------- #

    def open_incident(
        self,
        component_id: str,
        reason: str = "UNKNOWN",
        now: Optional[datetime] = None,
    ) -> HealthIncident:
        now = now or utcnow()
        existing = self._incidents.get(component_id)
        if existing is not None and not existing.state.is_terminal:
            return existing
        self._incident_seq += 1
        incident = HealthIncident(
            incident_id=f"INC-{self._incident_seq:05d}",
            component_id=component_id,
            severity=incident_severity_for_criticality(
                self.profile(component_id).criticality
            ),
            reason=reason,
            state=HealthIncidentState.DETECTED,
            started_at=now,
            current_status=self.health_status(component_id),
        )
        incident.transition(HealthIncidentState.OPEN, now)
        self._incidents[component_id] = incident
        return incident

    def resolve_incident(
        self,
        component_id: str,
        now: Optional[datetime] = None,
    ) -> Optional[HealthIncident]:
        incident = self._incidents.get(component_id)
        if incident is None or incident.state.is_terminal:
            return incident
        now = now or utcnow()
        incident.transition(HealthIncidentState.RESOLVED, now)
        incident.current_status = HealthStatus.HEALTHY
        return incident

    def escalate_incident(
        self,
        component_id: str,
        now: Optional[datetime] = None,
    ) -> Optional[HealthIncident]:
        incident = self._incidents.get(component_id)
        if incident is None or incident.state.is_terminal:
            return incident
        now = now or utcnow()
        incident.transition(HealthIncidentState.ESCALATED, now)
        return incident

    # -- internals -------------------------------------------------------- #

    def _manage_incident(
        self,
        component_id: str,
        desired: HealthStatus,
        missed_this_tick: bool,
        miss_count: int,
        now: datetime,
        reason: str,
    ) -> None:
        incident = self._incidents.get(component_id)

        if desired in (HealthStatus.DEGRADED, HealthStatus.UNHEALTHY):
            if incident is None or incident.state.is_terminal:
                self.open_incident(component_id, reason=reason, now=now)
                incident = self._incidents[component_id]
            incident.current_status = desired
            if miss_count >= self.failure_threshold:
                if incident.state is not HealthIncidentState.ESCALATED:
                    incident.transition(HealthIncidentState.ESCALATED, now)
            elif not missed_this_tick and incident.state in (
                HealthIncidentState.OPEN,
                HealthIncidentState.INVESTIGATING,
            ):
                incident.transition(HealthIncidentState.RECOVERING, now)
            elif (
                desired is HealthStatus.UNHEALTHY
                and incident.state is HealthIncidentState.OPEN
            ):
                incident.transition(HealthIncidentState.INVESTIGATING, now)
        elif desired is HealthStatus.HEALTHY:
            if (
                incident is not None
                and not incident.state.is_terminal
                and incident.state is not HealthIncidentState.ESCALATED
            ):
                incident.transition(HealthIncidentState.RESOLVED, now)
                incident.current_status = HealthStatus.HEALTHY

    def _emit(self, event: Any) -> None:
        self._events.append(event)
        if self.on_event is not None:
            self.on_event(event)
