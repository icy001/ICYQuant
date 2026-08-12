"""Tests for executors, the registry and the mitigation engine
(spec section 11/13/14/16).
"""
from __future__ import annotations

import pytest

from services.control_plane.incident.audit.event_type import IncidentAuditEventType
from services.control_plane.incident.audit.recorder import IncidentAuditRecorder
from services.control_plane.incident.audit.repository import (
    InMemoryIncidentAuditRepository,
)
from services.control_plane.incident.audit.service import IncidentAuditService
from services.control_plane.incident.incident_severity import IncidentSeverity
from services.control_plane.incident.mitigation.action import MitigationAction
from services.control_plane.incident.mitigation.action_type import (
    MitigationActionType,
)
from services.control_plane.incident.mitigation.executor import (
    MitigationEngine,
    MitigationExecutor,
    MitigationExecutorRegistry,
)
from services.control_plane.incident.mitigation.plan import MitigationPlan
from services.control_plane.incident.mitigation.result import MitigationResult


class RecordingExecutor(MitigationExecutor):
    """Executor that records the actions it was handed."""

    def __init__(self, success=True, message="ok", external_reference=None):
        self.calls = 0
        self.actions = []
        self.success = success
        self.message = message
        self.external_reference = external_reference

    def execute(self, action):
        self.calls += 1
        self.actions.append(action)
        return MitigationResult(
            action_id=action.action_id,
            success=self.success,
            message=self.message,
            external_reference=self.external_reference,
        )


def _audit_service() -> IncidentAuditService:
    return IncidentAuditService(
        IncidentAuditRecorder(InMemoryIncidentAuditRepository())
    )


def test_executor_is_abstract():
    with pytest.raises(TypeError):
        MitigationExecutor()  # type: ignore[abstract]


def test_registry_register_and_get():
    registry = MitigationExecutorRegistry()
    executor = RecordingExecutor()

    registry.register(MitigationActionType.CANCEL_OPEN_ORDERS, executor)

    assert registry.get(MitigationActionType.CANCEL_OPEN_ORDERS) is executor
    assert MitigationActionType.CANCEL_OPEN_ORDERS in registry
    assert len(registry) == 1


def test_registry_missing_executor_raises_key_error():
    registry = MitigationExecutorRegistry()

    with pytest.raises(KeyError):
        registry.get(MitigationActionType.CANCEL_OPEN_ORDERS)


def test_engine_executes_plan_in_order():
    registry = MitigationExecutorRegistry()
    cancel = RecordingExecutor()
    block = RecordingExecutor()
    registry.register(MitigationActionType.CANCEL_OPEN_ORDERS, cancel)
    registry.register(MitigationActionType.BLOCK_NEW_ORDERS, block)

    engine = MitigationEngine(registry)
    plan = MitigationPlan(incident_id="INC-1")
    plan.add(
        MitigationAction(
            incident_id="INC-1",
            action_type=MitigationActionType.CANCEL_OPEN_ORDERS,
        )
    )
    plan.add(
        MitigationAction(
            incident_id="INC-1",
            action_type=MitigationActionType.BLOCK_NEW_ORDERS,
        )
    )

    results = engine.execute(plan)

    assert len(results) == 2
    assert cancel.calls == 1
    assert block.calls == 1
    assert all(r.success for r in results)


def test_cancel_orders_is_idempotent():
    """Key test: retrying the same control action must not re-execute it."""
    registry = MitigationExecutorRegistry()
    cancel = RecordingExecutor(message="cancelled")
    registry.register(MitigationActionType.CANCEL_OPEN_ORDERS, cancel)

    engine = MitigationEngine(registry)
    plan = MitigationPlan(incident_id="INC-1")
    plan.add(
        MitigationAction(
            incident_id="INC-1",
            action_type=MitigationActionType.CANCEL_OPEN_ORDERS,
        )
    )

    first = engine.execute(plan)
    second = engine.execute(plan)  # retry / duplicate delivery

    assert cancel.calls == 1
    assert len(second) == 1
    assert second[0].message == "cancelled"
    assert first[0].action_id == second[0].action_id


def test_failed_mitigation_stops_fail_fast_plan():
    """Key test: a failed action halts a fail-fast plan."""
    registry = MitigationExecutorRegistry()
    failing = RecordingExecutor(success=False, message="execution failed")
    block = RecordingExecutor()
    registry.register(MitigationActionType.CANCEL_OPEN_ORDERS, failing)
    registry.register(MitigationActionType.BLOCK_NEW_ORDERS, block)

    engine = MitigationEngine(registry)
    plan = MitigationPlan(incident_id="INC-1", fail_fast=True)
    plan.add(
        MitigationAction(
            incident_id="INC-1",
            action_type=MitigationActionType.CANCEL_OPEN_ORDERS,
        )
    )
    plan.add(
        MitigationAction(
            incident_id="INC-1",
            action_type=MitigationActionType.BLOCK_NEW_ORDERS,
        )
    )

    results = engine.execute(plan)

    assert len(results) == 1
    assert results[0].success is False
    assert block.calls == 0


