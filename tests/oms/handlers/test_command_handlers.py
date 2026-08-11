"""Tests for command handlers — integration of validation + aggregate + events."""

import unittest

from services.oms.commands.create_order import CreateOrderCommand
from services.oms.commands.command_metadata import CommandMetadata
from services.oms.event_store.order_event_store import InMemoryOrderEventStore
from services.oms.projection.order_projector import OrderProjector
from services.oms.handlers.create_order_handler import CreateOrderHandler
from services.oms.results.command_result import CommandResult


class TestCommandHandlerIntegration(unittest.TestCase):

    def setUp(self):
        self.store = InMemoryOrderEventStore()
        self.projector = OrderProjector(self.store, use_snapshots=False)
        self.handler = CreateOrderHandler(self.store, self.projector)

    def test_full_pipeline(self):
        cmd = CreateOrderCommand(
            metadata=CommandMetadata.for_system(),
            symbol="AAPL", side="SELL", order_type="LIMIT",
            quantity=500, price=195.0,
            certificate_id="CERT-1", lineage_id="L-1", flow_id="F-1",
            client_order_id="CL-1",
        )
        result = self.handler.execute(cmd)
        self.assertTrue(result.success)

        # Verify events were stored
        events = self.store.read(result.order_id)
        self.assertEqual(len(events), 2)  # ACCEPTED + CREATED

        # Verify projection was updated
        proj = self.projector.get(result.order_id)
        self.assertEqual(proj.symbol, "AAPL")
        self.assertEqual(proj.original_quantity, 500)

    def test_command_result_serialization(self):
        result = CommandResult.ok(
            command_id="CMD-1", order_id="ORD-1",
            event_id="EVT-1", event_sequence=5,
            status="WORKING",
        )
        d = result.to_dict()
        self.assertTrue(d["success"])
        self.assertEqual(d["status"], "WORKING")

    def test_command_result_idempotent(self):
        original = CommandResult.ok(
            command_id="CMD-1", order_id="ORD-1",
            event_id="EVT-1", event_sequence=5,
            status="CREATED",
        )
        replay = CommandResult.idempotent_replay(original)
        self.assertTrue(replay.idempotent)
        self.assertEqual(replay.order_id, original.order_id)


if __name__ == '__main__':
    unittest.main()
