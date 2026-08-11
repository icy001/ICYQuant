"""Tests for cancel, reject, expire commands."""

import unittest
import time

from services.oms.commands.create_order import CreateOrderCommand
from services.oms.commands.start_routing import StartRoutingCommand
from services.oms.commands.mark_working import MarkWorkingCommand
from services.oms.commands.request_cancel import RequestCancelCommand
from services.oms.commands.confirm_cancel import ConfirmCancelCommand
from services.oms.commands.reject_order import RejectOrderCommand
from services.oms.commands.expire_order import ExpireOrderCommand
from services.oms.commands.command_metadata import CommandMetadata
from services.oms.event_store.order_event_store import InMemoryOrderEventStore
from services.oms.projection.order_projector import OrderProjector
from services.oms.handlers.create_order_handler import CreateOrderHandler
from services.oms.handlers.routing_handler import RoutingHandler
from services.oms.handlers.cancellation_handler import CancellationHandler


def _make_order_working(create_handler, routing_handler):
    defaults = dict(
        metadata=CommandMetadata.for_system(),
        symbol="NVDA", side="BUY", order_type="MARKET",
        quantity=1000, certificate_id="CERT-001",
        lineage_id="L-1", flow_id="F-1",
        client_order_id="CLIENT-001",
    )
    result = create_handler.execute(CreateOrderCommand(**defaults))
    oid = result.order_id
    routing_handler.execute(StartRoutingCommand(
        metadata=CommandMetadata.for_system(), order_id=oid,
    ))
    routing_handler.execute(MarkWorkingCommand(
        metadata=CommandMetadata.for_system(), order_id=oid,
    ))
    return oid


class TestCancelCommands(unittest.TestCase):

    def setUp(self):
        self.store = InMemoryOrderEventStore()
        self.projector = OrderProjector(self.store, use_snapshots=False)
        self.create_handler = CreateOrderHandler(self.store, self.projector)
        self.routing_handler = RoutingHandler(self.store, self.projector)
        self.cancel_handler = CancellationHandler(self.store, self.projector)
        self.order_id = _make_order_working(
            self.create_handler, self.routing_handler,
        )

    def test_request_cancel(self):
        cmd = RequestCancelCommand(
            metadata=CommandMetadata.for_system(),
            order_id=self.order_id,
            reason="user cancel",
        )
        result = self.cancel_handler.execute(cmd)
        self.assertTrue(result.success)

    def test_confirm_cancel(self):
        # First request
        self.cancel_handler.execute(RequestCancelCommand(
            metadata=CommandMetadata.for_system(),
            order_id=self.order_id, reason="user",
        ))
        # Then confirm
        cmd = ConfirmCancelCommand(
            metadata=CommandMetadata.for_execution("EXEC-CANCEL"),
            order_id=self.order_id,
            cancelled_quantity=1000,
        )
        result = self.cancel_handler.execute(cmd)
        self.assertTrue(result.success)
        self.assertEqual(result.status, "CANCELLED")

    def test_reject_order(self):
        cmd = RejectOrderCommand(
            metadata=CommandMetadata.for_execution("EXEC-1"),
            order_id=self.order_id,
            reject_code="VENUE_REJECTED",
            reject_reason="Invalid size",
        )
        result = self.cancel_handler.execute(cmd)
        self.assertTrue(result.success)
        self.assertEqual(result.status, "REJECTED")

    def test_expire_order(self):
        cmd = ExpireOrderCommand(
            metadata=CommandMetadata.for_system(),
            order_id=self.order_id,
            expired_at=time.time(),
        )
        result = self.cancel_handler.execute(cmd)
        self.assertTrue(result.success)
        self.assertEqual(result.status, "EXPIRED")


if __name__ == '__main__':
    unittest.main()
