"""Tests for EventStream — stream-level operations."""

import unittest

from services.oms.events.order_event_factory import OrderEventFactory
from services.oms.event_store.event_stream import EventStream
from services.oms.events.order_event_errors import EventSequenceGapError


class TestEventStreamOperations(unittest.TestCase):

    def test_empty_stream(self):
        stream = EventStream(order_id="ORD-001")
        self.assertTrue(stream.is_empty)
        self.assertEqual(stream.next_sequence, 1)
        self.assertEqual(stream.last_sequence, 0)

    def test_append_increments_version(self):
        stream = EventStream(order_id="ORD-001")
        evt = OrderEventFactory.accepted(
            order_id="ORD-001", sequence=1, lineage_id="L-1",
        )
        stream.append(evt)
        self.assertEqual(stream.version, 1)
        self.assertEqual(stream.next_sequence, 2)

    def test_last_event_hash(self):
        stream = EventStream(order_id="ORD-001")
        evt = OrderEventFactory.accepted(
            order_id="ORD-001", sequence=1, lineage_id="L-1",
        )
        stream.append(evt)
        self.assertEqual(stream.last_event_hash, evt.event_hash)

    def test_get_lineage_id(self):
        stream = EventStream(order_id="ORD-001")
        evt = OrderEventFactory.accepted(
            order_id="ORD-001", sequence=1,
            lineage_id="LINEAGE-42", flow_id="FLOW-1",
        )
        stream.append(evt)
        self.assertEqual(stream.get_lineage_id(), "LINEAGE-42")
        self.assertEqual(stream.get_flow_id(), "FLOW-1")

    def test_iterate(self):
        stream = EventStream(order_id="ORD-001")
        prev = ""
        for i in range(1, 4):
            evt = OrderEventFactory.accepted(
                order_id="ORD-001", sequence=i,
                lineage_id="L-1", previous_hash=prev,
            )
            stream.append(evt)
            prev = evt.event_hash
        events = list(stream)
        self.assertEqual(len(events), 3)

    def test_len(self):
        stream = EventStream(order_id="ORD-001")
        for i in range(1, 4):
            evt = OrderEventFactory.accepted(
                order_id="ORD-001", sequence=i,
                lineage_id="L-1",
            )
            stream.append(evt)
        self.assertEqual(len(stream), 3)


if __name__ == '__main__':
    unittest.main()
