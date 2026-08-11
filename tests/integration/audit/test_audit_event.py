"""Tests for audit_event.py — AuditEvent, EventType, ActorType."""

import os
import sys
import types
import importlib.util
import unittest

_ws = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
_int_dir = os.path.join(_ws, 'services', 'integration')
_audit_dir = os.path.join(_int_dir, 'audit')

if 'services' not in sys.modules:
    _svc = types.ModuleType('services')
    _svc.__path__ = [os.path.join(_ws, 'services')]
    sys.modules['services'] = _svc
if 'services.integration' not in sys.modules:
    _mod = types.ModuleType('services.integration')
    _mod.__path__ = [_int_dir]
    sys.modules['services.integration'] = _mod
if 'services.integration.audit' not in sys.modules:
    _pkg = types.ModuleType('services.integration.audit')
    _pkg.__path__ = [_audit_dir]
    sys.modules['services.integration.audit'] = _pkg

_audit_files = [
    'audit_event', 'audit_record', 'audit_fingerprint',
    'audit_chain', 'audit_verifier', 'audit_query',
]
for _name in _audit_files:
    _fp = os.path.join(_audit_dir, f'{_name}.py')
    _mod_name = f'services.integration.audit.{_name}'
    if _mod_name not in sys.modules:
        _spec = importlib.util.spec_from_file_location(_mod_name, _fp)
        _m = importlib.util.module_from_spec(_spec)
        sys.modules[_mod_name] = _m
        _spec.loader.exec_module(_m)

from services.integration.audit.audit_event import (
    AuditEvent, EventType, ActorType, compute_event_hash,
)


class TestActorType(unittest.TestCase):

    def test_all_types(self):
        self.assertIn(ActorType.SYSTEM, ActorType)
        self.assertIn(ActorType.RISK_ENGINE, ActorType)
        self.assertIn(ActorType.OMS, ActorType)
        self.assertIn(ActorType.EXECUTION_ENGINE, ActorType)

    def test_labels(self):
        self.assertEqual(ActorType.SYSTEM.label, "System")
        self.assertEqual(ActorType.OMS.label, "OMS")


class TestEventType(unittest.TestCase):

    def test_all_types(self):
        self.assertIn(EventType.DECISION_CREATED, EventType)
        self.assertIn(EventType.RISK_EVALUATED, EventType)
        self.assertIn(EventType.GOVERNANCE_EVALUATED, EventType)
        self.assertIn(EventType.AUTHORITY_CHECKED, EventType)
        self.assertIn(EventType.APPROVAL_GRANTED, EventType)
        self.assertIn(EventType.CERTIFICATE_ISSUED, EventType)
        self.assertIn(EventType.ORDER_CREATED, EventType)
        self.assertIn(EventType.TRADE_RECORDED, EventType)

    def test_labels(self):
        self.assertEqual(EventType.RISK_EVALUATED.label, "Risk Evaluated")
        self.assertEqual(EventType.ORDER_FILLED.label, "Order Filled")


class TestAuditEvent(unittest.TestCase):

    def test_default_construction(self):
        event = AuditEvent()
        self.assertTrue(event.event_id.startswith("AEVT-"))
        self.assertEqual(event.event_type, EventType.DECISION_CREATED)
        self.assertEqual(event.actor_type, ActorType.SYSTEM)
        self.assertGreater(event.timestamp, 0)

    def test_is_control_event(self):
        risk = AuditEvent(event_type=EventType.RISK_EVALUATED)
        self.assertTrue(risk.is_control_event)

        trade = AuditEvent(event_type=EventType.TRADE_RECORDED)
        self.assertFalse(trade.is_control_event)

    def test_is_execution_event(self):
        fill = AuditEvent(event_type=EventType.ORDER_FILLED)
        self.assertTrue(fill.is_execution_event)

        approval = AuditEvent(event_type=EventType.APPROVAL_GRANTED)
        self.assertFalse(approval.is_execution_event)

    def test_factory_create(self):
        event = AuditEvent.create(
            event_type=EventType.RISK_EVALUATED,
            lineage_id="LINEAGE-001",
            actor_type=ActorType.RISK_ENGINE,
            actor_id="risk-service-v3",
            payload={"exposure": 12.4, "limit": 15.0},
        )
        self.assertEqual(event.lineage_id, "LINEAGE-001")
        self.assertEqual(event.actor_type, ActorType.RISK_ENGINE)
        self.assertEqual(event.actor_id, "risk-service-v3")
        self.assertEqual(event.payload["exposure"], 12.4)

    def test_seal_produces_hash(self):
        event = AuditEvent.create(
            event_type=EventType.DECISION_CREATED,
            lineage_id="LINEAGE-001",
        )
        event.seal(previous_hash="", sequence_number=0)
        self.assertNotEqual(event.event_hash, "")
        self.assertEqual(event.previous_event_hash, "")
        self.assertEqual(event.sequence_number, 0)

    def test_seal_with_previous_hash(self):
        event = AuditEvent.create(
            event_type=EventType.RISK_EVALUATED,
            lineage_id="LINEAGE-001",
        )
        event.seal(previous_hash="abc123", sequence_number=1)
        self.assertEqual(event.previous_event_hash, "abc123")
        self.assertEqual(event.sequence_number, 1)

    def test_hash_deterministic(self):
        event1 = AuditEvent.create(
            event_type=EventType.DECISION_CREATED,
            lineage_id="LINEAGE-001",
            payload={"key": "value"},
        )
        h1 = event1.compute_hash(previous_hash="")

        event2 = AuditEvent(
            event_type=EventType.DECISION_CREATED,
            lineage_id="LINEAGE-001",
            payload={"key": "value"},
        )
        # Copy timestamp for determinism
        event2.timestamp = event1.timestamp
        event2.event_id = event1.event_id
        h2 = event2.compute_hash(previous_hash="")

        self.assertEqual(h1, h2)

    def test_hash_changes_with_different_payload(self):
        event = AuditEvent.create(
            event_type=EventType.DECISION_CREATED,
            lineage_id="LINEAGE-001",
            payload={"key": "value1"},
        )
        h1 = event.compute_hash()

        event.payload = {"key": "value2"}
        h2 = event.compute_hash()

        self.assertNotEqual(h1, h2)

    def test_compute_hash_no_previous(self):
        event = AuditEvent.create(
            event_type=EventType.APPROVAL_GRANTED,
            lineage_id="L-1",
        )
        h = event.compute_hash()
        self.assertEqual(len(h), 64)  # SHA-256 hex

    def test_to_dict(self):
        event = AuditEvent.create(
            event_type=EventType.CERTIFICATE_ISSUED,
            lineage_id="L-1",
            actor_type=ActorType.OMS,
            actor_id="oms-1",
        )
        event.seal(sequence_number=5)
        d = event.to_dict()
        self.assertEqual(d["event_type"], "CERTIFICATE_ISSUED")
        self.assertEqual(d["actor_type"], "OMS")
        self.assertEqual(d["sequence_number"], 5)


if __name__ == '__main__':
    unittest.main()
