"""Tests for audit_chain.py — AuditChain."""

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
from services.integration.audit.audit_chain import AuditChain


def _sealed_event(et: EventType, lid: str = "L-001",
                  prev: str = "", seq: int = 0):
    event = AuditEvent.create(
        event_type=et, lineage_id=lid,
    )
    event.seal(previous_hash=prev, sequence_number=seq)
    return event


class TestAuditChain(unittest.TestCase):

    def setUp(self):
        self.chain = AuditChain()

    def test_create_record(self):
        rec = self.chain.create_record("LINEAGE-001")
        self.assertTrue(rec.record_id.startswith("AREC-"))
        self.assertEqual(rec.lineage_id, "LINEAGE-001")

    def test_create_record_custom_id(self):
        rec = self.chain.create_record("L-1", record_id="AREC-CUSTOM")
        self.assertEqual(rec.record_id, "AREC-CUSTOM")

    def test_get_record(self):
        rec = self.chain.create_record("L-1")
        self.assertIsNotNone(self.chain.get_record(rec.record_id))

    def test_get_record_by_lineage(self):
        self.chain.create_record("L-A")
        self.chain.create_record("L-B")
        found = self.chain.get_record_by_lineage("L-B")
        self.assertIsNotNone(found)
        self.assertEqual(found.lineage_id, "L-B")

    def test_verify_empty_record(self):
        rec = self.chain.create_record("L-1")
        report = self.chain.verify_chain(rec)
        self.assertTrue(report.valid)

    def test_verify_valid_chain(self):
        rec = self.chain.create_record("L-1")

        e1 = _sealed_event(EventType.DECISION_CREATED, "L-1",
                           prev="", seq=0)
        rec.append(e1)

        e2 = _sealed_event(EventType.RISK_EVALUATED, "L-1",
                           prev=e1.event_hash, seq=1)
        rec.append(e2)

        e3 = _sealed_event(EventType.APPROVAL_GRANTED, "L-1",
                           prev=e2.event_hash, seq=2)
        rec.append(e3)

        # Update chain_hash manually since we used append() not append_and_seal()
        rec.chain_hash = e3.event_hash

        report = self.chain.verify_chain(rec)
        self.assertTrue(report.valid, msg=report.errors)

    def test_verify_broken_link_detected(self):
        rec = self.chain.create_record("L-1")

        e1 = _sealed_event(EventType.DECISION_CREATED, "L-1",
                           prev="", seq=0)
        rec.append(e1)

        e2 = _sealed_event(EventType.RISK_EVALUATED, "L-1",
                           prev="WRONG_HASH", seq=1)
        rec.append(e2)

        report = self.chain.verify_chain(rec)
        self.assertFalse(report.valid)

    def test_verify_hash_mismatch(self):
        rec = self.chain.create_record("L-1")

        event = AuditEvent.create(
            event_type=EventType.DECISION_CREATED,
            lineage_id="L-1",
        )
        event.seal(sequence_number=0)
        # Tamper with the stored hash AFTER sealing
        event.event_hash = "tampered_hash_0000000000000000000000000000000000"
        rec.append(event)

        report = self.chain.verify_chain(rec)
        self.assertFalse(report.valid)

    def test_verify_sequence_number_mismatch(self):
        rec = self.chain.create_record("L-1")

        e1 = _sealed_event(EventType.DECISION_CREATED, "L-1",
                           prev="", seq=999)  # wrong seq
        rec.append(e1)

        report = self.chain.verify_chain(rec)
        self.assertFalse(report.valid)

    def test_verify_all(self):
        rec1 = self.chain.create_record("L-1")
        e1 = _sealed_event(EventType.DECISION_CREATED, "L-1", seq=0)
        rec1.append(e1)
        rec1.chain_hash = e1.event_hash

        rec2 = self.chain.create_record("L-2")
        e2 = _sealed_event(EventType.DECISION_CREATED, "L-2", seq=0)
        rec2.append(e2)
        rec2.chain_hash = e2.event_hash

        reports = self.chain.verify_all()
        self.assertEqual(len(reports), 2)
        self.assertTrue(all(r.valid for r in reports))

    def test_append_and_seal(self):
        rec = self.chain.create_record("L-1")
        e1 = AuditEvent.create(
            event_type=EventType.DECISION_CREATED,
            lineage_id="L-1",
        )
        rec.append_and_seal(e1)
        self.assertEqual(e1.sequence_number, 0)
        self.assertNotEqual(e1.event_hash, "")

        e2 = AuditEvent.create(
            event_type=EventType.RISK_EVALUATED,
            lineage_id="L-1",
        )
        rec.append_and_seal(e2)
        self.assertEqual(e2.sequence_number, 1)
        self.assertEqual(e2.previous_event_hash, e1.event_hash)

    def test_record_freeze(self):
        rec = self.chain.create_record("L-1")
        e1 = _sealed_event(EventType.DECISION_CREATED, "L-1", seq=0)
        rec.append(e1)
        rec.freeze()
        self.assertTrue(rec.is_frozen)

        e2 = _sealed_event(EventType.RISK_EVALUATED, "L-1", seq=1)
        with self.assertRaises(ValueError):
            rec.append(e2)

    def test_record_tamper_detection(self):
        rec = self.chain.create_record("L-1")
        e1 = AuditEvent.create(
            event_type=EventType.DECISION_CREATED,
            lineage_id="L-1",
        )
        rec.append_and_seal(e1)

        # Tamper with the event
        e1.payload["sneaky"] = "changed"
        report = self.chain.verify_chain(rec)
        self.assertFalse(report.valid)


if __name__ == '__main__':
    unittest.main()
