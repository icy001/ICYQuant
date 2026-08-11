"""Tests for OrderEventValidator — integrity, hash chain, duplicates."""

import os
import sys
import types
import importlib.util
import unittest

# ── Bootstrap ──────────────────────────────────────
_ws = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
_oms_dir = os.path.join(_ws, 'services', 'oms')
_domain_dir = os.path.join(_oms_dir, 'domain')
_events_dir = os.path.join(_oms_dir, 'events')

if 'services' not in sys.modules:
    _svc = types.ModuleType('services')
    _svc.__path__ = [os.path.join(_ws, 'services')]
    sys.modules['services'] = _svc
if 'services.oms' not in sys.modules:
    _mod = types.ModuleType('services.oms')
    _mod.__path__ = [_oms_dir]
    sys.modules['services.oms'] = _mod
if 'services.oms.domain' not in sys.modules:
    _pkg = types.ModuleType('services.oms.domain')
    _pkg.__path__ = [_domain_dir]
    sys.modules['services.oms.domain'] = _pkg
if 'services.oms.events' not in sys.modules:
    _pkg_ev = types.ModuleType('services.oms.events')
    _pkg_ev.__path__ = [_events_dir]
    sys.modules['services.oms.events'] = _pkg_ev

_domain_files = [
    'order_id', 'order_status', 'order_side', 'order_type',
    'time_in_force', 'order_quantity', 'order_price',
    'order_lifecycle', 'order',
]
for _name in _domain_files:
    _fp = os.path.join(_domain_dir, f'{_name}.py')
    _mod_name = f'services.oms.domain.{_name}'
    if _mod_name not in sys.modules and os.path.exists(_fp):
        _spec = importlib.util.spec_from_file_location(_mod_name, _fp)
        _m = importlib.util.module_from_spec(_spec)
        sys.modules[_mod_name] = _m
        _spec.loader.exec_module(_m)

_event_files = [
    'order_event_type', 'order_event_errors', 'order_event_metadata',
    'order_event_sequence', 'order_event', 'order_event_factory',
    'order_event_serializer', 'order_event_validator',
]
for _name in _event_files:
    _fp = os.path.join(_events_dir, f'{_name}.py')
    _mod_name = f'services.oms.events.{_name}'
    if _mod_name not in sys.modules and os.path.exists(_fp):
        _spec = importlib.util.spec_from_file_location(_mod_name, _fp)
        _m = importlib.util.module_from_spec(_spec)
        sys.modules[_mod_name] = _m
        _spec.loader.exec_module(_m)

from services.oms.events.order_event import OrderEvent
from services.oms.events.order_event_type import OrderEventType
from services.oms.events.order_event_factory import OrderEventFactory
from services.oms.events.order_event_validator import OrderEventValidator
from services.oms.events.order_event_errors import (
    EventValidationError,
    EventSequenceGapError,
    EventHashChainError,
    DuplicateEventError,
    EventCollisionError,
)


def _make_event(order_id="ORD-001", seq=1,
                event_type=OrderEventType.ORDER_CREATED,
                lineage_id="L-1", previous_hash="") -> OrderEvent:
    evt = OrderEvent.create(
        order_id=order_id,
        event_type=event_type,
        sequence=seq,
        lineage_id=lineage_id,
        previous_event_hash=previous_hash,
    )
    evt.seal()
    return evt


def _make_chain(order_id="ORD-001", count=3) -> list:
    events = []
    prev_hash = ""
    for i in range(1, count + 1):
        evt = _make_event(order_id=order_id, seq=i, previous_hash=prev_hash)
        events.append(evt)
        prev_hash = evt.event_hash
    return events


