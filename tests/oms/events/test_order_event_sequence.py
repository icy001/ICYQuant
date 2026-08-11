"""Tests for OrderEventSequence — gap detection and validation."""

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

from services.oms.events.order_event_sequence import OrderEventSequence
from services.oms.events.order_event_errors import EventSequenceGapError


class TestSequenceAllocation(unittest.TestCase):

    def test_allocate_starts_at_1(self):
        seq = OrderEventSequence.for_order("ORD-001")
        self.assertEqual(seq.allocate(), 1)
        self.assertEqual(seq.allocate(), 2)
        self.assertEqual(seq.allocate(), 3)

    def test_next_sequence(self):
        seq = OrderEventSequence.for_order("ORD-001")
        self.assertEqual(seq.next_sequence, 1)
        seq.allocate()
        self.assertEqual(seq.next_sequence, 2)

    def test_last_sequence(self):
        seq = OrderEventSequence.for_order("ORD-001")
        self.assertEqual(seq.last_sequence, 0)
        seq.allocate()
        self.assertEqual(seq.last_sequence, 1)


class TestSequenceValidation(unittest.TestCase):

    def test_expect_next_valid(self):
        seq = OrderEventSequence.for_order("ORD-001")
        seq.expect_next(1)
        seq.expect_next(2)
        self.assertEqual(seq.next_sequence, 3)

    def test_expect_next_gap_raises(self):
        seq = OrderEventSequence.for_order("ORD-001")
        with self.assertRaises(EventSequenceGapError):
            seq.expect_next(5)


class TestGapDetection(unittest.TestCase):

    def test_no_gaps(self):
        gaps = OrderEventSequence.find_gaps([1, 2, 3, 4, 5])
        self.assertEqual(gaps, [])

    def test_find_gap(self):
        gaps = OrderEventSequence.find_gaps([1, 2, 4, 5])
        self.assertEqual(gaps, [3])

    def test_find_multiple_gaps(self):
        gaps = OrderEventSequence.find_gaps([1, 3, 5, 7])
        self.assertEqual(gaps, [2, 4, 6])

    def test_empty_list(self):
        gaps = OrderEventSequence.find_gaps([])
        self.assertEqual(gaps, [])

    def test_single_element(self):
        gaps = OrderEventSequence.find_gaps([1])
        self.assertEqual(gaps, [])

    def test_validate_sequence_list_valid(self):
        self.assertTrue(OrderEventSequence.validate_sequence_list([1, 2, 3]))

    def test_validate_sequence_list_with_gap(self):
        with self.assertRaises(EventSequenceGapError):
            OrderEventSequence.validate_sequence_list([1, 2, 4, 5])


if __name__ == '__main__':
    unittest.main()
