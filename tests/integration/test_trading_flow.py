"""
Tests: Trading Flow
Commit 21 Part 1.1
"""

import sys
import os
import unittest
import types
import importlib.util
import time

_ws = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if "services" not in sys.modules:
    _svc = types.ModuleType("services")
    _svc.__path__ = [os.path.join(_ws, "services")]
    sys.modules["services"] = _svc

_svc_dir = os.path.join(_ws, "services")
_int_dir = os.path.join(_svc_dir, "integration")

if "services.integration" not in sys.modules:
    _mod = types.ModuleType("services.integration")
    _mod.__path__ = [_int_dir]
    sys.modules["services.integration"] = _mod

for _name in [
    "control_state", "control_context", "control_transition",
    "control_result", "control_flow",
    "trading_context", "trading_transition", "trading_result", "trading_flow",
]:
    _fp = os.path.join(_int_dir, f"{_name}.py")
    _spec = importlib.util.spec_from_file_location(
        f"services.integration.{_name}", _fp
    )
    _m = importlib.util.module_from_spec(_spec)
    sys.modules[f"services.integration.{_name}"] = _m
    _spec.loader.exec_module(_m)

from services.integration.control_state import ControlFlowState
from services.integration.trading_context import TradingContext
from services.integration.trading_transition import TradingTransition, TradingTransitionType
from services.integration.trading_result import TradingResult, TradingOutcome
from services.integration.trading_flow import TradingFlow
from services.integration.control_context import TradingControlContext
from services.integration.control_result import ControlResult, GateStatus


class TestTradingFlow(unittest.TestCase):
    """TradingFlow lifecycle."""

    def setUp(self):
        self.ctx = TradingControlContext(
            decision_id="DEC-001",
            strategy_id="STRAT-001",
            portfolio_id="PORT-001",
        )
        self.tctx = TradingContext(
            symbol="AAPL",
            side="BUY",
            quantity=100,
            price=150.0,
            notional=15000,
        )

    def test_flow_creation(self):
        flow = TradingFlow(
            control_context=self.ctx,
            trading_context=self.tctx,
        )
        self.assertIsNotNone(flow.flow_id)
        self.assertTrue(flow.flow_id.startswith("FLOW-"))

    def test_start_creates_decision_transition(self):
        flow = TradingFlow(
            control_context=self.ctx,
            trading_context=self.tctx,
        )
        tt = flow.start()
        self.assertEqual(tt.transition_type, TradingTransitionType.DECISION_CREATED)
        self.assertEqual(len(flow.trading_transitions), 1)

    def test_record_order_created(self):
        flow = TradingFlow(
            control_context=self.ctx,
            trading_context=self.tctx,
        )
        flow.start()
        flow.record_order_created("ORD-001")
        self.assertEqual(len(flow.trading_transitions), 2)
        self.assertEqual(
            flow.trading_transitions[1].transition_type,
            TradingTransitionType.ORDER_CREATED,
        )

    def test_record_order_submitted(self):
        flow = TradingFlow(
            control_context=self.ctx,
            trading_context=self.tctx,
        )
        flow.start()
        flow.record_order_created("ORD-001")
        flow.record_order_submitted("ORD-001")
        self.assertEqual(len(flow.trading_transitions), 3)

    def test_finalize_success(self):
        flow = TradingFlow(
            control_context=self.ctx,
            trading_context=self.tctx,
        )
        flow.start()
        result = flow.finalize(ControlFlowState.EXECUTED, "Done")
        self.assertTrue(result.success)
        self.assertEqual(result.outcome, TradingOutcome.EXECUTED)

    def test_finalize_rejected(self):
        flow = TradingFlow(
            control_context=self.ctx,
            trading_context=self.tctx,
        )
        flow.start()
        result = flow.finalize(ControlFlowState.REJECTED, "Bad risk")
        self.assertFalse(result.success)
        self.assertEqual(result.outcome, TradingOutcome.REJECTED)

    def test_finalize_blocked(self):
        flow = TradingFlow(
            control_context=self.ctx,
            trading_context=self.tctx,
        )
        flow.start()
        result = flow.finalize(ControlFlowState.BLOCKED, "Frozen")
        self.assertFalse(result.success)
        self.assertEqual(result.outcome, TradingOutcome.BLOCKED)

    def test_control_flow_is_accessible(self):
        flow = TradingFlow(
            control_context=self.ctx,
            trading_context=self.tctx,
        )
        self.assertIsNotNone(flow.control_flow)
        self.assertEqual(flow.current_state, ControlFlowState.PROPOSED)

    def test_summary(self):
        flow = TradingFlow(
            control_context=self.ctx,
            trading_context=self.tctx,
        )
        flow.start()
        s = flow.summary()
        self.assertEqual(s["symbol"], "AAPL")
        self.assertEqual(s["side"], "BUY")
        self.assertEqual(s["quantity"], 100)

    def test_flow_id_matches_context(self):
        flow = TradingFlow(
            control_context=self.ctx,
            trading_context=self.tctx,
        )
        self.assertEqual(flow.flow_id, flow.control_context.flow_id)


class TestTradingContext(unittest.TestCase):
    """TradingContext domain model."""

    def test_defaults(self):
        tc = TradingContext()
        self.assertEqual(tc.symbol, "")
        self.assertEqual(tc.quantity, 0.0)
        self.assertEqual(tc.order_type, "LIMIT")

    def test_to_dict(self):
        tc = TradingContext(
            symbol="TSLA",
            side="SELL",
            quantity=50,
            price=200.0,
            notional=10000,
        )
        d = tc.to_dict()
        self.assertEqual(d["symbol"], "TSLA")
        self.assertEqual(d["notional"], 10000)


class TestTradingTransition(unittest.TestCase):
    """TradingTransition domain model."""

    def test_creation(self):
        tt = TradingTransition(
            transition_type=TradingTransitionType.ORDER_CREATED,
            flow_id="FLOW-001",
            order_id="ORD-001",
            quantity=100,
            price=150.0,
        )
        self.assertTrue(tt.transition_id.startswith("TT-"))
        self.assertEqual(tt.transition_type, TradingTransitionType.ORDER_CREATED)

    def test_to_dict(self):
        tt = TradingTransition(
            transition_type=TradingTransitionType.ORDER_FILLED,
            flow_id="FLOW-001",
            notional=15000,
        )
        d = tt.to_dict()
        self.assertEqual(d["transition_type"], "ORDER_FILLED")
        self.assertEqual(d["notional"], 15000)


if __name__ == "__main__":
    unittest.main()
