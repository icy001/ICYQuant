"""
Audit Engine — central recording engine for all governance audit events.

Listens to governance events and records them as immutable AuditEvent records.
Supports both synchronous recording and Event Bus integration.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Callable

from .audit_event import AuditEvent
from .audit_event_type import AuditEventType
from .audit_actor import AuditActor
from .audit_action import AuditAction
from .audit_outcome import AuditOutcome
from .audit_context import AuditContext
from .audit_hash import AuditHash
from .immutable_audit_log import ImmutableAuditLog
from .audit_chain import AuditChain
from .audit_integrity import AuditIntegrityChecker


class AuditEngine:
    """Central audit recording engine for governance.

    Responsibilities:
      1. Record governance events as immutable AuditEvent records
      2. Maintain hash chain integrity
      3. Support correlation_id / causation_id lineage
      4. Integrate with Event Bus for automatic event capture
      5. Isolate audit failures from trading system availability
    """

    def __init__(
        self,
        audit_log: Optional[ImmutableAuditLog] = None,
        chain: Optional[AuditChain] = None,
        fail_closed_for_critical: bool = True,
    ):
        self._log = audit_log or ImmutableAuditLog()
        self._chain = chain or AuditChain()
        self._integrity_checker = AuditIntegrityChecker(self._chain)
        self._fail_closed_critical = fail_closed_for_critical

        # Event bus listeners
        self._listeners: List[Callable[[AuditEvent], None]] = []

        # Metrics
        self._events_recorded: int = 0
        self._events_failed: int = 0
        self._integrity_failures: int = 0

    # ── Core Recording ──

    def record_event(
        self,
        event_type: AuditEventType,
        entity_type: str,
        entity_id: str,
        actor: AuditActor,
        action: AuditAction,
        outcome: AuditOutcome = AuditOutcome.SUCCESS,
        reason: str = "",
        correlation_id: str = "",
        causation_id: str = "",
        context: Optional[AuditContext] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[AuditEvent]:
        """Record a single governance audit event.

        Returns the created AuditEvent or None if recording failed
        (and the event was not critical).
        """
        # Build event
        event = AuditEvent(
            event_id=f"AEVT-{uuid.uuid4().hex[:12].upper()}",
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            action=action,
            outcome=outcome,
            reason=reason,
            correlation_id=correlation_id or f"CORR-{uuid.uuid4().hex[:8].upper()}",
            causation_id=causation_id,
            context=context or AuditContext(
                correlation_id=correlation_id,
                causation_id=causation_id,
            ),
            metadata=metadata or {},
            timestamp=time.time(),
            created_at=time.time(),
        )

        # Compute hash
        event.event_hash = AuditHash.compute_event_hash(event.to_dict())

        # Append to chain for integrity
        previous = self._chain.last_hash
        event.previous_hash = previous
        self._chain.append(event.event_hash, event.event_id, event.timestamp)

        # Record in immutable log
        try:
            self._log.record(event)
            self._events_recorded += 1
        except Exception:
            self._events_failed += 1
            if event.is_critical and self._fail_closed_critical:
                raise RuntimeError(
                    f"Failed to record critical audit event {event.event_id}. "
                    f"Policy requires FAIL CLOSED for critical events."
                )
            return None

        # Notify listeners
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                pass  # Listener failure must not block audit recording

        return event

    def record_batch(
        self,
        events_data: List[Dict[str, Any]],
        correlation_id: str = "",
    ) -> List[Optional[AuditEvent]]:
        """Record multiple events sharing the same correlation_id."""
        results: List[Optional[AuditEvent]] = []
        cid = correlation_id or f"CORR-{uuid.uuid4().hex[:8].upper()}"

        for data in events_data:
            event = self.record_event(
                event_type=data["event_type"],
                entity_type=data["entity_type"],
                entity_id=data["entity_id"],
                actor=data["actor"],
                action=data["action"],
                outcome=data.get("outcome", AuditOutcome.SUCCESS),
                reason=data.get("reason", ""),
                correlation_id=cid,
                causation_id=data.get("causation_id", ""),
                context=data.get("context"),
                metadata=data.get("metadata"),
            )
            results.append(event)

        return results

    # ── Convenience Recording ──

    def record_decision(
        self,
        event_type: AuditEventType,
        decision_id: str,
        actor: AuditActor,
        action: AuditAction,
        outcome: AuditOutcome = AuditOutcome.SUCCESS,
        reason: str = "",
        correlation_id: str = "",
        **kwargs,
    ) -> Optional[AuditEvent]:
        """Record a decision-related audit event."""
        ctx = AuditContext(
            correlation_id=correlation_id,
            decision_id=decision_id,
            **kwargs,
        )
        return self.record_event(
            event_type=event_type,
            entity_type="DECISION",
            entity_id=decision_id,
            actor=actor,
            action=action,
            outcome=outcome,
            reason=reason,
            correlation_id=correlation_id,
            context=ctx,
        )

    def record_policy(
        self,
        event_type: AuditEventType,
        policy_id: str,
        actor: AuditActor,
        action: AuditAction,
        outcome: AuditOutcome = AuditOutcome.SUCCESS,
        reason: str = "",
        policy_version: str = "",
        policy_hash: str = "",
        correlation_id: str = "",
    ) -> Optional[AuditEvent]:
        """Record a policy-related audit event."""
        ctx = AuditContext(
            correlation_id=correlation_id,
            policy_id=policy_id,
            policy_version=policy_version,
            policy_hash=policy_hash,
        )
        return self.record_event(
            event_type=event_type,
            entity_type="POLICY",
            entity_id=policy_id,
            actor=actor,
            action=action,
            outcome=outcome,
            reason=reason,
            correlation_id=correlation_id,
            context=ctx,
        )

    def record_authority(
        self,
        event_type: AuditEventType,
        authority_id: str,
        actor: AuditActor,
        action: AuditAction,
        outcome: AuditOutcome = AuditOutcome.SUCCESS,
        reason: str = "",
        correlation_id: str = "",
        **kwargs,
    ) -> Optional[AuditEvent]:
        """Record an authority-related audit event."""
        ctx = AuditContext(
            correlation_id=correlation_id,
            authority_id=authority_id,
            **kwargs,
        )
        return self.record_event(
            event_type=event_type,
            entity_type="AUTHORITY",
            entity_id=authority_id,
            actor=actor,
            action=action,
            outcome=outcome,
            reason=reason,
            correlation_id=correlation_id,
            context=ctx,
        )

    def record_approval(
        self,
        event_type: AuditEventType,
        approval_id: str,
        actor: AuditActor,
        action: AuditAction,
        outcome: AuditOutcome = AuditOutcome.SUCCESS,
        reason: str = "",
        correlation_id: str = "",
        **kwargs,
    ) -> Optional[AuditEvent]:
        """Record an approval-related audit event."""
        ctx = AuditContext(
            correlation_id=correlation_id,
            approval_id=approval_id,
            **kwargs,
        )
        return self.record_event(
            event_type=event_type,
            entity_type="APPROVAL",
            entity_id=approval_id,
            actor=actor,
            action=action,
            outcome=outcome,
            reason=reason,
            correlation_id=correlation_id,
            context=ctx,
        )

    def record_execution(
        self,
        event_type: AuditEventType,
        execution_id: str,
        actor: AuditActor,
        action: AuditAction,
        outcome: AuditOutcome = AuditOutcome.SUCCESS,
        reason: str = "",
        correlation_id: str = "",
        order_id: str = "",
        trade_id: str = "",
    ) -> Optional[AuditEvent]:
        """Record an execution-related audit event."""
        ctx = AuditContext(
            correlation_id=correlation_id,
            execution_id=execution_id,
            order_id=order_id,
            trade_id=trade_id,
        )
        return self.record_event(
            event_type=event_type,
            entity_type="EXECUTION",
            entity_id=execution_id,
            actor=actor,
            action=action,
            outcome=outcome,
            reason=reason,
            correlation_id=correlation_id,
            context=ctx,
        )

    # ── Query ──

    def get_events_by_correlation(self, correlation_id: str) -> List[AuditEvent]:
        """Retrieve all events sharing a correlation_id."""
        return self._log.query_by_correlation(correlation_id)

    def get_events_by_entity(self, entity_type: str, entity_id: str) -> List[AuditEvent]:
        """Retrieve all events for a specific entity."""
        return self._log.query_by_entity(entity_type, entity_id)

    def get_events_by_type(self, event_type: AuditEventType, limit: int = 100) -> List[AuditEvent]:
        """Retrieve events of a specific type."""
        return self._log.query_by_type(event_type, limit)

    def get_events_in_time_range(
        self, start: float, end: float, limit: int = 1000
    ) -> List[AuditEvent]:
        """Retrieve events within a time range."""
        return self._log.query_time_range(start, end, limit)

    def get_all_events(self, limit: int = 1000) -> List[AuditEvent]:
        """Retrieve all audit events."""
        return self._log.query_all(limit)

    # ── Integrity ──

    def verify_integrity(self) -> Dict[str, Any]:
        """Run a full audit integrity check."""
        result = self._integrity_checker.verify()
        if not result["valid"]:
            self._integrity_failures += 1
            self.record_event(
                event_type=AuditEventType.AUDIT_INTEGRITY_FAILURE,
                entity_type="AUDIT",
                entity_id="INTEGRITY_CHECK",
                actor=AuditActor.system("audit-engine"),
                action=AuditAction.VERIFY_INTEGRITY,
                outcome=AuditOutcome.INTEGRITY_INVALID,
                reason=str(result.get("issues", [])),
            )
        return result

    def verify_chain(self) -> Dict[str, Any]:
        """Verify only the hash chain."""
        return self._chain.verify()

    # ── Event Bus Integration ──

    def add_listener(self, listener: Callable[[AuditEvent], None]) -> None:
        """Add a listener for audit events (e.g., Event Bus publisher)."""
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[AuditEvent], None]) -> None:
        """Remove a listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    # ── Metrics ──

    @property
    def events_recorded(self) -> int:
        return self._events_recorded

    @property
    def events_failed(self) -> int:
        return self._events_failed

    @property
    def integrity_failures(self) -> int:
        return self._integrity_failures

    @property
    def chain_length(self) -> int:
        return self._chain.length

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "events_recorded": self._events_recorded,
            "events_failed": self._events_failed,
            "integrity_failures": self._integrity_failures,
            "chain_length": self._chain.length,
            "log_size": self._log.size,
            "last_event_id": self._chain.last_event_id,
        }