class TestEventValidation(unittest.TestCase):

    def test_valid_event(self):
        evt = _make_event()
        OrderEventValidator.validate_event(evt)

    def test_missing_order_id(self):
        evt = _make_event()
        evt.order_id = ""
        with self.assertRaises(EventValidationError):
            OrderEventValidator.validate_event(evt)

    def test_missing_lineage(self):
        evt = _make_event()
        evt.lineage_id = ""
        with self.assertRaises(EventValidationError):
            OrderEventValidator.validate_event(evt)

    def test_unsealed_event(self):
        evt = OrderEvent.create(
            order_id="ORD-001",
            event_type=OrderEventType.ORDER_CREATED,
            sequence=1,
            lineage_id="L-1",
        )
        with self.assertRaises(EventValidationError):
            OrderEventValidator.validate_event(evt)

    def test_tampered_hash(self):
        evt = _make_event()
        evt.event_hash = "tampered_00000000000000000000000000000000000"
        with self.assertRaises(EventValidationError):
            OrderEventValidator.validate_event(evt)


class TestSequenceValidation(unittest.TestCase):

    def test_valid_sequence(self):
        events = _make_chain(count=3)
        OrderEventValidator.validate_sequence(events)

    def test_gap_in_sequence(self):
        events = _make_chain(count=5)
        # Remove event at index 2 (sequence 3)
        events.pop(2)
        with self.assertRaises(EventSequenceGapError):
            OrderEventValidator.validate_sequence(events)

    def test_check_for_gaps_none(self):
        events = _make_chain(count=4)
        gaps = OrderEventValidator.check_for_gaps(events)
        self.assertEqual(gaps, [])

    def test_check_for_gaps_found(self):
        events = _make_chain(count=5)
        events.pop(2)  # Remove seq 3
        gaps = OrderEventValidator.check_for_gaps(events)
        self.assertIn(3, gaps)


class TestHashChainValidation(unittest.TestCase):

    def test_valid_chain(self):
        events = _make_chain(count=4)
        OrderEventValidator.validate_hash_chain(events)

    def test_broken_chain_linkage(self):
        events = _make_chain(count=3)
        # Tamper with the second event's previous_event_hash
        events[1].previous_event_hash = "wrong_hash"
        with self.assertRaises(EventHashChainError):
            OrderEventValidator.validate_hash_chain(events)

    def test_broken_chain_event_hash(self):
        events = _make_chain(count=3)
        # Tamper with the second event's stored hash
        events[1].event_hash = "tampered_00000000000000000000000000000000000"
        with self.assertRaises(EventHashChainError):
            OrderEventValidator.validate_hash_chain(events)


class TestDuplicateDetection(unittest.TestCase):

    def test_idempotent_replay(self):
        evt = _make_event()
        existing = [evt]
        with self.assertRaises(DuplicateEventError) as ctx:
            OrderEventValidator.check_duplicate(evt, existing)
        self.assertTrue(ctx.exception.idempotent)

    def test_event_collision_different_payload(self):
        evt1 = _make_event(seq=1)
        # Create a different event with the same event_id
        evt2 = OrderEvent.create(
            order_id="ORD-001",
            event_type=OrderEventType.ORDER_CREATED,
            sequence=1,
            lineage_id="L-1",
            payload={"different": True},
        )
        evt2.event_id = evt1.event_id
        evt2.seal()
        with self.assertRaises(EventCollisionError):
            OrderEventValidator.check_duplicate(evt2, [evt1])

    def test_no_duplicate(self):
        evt1 = _make_event(seq=1)
        evt2 = _make_event(seq=2)
        result = OrderEventValidator.check_duplicate(evt2, [evt1])
        self.assertFalse(result)


class TestStreamValidation(unittest.TestCase):

    def test_validate_full_stream(self):
        events = _make_chain(count=4)
        OrderEventValidator.validate_stream(events)

    def test_validate_stream_with_gap(self):
        events = _make_chain(count=5)
        events.pop(2)
        with self.assertRaises(EventSequenceGapError):
            OrderEventValidator.validate_stream(events)


if __name__ == '__main__':
    unittest.main()
