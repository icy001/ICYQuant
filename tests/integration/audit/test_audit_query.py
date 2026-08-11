"""Tests for audit_query.py — AuditQuery."""

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
    AuditEvent, EventType, ActorType,
)
from services.integration.audit.audit_record import AuditRecord
from services.integration.audit.audit_query import AuditQuery


def _build_complete_record(lid: str = "LINEAGE-001",
                           rid: str = "AREC-001"):
    rec = AuditRecord(record_id=rid, lineage_id=lid)
    events_spec = [
        (EventType.DECISION_CREATED, ActorType.STRATEGY, {"decision_id": "DEC-001"}),
        (EventType.RISK_EVALUATED, ActorType.RISK_ENGINE, {"exposure": 12.4, "passed": True}),
        (EventType.GOVERNANCE_EVALUATED, ActorType.GOVERNANCE_ENGINE, {"state": "NORMAL"}),
        (EventType.AUTHORITY_CHECKED, ActorType.AUTHORITY_ENGINE, {"limit": 20_000_000}),
        (EventType.APPROVAL_GRANTED, ActorType.APPROVAL_ENGINE, {"approval_id": "APR-001"}),
        (EventType.ORDER_INTENT_CREATED, ActorType.SYSTEM, {"symbol": "NVDA"}),
        (EventType.ORDER_ADMITTED, ActorType.OMS, {"admission_id": "ADM-001"}),
        (EventType.CERTIFICATE_ISSUED, ActorType.OMS, {"certificate_id": "CERT-001"}),
        (EventType.ORDER_CREATED, ActorType.OMS, {"order_id": "ORDER-001"}),
        (EventType.ORDER_SUBMITTED, ActorType.OMS, {}),
        (EventType.ORDER_FILLED, ActorType.EXECUTION_ENGINE, {"filled": 1000}),
        (EventType.TRADE_RECORDED, ActorType.EXECUTION_ENGINE, {"trade_id": "TRADE-001"}),
    ]
    for et, at, payload in events_spec:
        e = AuditEvent.create(
            event_type=et, lineage_id=lid,
            actor_type=at, payload=payload,
        )
        rec.append_and_seal(e)
    return rec


class TestAuditQuery(unittest.TestCase):

    def setUp(self):
        self.query = AuditQuery()
        self.record = _build_complete_record()
        self.query.register(self.record)

    def test_get_lineage_events(self):
        result = self.query.get_lineage_events("LINEAGE-001")
        self.assertEqual(result["lineage_id"], "LINEAGE-001")
        self.assertEqual(result["event_count"], 12)
        self.assertNotEqual(result["chain_hash"], "")

    def test_get_lineage_events_nonexistent(self):
        result = self.query.get_lineage_events("NONEXISTENT")
        self.assertEqual(result["events"], [])

    def test_get_events_by_type(self):
        events = self.query.get_events_by_type(
            "LINEAGE-001", EventType.RISK_EVALUATED)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "RISK_EVALUATED")
        self.assertEqual(events[0]["payload"]["exposure"], 12.4)

    def test_get_control_events(self):
        events = self.query.get_control_events("LINEAGE-001")
        self.assertGreater(len(events), 0)
        control_types = {e["event_type"] for e in events}
        self.assertIn("RISK_EVALUATED", control_types)
        self.assertIn("APPROVAL_GRANTED", control_types)
        self.assertNotIn("ORDER_FILLED", control_types)  # execution, not control

    def test_get_execution_events(self):
        events = self.query.get_execution_events("LINEAGE-001")
        self.assertGreater(len(events), 0)
        exec_types = {e["event_type"] for e in events}
        self.assertIn("ORDER_FILLED", exec_types)
        self.assertIn("TRADE_RECORDED", exec_types)
        self.assertNotIn("APPROVAL_GRANTED", exec_types)

    def test_get_decision_audit(self):
        result = self.query.get_decision_audit("LINEAGE-001")
        self.assertEqual(result["lineage_id"], "LINEAGE-001")
        self.assertGreater(len(result["audit"]), 0)

        # Check ordering
        sequences = [a["sequence"] for a in result["audit"]]
        self.assertEqual(sequences, sorted(sequences))

    def test_get_decision_audit_nonexistent(self):
        result = self.query.get_decision_audit("NONEXISTENT")
        self.assertEqual(result["lineage_id"], "NONEXISTENT")
        self.assertEqual(result["audit"], [])

    def test_decision_audit_content(self):
        result = self.query.get_decision_audit("LINEAGE-001")
        event_types = [a["event_type"] for a in result["audit"]]
        self.assertIn("DECISION_CREATED", event_types)
        self.assertIn("APPROVAL_GRANTED", event_types)
        self.assertIn("TRADE_RECORDED", event_types)

    def test_get_record_history(self):
        result = self.query.get_record_history("AREC-001")
        self.assertEqual(result["record_id"], "AREC-001")
        self.assertEqual(len(result["events"]), 12)

    def test_get_record_history_nonexistent(self):
        result = self.query.get_record_history("NONEXISTENT")
        self.assertEqual(result["events"], [])

    def test_events_by_type_nonexistent(self):
        events = self.query.get_events_by_type(
            "NONEXISTENT", EventType.RISK_EVALUATED)
        self.assertEqual(events, [])

    def test_control_events_nonexistent(self):
        events = self.query.get_control_events("NONEXISTENT")
        self.assertEqual(events, [])

    def test_execution_events_nonexistent(self):
        events = self.query.get_execution_events("NONEXISTENT")
        self.assertEqual(events, [])


if __name__ == '__main__':
    unittest.main()