def test_best_effort_plan_continues_after_failure():
    registry = MitigationExecutorRegistry()
    failing = RecordingExecutor(success=False, message="execution failed")
    block = RecordingExecutor()
    registry.register(MitigationActionType.CANCEL_OPEN_ORDERS, failing)
    registry.register(MitigationActionType.BLOCK_NEW_ORDERS, block)

    engine = MitigationEngine(registry)
    plan = MitigationPlan(incident_id="INC-1", fail_fast=False)
    plan.add(
        MitigationAction(
            incident_id="INC-1",
            action_type=MitigationActionType.CANCEL_OPEN_ORDERS,
        )
    )
    plan.add(
        MitigationAction(
            incident_id="INC-1",
            action_type=MitigationActionType.BLOCK_NEW_ORDERS,
        )
    )

    results = engine.execute(plan)

    assert len(results) == 2
    assert block.calls == 1


def test_engine_records_audit_events():
    audit = _audit_service()
    registry = MitigationExecutorRegistry()
    cancel = RecordingExecutor(external_reference="oms:cancel-batch-1")
    registry.register(MitigationActionType.CANCEL_OPEN_ORDERS, cancel)

    engine = MitigationEngine(registry, audit_service=audit)
    plan = MitigationPlan(incident_id="INC-1")
    plan.add(
        MitigationAction(
            incident_id="INC-1",
            action_type=MitigationActionType.CANCEL_OPEN_ORDERS,
        )
    )

    engine.execute(plan, actor="risk-engine")

    types = [e.event_type for e in audit.timeline("INC-1")]
    assert IncidentAuditEventType.MITIGATION_STARTED in types
    assert IncidentAuditEventType.MITIGATION_COMPLETED in types
    assert IncidentAuditEventType.MITIGATION_FAILED not in types


def test_engine_records_failure_audit_event():
    audit = _audit_service()
    registry = MitigationExecutorRegistry()
    failing = RecordingExecutor(success=False, message="execution failed")
    registry.register(MitigationActionType.CANCEL_OPEN_ORDERS, failing)

    engine = MitigationEngine(registry, audit_service=audit)
    plan = MitigationPlan(incident_id="INC-1")
    plan.add(
        MitigationAction(
            incident_id="INC-1",
            action_type=MitigationActionType.CANCEL_OPEN_ORDERS,
        )
    )

    engine.execute(plan)

    types = [e.event_type for e in audit.timeline("INC-1")]
    assert IncidentAuditEventType.MITIGATION_STARTED in types
    assert IncidentAuditEventType.MITIGATION_FAILED in types


def test_incident_cannot_modify_position_directly(incident_factory):
    """Key test: the incident system never mutates Position directly.

    Position changes flow exclusively through an executor adapter that talks to
    the real business ledger; the incident object has no position surface.
    """
    incident = incident_factory(severity=IncidentSeverity.CRITICAL)
    assert not hasattr(incident, "position")
    assert not hasattr(incident, "set_position")

    calls = []

    class PositionLedgerAdapter(MitigationExecutor):
        def execute(self, action):
            calls.append(action.action_type)
            return MitigationResult(
                action_id=action.action_id,
                success=True,
                external_reference="ledger:tx-1",
            )

    registry = MitigationExecutorRegistry()
    registry.register(MitigationActionType.FLATTEN_POSITION, PositionLedgerAdapter())
    engine = MitigationEngine(registry)

    plan = MitigationPlan(incident_id=incident.id)
    plan.add(
        MitigationAction(
            incident_id=incident.id,
            action_type=MitigationActionType.FLATTEN_POSITION,
            requested_by="operator-1",
        )
    )

    results = engine.execute(plan)

    assert calls == [MitigationActionType.FLATTEN_POSITION]
    assert results[0].success
    assert results[0].external_reference == "ledger:tx-1"
    # The incident object itself was never touched.
    assert not hasattr(incident, "position")


def test_kill_switch_is_executed_through_control_gate(incident_factory):
    """Key test: KILL_SWITCH goes through a registered executor, not a flag.

    The incident system must not set ``kill_switch = True`` on a database row;
    it dispatches a KILL_SWITCH control action through the executor adapter,
    which is the only component allowed to engage the control gate.
    """
    incident = incident_factory(severity=IncidentSeverity.CRITICAL)
    assert not hasattr(incident, "kill_switch")

    class KillSwitchGate:
        def __init__(self):
            self.engaged = False
            self.reason = None
            self.actor = None

        def engage(self, *, reason="", actor="system"):
            self.engaged = True
            self.reason = reason
            self.actor = actor

    gate = KillSwitchGate()

    class KillSwitchExecutor(MitigationExecutor):
        def execute(self, action):
            gate.engage(
                reason=f"incident:{action.incident_id}",
                actor=action.requested_by,
            )
            return MitigationResult(
                action_id=action.action_id,
                success=True,
                external_reference="gate:ks-1",
            )

    registry = MitigationExecutorRegistry()
    registry.register(MitigationActionType.KILL_SWITCH, KillSwitchExecutor())
    engine = MitigationEngine(registry)

    plan = MitigationPlan(incident_id=incident.id)
    plan.add(
        MitigationAction(
            incident_id=incident.id,
            action_type=MitigationActionType.KILL_SWITCH,
            requested_by="risk-engine",
        )
    )

    results = engine.execute(plan)

    assert results[0].success
    assert gate.engaged is True
    assert gate.actor == "risk-engine"
    assert gate.reason == f"incident:{incident.id}"
    # No direct kill-switch field was toggled anywhere in the control plane.
    assert not hasattr(incident, "kill_switch")
    assert not hasattr(plan, "kill_switch")
