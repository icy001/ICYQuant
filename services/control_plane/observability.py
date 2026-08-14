"""Observability facade: unified entry point for audit + event + metrics + trace
(Commit 29 Part 1.5 §13-18).

All Control Plane components report through ``ControlPlaneObservability`` so a
single command automatically produces, in one place:

    Audit (who/why/result)  +  Event (what happened)  +  Metrics (system health)  +  Trace (path)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .audit_event import AuditEventType, AuditTrail
from .diagnostics import redact
from .event import InMemoryEventStore
from .metrics import ControlMetrics
from .tracing import ControlTrace


class ControlPlaneObservability:
    """Facade over the four observability channels (§13)."""

    def __init__(
        self,
        *,
        audit: AuditTrail,
        events: InMemoryEventStore,
        metrics: ControlMetrics,
        tracer: ControlTrace,
    ) -> None:
        self.audit = audit
        self.events = events
        self.metrics = metrics
        self.tracer = tracer

    # --- command creation (§14) ---

    def record_command_created(
        self,
        *,
        command_id: str,
        action: str,
        resource: str,
        target: str,
        principal_id: str,
        correlation_id: str,
        idempotency_key: str | None = None,
        fingerprint: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        self.metrics.record_submitted()
        self.audit.record(
            event_type=AuditEventType.COMMAND_CREATED,
            command_id=command_id,
            principal_id=principal_id,
            action=action,
            resource=resource,
            target=target,
            decision="SUBMITTED",
            reason="command_created",
            correlation_id=correlation_id,
            detail=redact(
                {
                    "idempotency_key": idempotency_key,
                    "fingerprint": fingerprint,
                    "parameters": parameters or {},
                }
            ),
        )
        self.events.append(
            event_type=AuditEventType.COMMAND_CREATED,
            command_id=command_id,
            correlation_id=correlation_id,
            payload=redact(
                {
                    "action": action,
                    "resource": resource,
                    "target": target,
                    "principal_id": principal_id,
                    "idempotency_key": idempotency_key,
                    "fingerprint": fingerprint,
                }
            ),
        )
        self.tracer.start_span(
            "control.command",
            {
                "command_id": command_id,
                "command_type": action,
                "target": target,
                "principal_id": principal_id,
                "correlation_id": correlation_id,
            },
        )

    # --- authorization (§15-16) ---

    def record_authorization(
        self,
        *,
        command_id: str,
        action: str,
        resource: str,
        target: str,
        principal_id: str,
        correlation_id: str,
        decision: str,
        reason: str,
        policy: str | None = None,
        grant_id: str | None = None,
    ) -> None:
        event_type = (
            AuditEventType.AUTHORIZATION_GRANTED
            if decision.upper() == "ALLOW"
            else AuditEventType.AUTHORIZATION_REJECTED
        )
        if decision.upper() == "ALLOW":
            self.metrics.record_authorized()
        else:
            self.metrics.record_rejected()
        self.audit.record(
            event_type=event_type,
            command_id=command_id,
            principal_id=principal_id,
            action=action,
            resource=resource,
            target=target,
            decision=decision,
            reason=reason,
            correlation_id=correlation_id,
            detail=redact({"policy": policy, "grant_id": grant_id}),
        )
        self.events.append(
            event_type=event_type,
            command_id=command_id,
            correlation_id=correlation_id,
            payload=redact(
                {
                    "principal": principal_id,
                    "policy": policy,
                    "resource": resource,
                    "action": action,
                    "target": target,
                    "decision": decision,
                    "reason": reason,
                    "grant_id": grant_id,
                }
            ),
        )
        self.tracer.start_span(
            "control.authorization",
            {
                "command_id": command_id,
                "principal_id": principal_id,
                "decision": decision,
            },
        )

    # --- execution (§17) ---

    def record_execution_started(
        self,
        *,
        command_id: str,
        action: str,
        target: str,
        correlation_id: str,
        worker_id: str,
        claim_id: str,
        fencing_token: int | str | None,
        attempt_number: int,
    ) -> None:
        self.metrics.record_executed()
        self.audit.record(
            event_type=AuditEventType.EXECUTION_STARTED,
            command_id=command_id,
            principal_id=worker_id,
            action=action,
            resource="execution",
            target=target,
            decision="STARTED",
            reason="execution_started",
            correlation_id=correlation_id,
            detail=redact(
                {
                    "worker_id": worker_id,
                    "claim_id": claim_id,
                    "fencing_token": fencing_token,
                    "attempt_number": attempt_number,
                }
            ),
        )
        self.events.append(
            event_type=AuditEventType.EXECUTION_STARTED,
            command_id=command_id,
            correlation_id=correlation_id,
            payload=redact(
                {
                    "worker_id": worker_id,
                    "claim_id": claim_id,
                    "fencing_token": fencing_token,
                    "attempt_number": attempt_number,
                }
            ),
        )
        self.tracer.start_span(
            "control.execution",
            {
                "command_id": command_id,
                "target": target,
                "attempt_number": attempt_number,
                "worker_id": worker_id,
                "correlation_id": correlation_id,
            },
        )

    def record_execution_succeeded(
        self,
        *,
        command_id: str,
        action: str,
        target: str,
        correlation_id: str,
        duration_seconds: float,
    ) -> None:
        self.metrics.record_succeeded(duration_seconds)
        self.metrics.record_execution_duration(duration_seconds)
        self.audit.record(
            event_type=AuditEventType.EXECUTION_SUCCEEDED,
            command_id=command_id,
            principal_id="executor",
            action=action,
            resource="execution",
            target=target,
            decision="SUCCEEDED",
            reason="execution_succeeded",
            correlation_id=correlation_id,
            detail={"duration_seconds": duration_seconds},
        )
        self.events.append(
            event_type=AuditEventType.EXECUTION_SUCCEEDED,
            command_id=command_id,
            correlation_id=correlation_id,
            payload={"duration_seconds": duration_seconds},
        )

    def record_execution_failed(
        self,
        *,
        command_id: str,
        action: str,
        target: str,
        correlation_id: str,
        error: str,
    ) -> None:
        self.metrics.record_failed()
        self.audit.record(
            event_type=AuditEventType.EXECUTION_FAILED,
            command_id=command_id,
            principal_id="executor",
            action=action,
            resource="execution",
            target=target,
            decision="FAILED",
            reason=error,
            correlation_id=correlation_id,
        )
        self.events.append(
            event_type=AuditEventType.EXECUTION_FAILED,
            command_id=command_id,
            correlation_id=correlation_id,
            payload={"error": error},
        )

    def record_execution_timeout(
        self,
        *,
        command_id: str,
        action: str,
        target: str,
        correlation_id: str,
        timeout_seconds: int,
    ) -> None:
        self.metrics.record_timeout()
        self.audit.record(
            event_type=AuditEventType.EXECUTION_TIMEOUT,
            command_id=command_id,
            principal_id="executor",
            action=action,
            resource="execution",
            target=target,
            decision="TIMEOUT",
            reason="execution_timeout",
            correlation_id=correlation_id,
            detail={"timeout_seconds": timeout_seconds},
        )
        self.events.append(
            event_type=AuditEventType.EXECUTION_TIMEOUT,
            command_id=command_id,
            correlation_id=correlation_id,
            payload={"timeout_seconds": timeout_seconds},
        )

    # --- recovery (§18) ---

    def record_recovery_started(
        self,
        *,
        command_id: str,
        action: str,
        target: str,
        correlation_id: str,
        causation_id: str | None = None,
    ) -> None:
        self.metrics.record_recovery()
        self.audit.record(
            event_type=AuditEventType.RECOVERY_STARTED,
            command_id=command_id,
            principal_id="system-recovery",
            action=action,
            resource="recovery",
            target=target,
            decision="RECOVERY",
            reason="recovery_started",
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
        self.events.append(
            event_type=AuditEventType.RECOVERY_STARTED,
            command_id=command_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload={"action": action, "target": target},
        )

    def record_target_reconciled(
        self,
        *,
        command_id: str,
        action: str,
        target: str,
        correlation_id: str,
        target_state: str,
    ) -> None:
        self.audit.record(
            event_type=AuditEventType.TARGET_RECONCILED,
            command_id=command_id,
            principal_id="system-recovery",
            action=action,
            resource="reconciliation",
            target=target,
            decision="RECONCILED",
            reason=f"target_state={target_state}",
            correlation_id=correlation_id,
        )
        self.events.append(
            event_type=AuditEventType.TARGET_RECONCILED,
            command_id=command_id,
            correlation_id=correlation_id,
            payload={"target_state": target_state},
        )

    def record_recovery_completed(
        self,
        *,
        command_id: str,
        action: str,
        target: str,
        correlation_id: str,
        succeeded: bool,
    ) -> None:
        if succeeded:
            self.metrics.record_recovery_success()
        else:
            self.metrics.record_recovery_failure()
        self.audit.record(
            event_type=AuditEventType.RECOVERY_COMPLETED,
            command_id=command_id,
            principal_id="system-recovery",
            action=action,
            resource="recovery",
            target=target,
            decision="SUCCEEDED" if succeeded else "FAILED",
            reason="recovery_completed",
            correlation_id=correlation_id,
        )
        self.events.append(
            event_type=AuditEventType.RECOVERY_COMPLETED,
            command_id=command_id,
            correlation_id=correlation_id,
            payload={"succeeded": succeeded},
        )

    # --- terminal states ---

    def record_command_succeeded(
        self,
        *,
        command_id: str,
        action: str,
        target: str,
        correlation_id: str,
    ) -> None:
        self.metrics.record_succeeded()
        self.audit.record(
            event_type=AuditEventType.COMMAND_SUCCEEDED,
            command_id=command_id,
            principal_id="control-plane",
            action=action,
            resource="command",
            target=target,
            decision="SUCCEEDED",
            reason="command_succeeded",
            correlation_id=correlation_id,
        )
        self.events.append(
            event_type=AuditEventType.COMMAND_SUCCEEDED,
            command_id=command_id,
            correlation_id=correlation_id,
        )

    def record_command_failed(
        self,
        *,
        command_id: str,
        action: str,
        target: str,
        correlation_id: str,
        error: str,
    ) -> None:
        self.metrics.record_failed()
        self.audit.record(
            event_type=AuditEventType.COMMAND_FAILED,
            command_id=command_id,
            principal_id="control-plane",
            action=action,
            resource="command",
            target=target,
            decision="FAILED",
            reason=error,
            correlation_id=correlation_id,
        )
        self.events.append(
            event_type=AuditEventType.COMMAND_FAILED,
            command_id=command_id,
            correlation_id=correlation_id,
            payload={"error": error},
        )

    # --- idempotency / replay safety (§19, §25) ---

    def record_duplicate(
        self,
        *,
        command_id: str,
        correlation_id: str,
        action: str,
        target: str,
    ) -> None:
        self.metrics.record_duplicate()
        self.audit.record(
            event_type=AuditEventType.DUPLICATE_COMMAND,
            command_id=command_id,
            principal_id="system",
            action=action,
            resource="idempotency",
            target=target,
            decision="DUPLICATE",
            reason="duplicate_submission",
            correlation_id=correlation_id,
        )
        self.events.append(
            event_type=AuditEventType.DUPLICATE_COMMAND,
            command_id=command_id,
            correlation_id=correlation_id,
        )

    def record_idempotency_conflict(
        self,
        *,
        command_id: str,
        correlation_id: str,
        action: str,
        target: str,
    ) -> None:
        self.metrics.record_idempotency_conflict()
        self.audit.record(
            event_type=AuditEventType.IDEMPOTENCY_CONFLICT,
            command_id=command_id,
            principal_id="system",
            action=action,
            resource="idempotency",
            target=target,
            decision="CONFLICT",
            reason="idempotency_key_reused",
            correlation_id=correlation_id,
        )
        self.events.append(
            event_type=AuditEventType.IDEMPOTENCY_CONFLICT,
            command_id=command_id,
            correlation_id=correlation_id,
        )

    def record_replay_rejection(
        self,
        *,
        command_id: str,
        correlation_id: str,
        action: str,
        target: str,
    ) -> None:
        self.metrics.record_replay_rejection()
        self.audit.record(
            event_type=AuditEventType.REPLAY_REJECTED,
            command_id=command_id,
            principal_id="system",
            action=action,
            resource="replay",
            target=target,
            decision="REJECTED",
            reason="replay_outside_window",
            correlation_id=correlation_id,
        )
        self.events.append(
            event_type=AuditEventType.REPLAY_REJECTED,
            command_id=command_id,
            correlation_id=correlation_id,
        )

    def record_claim_conflict(
        self,
        *,
        command_id: str,
        correlation_id: str,
        action: str,
        target: str,
    ) -> None:
        self.metrics.record_claim_conflict()
        self.events.append(
            event_type=AuditEventType.EXECUTION_CLAIMED,
            command_id=command_id,
            correlation_id=correlation_id,
            payload={"conflict": True},
        )

    def record_version_conflict(
        self,
        *,
        command_id: str,
        correlation_id: str,
        action: str,
        target: str,
    ) -> None:
        self.metrics.record_version_conflict()
        self.events.append(
            event_type=AuditEventType.IDEMPOTENCY_CONFLICT,
            command_id=command_id,
            correlation_id=correlation_id,
            payload={"version_conflict": True},
        )
