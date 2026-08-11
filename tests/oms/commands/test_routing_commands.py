"""Tests for StartRouting and MarkWorking commands."""

import unittest

from services.oms.commands.create_order import CreateOrderCommand
from services.oms.commands.start_routing import StartRoutingCommand
from services.oms.commands.mark_working import MarkWorkingCommand
from services.oms.commands.command_metadata import CommandMetadata
from services.oms.event_store.order_event_store import InMemoryOrderEventStore
from services.oms.projection.order_projector import OrderProjector
from services.oms.handlers.create_order_handler import CreateOrderHandler
from services.oms.handlers.routing_handler import RoutingHandler


def _create_order(handler, order_id=None, **kwargs):
    defaults = dict(
        metadata=CommandMetadata.for_system(),
        symbol="NVDA", side="BUY", order_type="MARKET",
        quantity=1000, certificate_id="CERT-001",
        lineage_id="L-1", flow_id="F-1",
        client_order_id="CLIENT-001",
    )
    defaults.update(kwargs)
    if order_id:
        defaults["order_id"] = order_id
    cmd = CreateOrderCommand(**defaults)
    return handler.execute(cmd)


class TestRoutingCommands(unittest.TestCase):

    def setUp(self):
        self.store = InMemoryOrderEventStore()
        self.projector = OrderProjector(self.store, use_snapshots=False)
        self.create_handler = CreateOrderHandler(self.store, self.projector)
        self.routing_handler = RoutingHandler(self.store, self.projector)
        result = _create_order(self.create_handler)
        self.order_id = result.order_id

    def test_start_routing(self):
        cmd = StartRoutingCommand(
            metadata=CommandMetadata.for_system(),
            order_id=self.order_id,
        )
        result = self.routing_handler.execute(cmd)
        self.assertTrue(result.success)
        self.assertEqual(result.status, "ROUTING")

    def test_mark_working(self):
        # First route
        self.routing_handler.execute(StartRoutingCommand(
            metadata=CommandMetadata.for_system(),
            order_id=self.order_id,
        ))
        # Then working
        cmd = MarkWorkingCommand(
            metadata=CommandMetadata.for_system(),
            order_id=self.order_id,
        )
        result = self.routing_handler.execute(cmd)
        self.assertTrue(result.success)
        self.assertEqual(result.status, "WORKING")

    def test_invalid_transition(self):
        # Try to mark working before routing
        cmd = MarkWorkingCommand(
            metadata=CommandMetadata.for_system(),
            order_id=self.order_id,
        )
        result = self.routing_handler.execute(cmd)
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "INVALID_STATE_TRANSITION")


if __name__ == '__main__':
    unittest.main()
