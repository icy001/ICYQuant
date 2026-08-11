"""Tests for OrderStateReducer — event → state reduction."""

import unittest

from services.oms.events.order_event_factory import OrderEventFactory
from services.oms.events.order_event_type import OrderEventType
from services.oms.domain.order_status import OrderStatus
from services.oms.projection.order_projection import OrderProjection
from services.oms.projection.order_state_reducer import OrderStateReducer


def _build_events(order_id="ORD-001", lineage_id="L-1"):
    """Build a chain: ACCEPTED → CREATED → ROUTING → WORKING."""
    events = []
    prev = ""

    e1 = OrderEventFactory.accepted(
        order_id=order_id, sequence=1,
        lineage_id=lineage_id, certificate_id="C-1",
        previous_hash=prev,
    )
    events.append(e1)
    prev = e1.event_hash

    e2 = OrderEventFactory.created(
        order_id=order_id, sequence=2,
        symbol="NVDA", side="BUY", order_type="MARKET",
        quantity=1000, price=0,
        lineage_id=lineage_id, certificate_id="C-1",
        previous_hash=prev,
    )
    events.append(e2)
    prev = e2.event_hash

    e3 = OrderEventFactory.routing_started(
        order_id=order_id, sequence=3,
        lineage_id=lineage_id, certificate_id="C-1",
        previous_hash=prev,
    )
    events.append(e3)
    prev = e3.event_hash

    e4 = OrderEventFactory.working(
        order_id=order_id, sequence=4,
        lineage_id=lineage_id, certificate_id="C-1",
        previous_hash=prev,
    )
    events.append(e4)

    return events


class TestReducerBasics(unittest.TestCase):

    def test_reduce_empty_state(self):
        state = OrderProjection.empty("ORD-001")
        self.assertEqual(state.status, OrderStatus.RECEIVED)

    def test_reduce_single_event(self):
        state = OrderProjection.empty("ORD-001")
        evt = OrderEventFactory.accepted(
            order_id="ORD-001", sequence=1,
            lineage_id="L-1", certificate_id="C-1",
        )
        new_state = OrderStateReducer.reduce(state, evt)
        self.assertEqual(new_state.status, OrderStatus.ACCEPTED)
        self.assertEqual(new_state.certificate_id, "C-1")

    def test_reduce_all(self):
        events = _build_events()
        state = OrderStateReducer.reduce_all(events, "ORD-001")
        self.assertEqual(state.status, OrderStatus.WORKING)
        self.assertEqual(state.original_quantity, 1000)
        self.assertEqual(state.filled_quantity, 0)
        self.assertEqual(state.remaining_quantity, 1000)


class TestReducerFills(unittest.TestCase):

    def test_partial_fill(self):
        events = _build_events()
        prev = events[-1].event_hash

        fill = OrderEventFactory.partial_fill(
            order_id="ORD-001", sequence=5,
            fill_quantity=300, fill_price=180,
            execution_id="EXEC-1",
            lineage_id="L-1",
            previous_hash=prev,
        )
        events.append(fill)

        state = OrderStateReducer.reduce_all(events, "ORD-001")
        self.assertEqual(state.status, OrderStatus.PARTIALLY_FILLED)
        self.assertEqual(state.filled_quantity, 300)
        self.assertEqual(state.remaining_quantity, 700)
        self.assertAlmostEqual(state.average_price, 180.0)

    def test_multiple_partial_fills(self):
        events = _build_events()
        prev = events[-1].event_hash

        f1 = OrderEventFactory.partial_fill(
            order_id="ORD-001", sequence=5,
            fill_quantity=300, fill_price=180,
            execution_id="EXEC-1", lineage_id="L-1",
            previous_hash=prev,
        )
        events.append(f1)
        prev = f1.event_hash

        f2 = OrderEventFactory.partial_fill(
            order_id="ORD-001", sequence=6,
            fill_quantity=200, fill_price=181,
            execution_id="EXEC-2", lineage_id="L-1",
            previous_hash=prev,
        )
        events.append(f2)

        state = OrderStateReducer.reduce_all(events, "ORD-001")
        self.assertEqual(state.filled_quantity, 500)
        self.assertEqual(state.remaining_quantity, 500)
        # VWAP = (300*180 + 200*181) / 500 = 180.4
        self.assertAlmostEqual(state.average_price, 180.4, places=1)

    def test_full_fill(self):
        events = _build_events()
        prev = events[-1].event_hash

        fill = OrderEventFactory.filled(
            order_id="ORD-001", sequence=5,
            fill_quantity=1000, fill_price=850,
            execution_id="EXEC-1",
            lineage_id="L-1",
            previous_hash=prev,
        )
        events.append(fill)

        state = OrderStateReducer.reduce_all(events, "ORD-001")
        self.assertEqual(state.status, OrderStatus.FILLED)
        self.assertEqual(state.filled_quantity, 1000)
        self.assertEqual(state.remaining_quantity, 0)


class TestReducerCancellation(unittest.TestCase):

    def test_cancelled(self):
        events = _build_events()
        prev = events[-1].event_hash

        cancel = OrderEventFactory.cancelled(
            order_id="ORD-001", sequence=5,
            cancelled_quantity=1000, reason="user",
            lineage_id="L-1", previous_hash=prev,
        )
        events.append(cancel)

        state = OrderStateReducer.reduce_all(events, "ORD-001")
        self.assertEqual(state.status, OrderStatus.CANCELLED)
        self.assertEqual(state.cancelled_quantity, 1000)
        self.assertEqual(state.remaining_quantity, 0)


class TestReducerLineage(unittest.TestCase):

    def test_lineage_propagated(self):
        events = _build_events(lineage_id="LINEAGE-E2E")
        state = OrderStateReducer.reduce_all(events, "ORD-001")
        self.assertEqual(state.lineage_id, "LINEAGE-E2E")


if __name__ == '__main__':
    unittest.main()
