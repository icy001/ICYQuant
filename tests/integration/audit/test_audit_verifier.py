"""Tests for audit_verifier.py — AuditVerifier."""

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
from services.integration.audit.audit_fingerprint import AuditFingerprint
from services.integration.audit.audit_verifier import (
    AuditVerifier, AuditVerificationReport, REQUIRED_CONTROL_EVENTS,
)


def _build_complete_record():
    rec = AuditRecord(
        record_id="AREC-001",
        lineage_id="LINEAGE-001",
    )
    events_spec = [
        (EventType.DECISION_CREATED, ActorType.STRATEGY),
        (EventType.RISK_EVALUATED, ActorType.RISK_ENGINE),
        (EventType.GOVERNANCE_EVALUATED, ActorType.GOVERNANCE_ENGINE),
        (EventType.AUTHORITY_CHECKED, ActorType.AUTHORITY_ENGINE),
        (EventType.APPROVAL_GRANTED, ActorType.APPROVAL_ENGINE),
        (EventType.CERTIFICATE_ISSUED, ActorType.OMS),
        (EventType.ORDER_CREATED, ActorType.OMS),
    ]
    for et, at in events_spec:
        e = AuditEvent.create(
            event_type=et,
            lineage_id="LINEAGE-001",
            actor_type=at,
        )
        rec.append_and_seal(e)
    return rec


class TestAuditVerifier(unittest.TestCase):

    def setUp(self):
        self.verifier = AuditVerifier()
        self.record = _build_complete_record()
        self.verifier.register_record(self.record)

    def test_verify_complete_record_passes(self):
        fp = AuditFingerprint.for_record(self.record)
        report = self.verifier.verify(self.record, expected_fingerprint=fp)
        self.assertTrue(report.passed, msg=report.errors)

    def test_verify_without_fingerprint(self):
        report = self.verifier.verify(self.record)
        self.assertTrue(report.fingerprint_valid)  # no fp = valid by default

    def test_verify_fingerprint_fail(self):
        fp = AuditFingerprint.for_record(self.record)
        # Tamper with the stored event hash
        self.record.events[2].event_hash = "tampered_hash_0000000000000000000000000000000000"
        report = self.verifier.verify(self.record, expected_fingerprint=fp)
        self.assertFalse(report.fingerprint_valid)

    def test_detect_overwrites(self):
        rec = _build_complete_record()
        # Duplicate an event with same ID but different content
        dup = AuditEvent(
            event_id=rec.events[0].event_id,
            event_type=EventType.DECISION_CREATED,
            lineage_id="LINEAGE-001",
            payload={"different": True},
        )
        dup.seal(previous_hash="", sequence_number=99)
        rec.append(dup)

        report = self.verifier.verify(rec)
        self.assertFalse(report.append_only_valid)
        self.assertGreater(len(report.overwrite_detected), 0)

    def test_coverage_check(self):
        # Record with only one event — missing the rest
        incomplete = AuditRecord(
            record_id="AREC-INC",
            lineage_id="LINEAGE-INC",
        )
        e = AuditEvent.create(
            event_type=EventType.DECISION_CREATED,
            lineage_id="LINEAGE-INC",
        )
        incomplete.append_and_seal(e)

        report = self.verifier.verify(incomplete)
        self.assertGreater(len(report.coverage_issues), 0)

    def test_audit_chain_integrity(self):
        fp = AuditFingerprint.for_record(self.record)
        report = self.verifier.verify(self.record, expected_fingerprint=fp)
        self.assertIsNotNone(report.chain_report)
        self.assertTrue(report.chain_report.valid)

    def test_append_only_no_overwrite(self):
        report = self.verifier.verify(self.record)
        self.assertTrue(report.append_only_valid)

    def test_report_to_dict(self):
        fp = AuditFingerprint.for_record(self.record)
        report = self.verifier.verify(self.record, expected_fingerprint=fp)
        d = report.to_dict()
        self.assertTrue(d["passed"])
        self.assertEqual(d["record_id"], "AREC-001")

    def test_required_control_events_defined(self):
        self.assertIn(EventType.DECISION_CREATED, REQUIRED_CONTROL_EVENTS)
        self.assertIn(EventType.RISK_EVALUATED, REQUIRED_CONTROL_EVENTS)
        self.assertIn(EventType.APPROVAL_GRANTED, REQUIRED_CONTROL_EVENTS)
        self.assertIn(EventType.CERTIFICATE_ISSUED, REQUIRED_CONTROL_EVENTS)
        self.assertIn(EventType.ORDER_CREATED, REQUIRED_CONTROL_EVENTS)


if __name__ == '__main__':
    unittest.main()
