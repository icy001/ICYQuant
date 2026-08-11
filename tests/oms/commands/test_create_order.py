"""Tests for CreateOrderCommand handler."""

import unittest

from services.oms.commands.create_order import CreateOrderCommand
from services.oms.commands.command_metadata import CommandMetadata
from services.oms.event_store.order_event_store import InMemoryOrderEventStore
from services.oms.projection.order_projector import OrderProjector
from services.oms.handlers.create_order_handler import CreateOrderHandler
from services.oms.results.command_errors import DuplicateCommandError


def _make_create_cmd(**overrides):
    defaults = dict(
        metadata=CommandMetadata.for_system(),
        symbol="NVDA",
        side="BUY",
        order_type="MARKET",
        quantity=1000,
        certificate_id="CERT-001",
        lineage_id="L-1",
        flow_id="F-1",
        client_order_id="CLIENT-001",
    )
    defaults.update(overrides)
    return CreateOrderCommand(**defaults)


class TestCreateOrder(unittest.TestCase):

    def setUp(self):
        self.store = InMemoryOrderEventStore()
        self.projector = OrderProjector(self.store, use_snapshots=False)
        self.handler = CreateOrderHandler(self.store, self.projector)

    def test_create_order_success(self):
        cmd = _make_create_cmd()
        result = self.handler.execute(cmd)
        self.assertTrue(result.success)
        self.assertTrue(result.order_id.startswith("ORD-"))
        self.assertEqual(result.status, "CREATED")
        self.assertEqual(result.event_sequence, 2)

    def test_idempotent_replay(self):
        cmd = _make_create_cmd()
        result1 = self.handler.execute(cmd)
        result2 = self.handler.execute(cmd)
        self.assertTrue(result2.idempotent)
        self.assertEqual(result1.order_id, result2.order_id)

    def test_duplicate_client_order_id(self):
        cmd1 = _make_create_cmd(client_order_id="DUP-001")
        self.handler.execute(cmd1)

        cmd2 = _make_create_cmd(client_order_id="DUP-001")
        cmd2.metadata = CommandMetadata.for_system()  # new command_id
        result = self.handler.execute(cmd2)
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "DUPLICATE_COMMAND")

    def test_missing_certificate_rejected(self):
        cmd = _make_create_cmd(certificate_id="")
        result = self.handler.execute(cmd)
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "MISSING_CERTIFICATE")

    def test_invalid_quantity_rejected(self):
        cmd = _make_create_cmd(quantity=0)
        result = self.handler.execute(cmd)
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "INVALID_QUANTITY")


if __name__ == '__main__':
    unittest.main()
