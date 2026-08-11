"""Tests for ApplyExecutionCommand handler — partial/full fills, duplicates."""

import unittest

from services.oms.commands.create_order import CreateOrderCommand
from services.oms.commands.start_routing import StartRoutingCommand
from services.oms.commands.mark_working import MarkWorkingCommand
from services.oms.commands.apply_execution import ApplyExecutionCommand
from services.oms.commands.command_metadata import CommandMetadata
from services.oms.event_store.order_event_store import InMemoryOrderEventStore
from services.oms.projection.order_projector import OrderProjector
from services.oms.handlers.create_order_handler import CreateOrderHandler
from services.oms.handlers.routing_handler import RoutingHandler
from services.oms.handlers.execution_handler import ExecutionHandler


def _make_order_working(create_handler, routing_handler, order_id=None):
    """Create an order and advance to WORKING state."""
    defaults = dict(
        metadata=CommandMetadata.for_system(),
        symbol="NVDA", side="BUY", order_type="MARKET",
        quantity=1000, certificate_id="CERT-001",
        lineage_id="L-1", flow_id="F-1",
        client_order_id="CLIENT-001",
    )
    if order_id:
        defaults["order_id"] = order_id
    result = create_handler.execute(CreateOrderCommand(**defaults))
    oid = result.order_id

    routing_handler.execute(StartRoutingCommand(
        metadata=CommandMetadata.for_system(), order_id=oid,
    ))
    routing_handler.execute(MarkWorkingCommand(
        metadata=CommandMetadata.for_system(), order_id=oid,
    ))
    return oid


class TestExecutionCommands(unittest.TestCase):

    def setUp(self):
        self.store = InMemoryOrderEventStore()
        self.projector = OrderProjector(self.store, use_snapshots=False)
        self.create_handler = CreateOrderHandler(self.store, self.projector)
        self.routing_handler = RoutingHandler(self.store, self.projector)
        self.exec_handler = ExecutionHandler(self.store, self.projector)
        self.order_id = _make_order_working(
            self.create_handler, self.routing_handler,
        )

    def test_partial_fill(self):
        cmd = ApplyExecutionCommand(
            metadata=CommandMetadata.for_execution("EXEC-1"),
            order_id=self.order_id,
            execution_id="EXEC-1",
            fill_quantity=300, fill_price=180,
        )
        result = self.exec_handler.execute(cmd)
        self.assertTrue(result.success)
        self.assertEqual(result.status, "PARTIALLY_FILLED")

    def test_full_fill(self):
        cmd = ApplyExecutionCommand(
            metadata=CommandMetadata.for_execution("EXEC-1"),
            order_id=self.order_id,
            execution_id="EXEC-1",
            fill_quantity=1000, fill_price=850,
        )
        result = self.exec_handler.execute(cmd)
        self.assertTrue(result.success)
        self.assertEqual(result.status, "FILLED")

    def test_multiple_partial_then_full(self):
        # Fill 300
        self.exec_handler.execute(ApplyExecutionCommand(
            metadata=CommandMetadata.for_execution("EXEC-1"),
            order_id=self.order_id,
            execution_id="EXEC-1", fill_quantity=300, fill_price=180,
        ))
        # Fill 700
        cmd = ApplyExecutionCommand(
            metadata=CommandMetadata.for_execution("EXEC-2"),
            order_id=self.order_id,
            execution_id="EXEC-2", fill_quantity=700, fill_price=181,
        )
        result = self.exec_handler.execute(cmd)
        self.assertTrue(result.success)
        self.assertEqual(result.status, "FILLED")

    def test_duplicate_execution_idempotent(self):
        cmd = ApplyExecutionCommand(
            metadata=CommandMetadata.for_execution("EXEC-1"),
            order_id=self.order_id,
            execution_id="EXEC-1", fill_quantity=300, fill_price=180,
        )
        result1 = self.exec_handler.execute(cmd)
        # Replay same execution
        cmd2 = ApplyExecutionCommand(
            metadata=CommandMetadata.for_execution("EXEC-1"),
            order_id=self.order_id,
            execution_id="EXEC-1", fill_quantity=300, fill_price=180,
        )
        result2 = self.exec_handler.execute(cmd2)
        self.assertTrue(result2.success)
        # Should not have created a new fill — still 5 events (4 lifecycle + 1 fill)
        self.assertEqual(self.store.count(self.order_id), 5)

    def test_conflicting_execution_id(self):
        # First fill
        self.exec_handler.execute(ApplyExecutionCommand(
            metadata=CommandMetadata.for_execution("EXEC-1"),
            order_id=self.order_id,
            execution_id="EXEC-1", fill_quantity=300, fill_price=180,
        ))
        # Same execution_id, different payload
        cmd = ApplyExecutionCommand(
            metadata=CommandMetadata.for_execution("EXEC-1"),
            order_id=self.order_id,
            execution_id="EXEC-1", fill_quantity=500, fill_price=181,
        )
        result = self.exec_handler.execute(cmd)
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "EXECUTION_ID_CONFLICT")

    def test_quantity_exceeded(self):
        cmd = ApplyExecutionCommand(
            metadata=CommandMetadata.for_execution("EXEC-1"),
            order_id=self.order_id,
            execution_id="EXEC-1", fill_quantity=1001, fill_price=850,
        )
        result = self.exec_handler.execute(cmd)
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "QUANTITY_EXCEEDED")


if __name__ == '__main__':
    unittest.main()
