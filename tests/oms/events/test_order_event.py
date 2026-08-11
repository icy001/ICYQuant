"""Tests for OrderEvent — creation, hashing, serialization."""

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
_errors_dir = os.path.join(_oms_dir, 'errors')

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
if 'services.oms.errors' not in sys.modules:
    _pkg2 = types.ModuleType('services.oms.errors')
    _pkg2.__path__ = [_errors_dir]
    sys.modules['services.oms.errors'] = _pkg2

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
from services.oms.events.order_event_metadata import OrderEventMetadata
from services.oms.events.order_event_factory import OrderEventFactory


class TestEventCreation(unittest.TestCase):

    def test_create_event(self):
        evt = OrderEvent.create(
            order_id="ORD-001",
            event_type=OrderEventType.ORDER_CREATED,
            sequence=1,
            lineage_id="LINEAGE-001",
        )
        self.assertEqual(evt.order_id, "ORD-001")
        self.assertEqual(evt.event_type, OrderEventType.ORDER_CREATED)
        self.assertEqual(evt.sequence, 1)
        self.assertEqual(evt.lineage_id, "LINEAGE-001")

    def test_event_id_auto_generated(self):
        evt = OrderEvent.create(
            order_id="ORD-001",
            event_type=OrderEventType.ORDER_CREATED,
            sequence=1,
        )
        self.assertTrue(evt.event_id.startswith("EVT-"))

    def test_event_timestamp_auto(self):
        evt = OrderEvent.create(
            order_id="ORD-001",
            event_type=OrderEventType.ORDER_CREATED,
            sequence=1,
        )
        self.assertTrue(evt.timestamp > 0)


class TestEventHashing(unittest.TestCase):

    def test_seal_computes_hash(self):
        evt = OrderEvent.create(
            order_id="ORD-001",
            event_type=OrderEventType.ORDER_CREATED,
            sequence=1,
            lineage_id="L-1",
        )
        evt.seal()
        self.assertTrue(evt.is_sealed)
        self.assertTrue(len(evt.event_hash) > 0)

    def test_verify_hash_valid(self):
        evt = OrderEvent.create(
            order_id="ORD-001",
            event_type=OrderEventType.ORDER_CREATED,
            sequence=1,
            lineage_id="L-1",
        )
        evt.seal()
        self.assertTrue(evt.verify_hash())

    def test_verify_hash_after_tamper(self):
        evt = OrderEvent.create(
            order_id="ORD-001",
            event_type=OrderEventType.ORDER_CREATED,
            sequence=1,
            lineage_id="L-1",
            payload={"quantity": 1000},
        )
        evt.seal()
        # Tamper with stored hash
        evt.event_hash = "tampered_hash_0000000000000000000000000000000000"
        self.assertFalse(evt.verify_hash())

    def test_hash_deterministic(self):
        evt1 = OrderEvent.create(
            order_id="ORD-001", event_type=OrderEventType.ORDER_CREATED,
            sequence=1, lineage_id="L-1",
        )
        evt1.seal()
        evt2 = OrderEvent.create(
            order_id="ORD-001", event_type=OrderEventType.ORDER_CREATED,
            sequence=1, lineage_id="L-1",
        )
        # Different event_id → different hash
        evt2.event_id = evt1.event_id
        evt2.timestamp = evt1.timestamp
        evt2.seal()
        self.assertEqual(evt1.event_hash, evt2.event_hash)


class TestEventSerialization(unittest.TestCase):

    def test_to_dict_and_from_dict(self):
        evt = OrderEventFactory.created(
            order_id="ORD-001", sequence=1,
            symbol="NVDA", side="BUY", order_type="MARKET",
            quantity=1000, price=850.0,
            lineage_id="L-1", flow_id="F-1", certificate_id="C-1",
        )
        d = evt.to_dict()
        self.assertEqual(d["order_id"], "ORD-001")
        self.assertEqual(d["event_type"], "ORDER_CREATED")
        self.assertEqual(d["payload"]["symbol"], "NVDA")

        evt2 = OrderEvent.from_dict(d)
        self.assertEqual(evt2.order_id, evt.order_id)
        self.assertEqual(evt2.event_type, evt.event_type)
        self.assertEqual(evt2.sequence, evt.sequence)

    def test_json_roundtrip(self):
        from services.oms.events.order_event_serializer import OrderEventSerializer
        evt = OrderEventFactory.accepted(
            order_id="ORD-001", sequence=1,
            lineage_id="L-1", certificate_id="C-1",
        )
        json_str = OrderEventSerializer.to_json(evt)
        evt2 = OrderEventSerializer.from_json(json_str)
        self.assertEqual(evt2.event_id, evt.event_id)
        self.assertEqual(evt2.event_hash, evt.event_hash)


class TestEventMetadata(unittest.TestCase):

    def test_system_metadata(self):
        meta = OrderEventMetadata.for_system()
        self.assertEqual(meta.actor_type, "SYSTEM")

    def test_execution_metadata(self):
        meta = OrderEventMetadata.for_execution("EXEC-001", "FLOW-001")
        self.assertEqual(meta.actor_type, "EXECUTION_ENGINE")
        self.assertEqual(meta.actor_id, "EXEC-001")
        self.assertEqual(meta.correlation_id, "FLOW-001")
        self.assertEqual(meta.causation_id, "EXEC-001")

    def test_metadata_serialization(self):
        meta = OrderEventMetadata.for_service(
            "risk-service", correlation_id="F-1", causation_id="DEC-1",
        )
        d = meta.to_dict()
        meta2 = OrderEventMetadata.from_dict(d)
        self.assertEqual(meta2.actor_id, "risk-service")
        self.assertEqual(meta2.correlation_id, "F-1")


class TestEventFactory(unittest.TestCase):

    def test_factory_accepted(self):
        evt = OrderEventFactory.accepted(
            order_id="ORD-1", sequence=1,
            lineage_id="L-1", certificate_id="C-1",
        )
        self.assertEqual(evt.event_type, OrderEventType.ORDER_ACCEPTED)
        self.assertTrue(evt.is_sealed)

    def test_factory_created(self):
        evt = OrderEventFactory.created(
            order_id="ORD-1", sequence=1,
            symbol="AAPL", side="SELL", order_type="LIMIT",
            quantity=500, price=195.0,
            lineage_id="L-1",
        )
        self.assertEqual(evt.event_type, OrderEventType.ORDER_CREATED)
        self.assertEqual(evt.payload["symbol"], "AAPL")
        self.assertEqual(evt.payload["quantity"], 500)

    def test_factory_partial_fill(self):
        evt = OrderEventFactory.partial_fill(
            order_id="ORD-1", sequence=5,
            fill_quantity=300, fill_price=180.0,
            execution_id="EXEC-1",
            lineage_id="L-1",
        )
        self.assertEqual(evt.event_type, OrderEventType.ORDER_PARTIAL_FILL)
        self.assertEqual(evt.payload["fill_quantity"], 300)

    def test_factory_filled_is_terminal(self):
        evt = OrderEventFactory.filled(
            order_id="ORD-1", sequence=5,
            fill_quantity=1000, fill_price=850.0,
            lineage_id="L-1",
        )
        self.assertTrue(evt.is_terminal)


if __name__ == '__main__':
    unittest.main()
