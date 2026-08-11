"""Tests for audit_fingerprint.py — AuditFingerprint."""

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
from services.integration.audit.audit_fingerprint import (
    AuditFingerprint, compute_audit_fingerprint, compute_event_fingerprint,
)


class TestAuditFingerprint(unittest.TestCase):

    def setUp(self):
        self.record = AuditRecord(
            record_id="AREC-001",
            lineage_id="LINEAGE-001",
        )
        # Build a sealed chain
        e1 = AuditEvent.create(
            event_type=EventType.DECISION_CREATED,
            lineage_id="LINEAGE-001",
            actor_type=ActorType.STRATEGY,
            actor_id="strat-1",
        )
        self.record.append_and_seal(e1)

        e2 = AuditEvent.create(
            event_type=EventType.RISK_EVALUATED,
            lineage_id="LINEAGE-001",
            actor_type=ActorType.RISK_ENGINE,
            payload={"exposure": 12.4},
        )
        self.record.append_and_seal(e2)

        e3 = AuditEvent.create(
            event_type=EventType.APPROVAL_GRANTED,
            lineage_id="LINEAGE-001",
            actor_type=ActorType.APPROVAL_ENGINE,
            payload={"approval_id": "APR-001"},
        )
        self.record.append_and_seal(e3)

    def test_for_record(self):
        fp = AuditFingerprint.for_record(self.record)
        self.assertEqual(fp.record_id, "AREC-001")
        self.assertEqual(fp.lineage_id, "LINEAGE-001")
        self.assertEqual(len(fp.fingerprint), 64)

    def test_for_event(self):
        event = self.record.events[0]
        fp = AuditFingerprint.for_event(event)
        self.assertEqual(fp.lineage_id, "LINEAGE-001")
        self.assertEqual(len(fp.fingerprint), 64)

    def test_verify_record_passes(self):
        fp = AuditFingerprint.for_record(self.record)
        self.assertTrue(fp.verify(self.record))

    def test_verify_record_fails_on_tamper(self):
        fp = AuditFingerprint.for_record(self.record)

        # Tamper with the stored event hash directly
        self.record.events[0].event_hash = "tampered_hash_0000000000000000000000000000000000"

        self.assertFalse(fp.verify(self.record))

    def test_verify_record_fails_on_new_event(self):
        fp = AuditFingerprint.for_record(self.record)

        # Add a new event
        e4 = AuditEvent.create(
            event_type=EventType.ORDER_CREATED,
            lineage_id="LINEAGE-001",
        )
        self.record.append_and_seal(e4)

        self.assertFalse(fp.verify(self.record))

    def test_verify_event_passes(self):
        event = self.record.events[1]
        fp = AuditFingerprint.for_event(event)
        self.assertTrue(fp.verify_event(event))

    def test_verify_event_fails_on_change(self):
        event = self.record.events[1]
        fp = AuditFingerprint.for_event(event)

        event.payload["exposure"] = 99.9  # tampered

        self.assertFalse(fp.verify_event(event))

    def test_compute_audit_fingerprint_deterministic(self):
        h1 = compute_audit_fingerprint(
            self.record.record_id,
            self.record.lineage_id,
            self.record.events,
            self.record.chain_hash,
        )
        h2 = compute_audit_fingerprint(
            self.record.record_id,
            self.record.lineage_id,
            self.record.events,
            self.record.chain_hash,
        )
        self.assertEqual(h1, h2)

    def test_to_dict(self):
        fp = AuditFingerprint.for_record(self.record)
        d = fp.to_dict()
        self.assertEqual(d["record_id"], "AREC-001")
        self.assertEqual(d["lineage_id"], "LINEAGE-001")
        self.assertIn("fingerprint", d)


if __name__ == '__main__':
    unittest.main()
