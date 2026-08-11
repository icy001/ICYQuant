"""Tests for lineage_node.py — LineageNode, NodeType."""

import os
import sys
import types
import importlib.util
import unittest

# ── Bootstrap: register packages manually ─────────────────────────
_ws = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
_int_dir = os.path.join(_ws, 'services', 'integration')
_lineage_dir = os.path.join(_int_dir, 'lineage')

if 'services' not in sys.modules:
    _svc = types.ModuleType('services')
    _svc.__path__ = [os.path.join(_ws, 'services')]
    sys.modules['services'] = _svc
if 'services.integration' not in sys.modules:
    _mod = types.ModuleType('services.integration')
    _mod.__path__ = [_int_dir]
    sys.modules['services.integration'] = _mod
if 'services.integration.lineage' not in sys.modules:
    _pkg = types.ModuleType('services.integration.lineage')
    _pkg.__path__ = [_lineage_dir]
    sys.modules['services.integration.lineage'] = _pkg

_lineage_files = [
    'lineage_errors', 'lineage_node', 'lineage_edge', 'lineage_event',
    'lineage_reference', 'lineage_snapshot', 'lineage_graph',
    'lineage_builder', 'lineage_resolver', 'lineage_validator',
    'lineage_query',
]
for _name in _lineage_files:
    _fp = os.path.join(_lineage_dir, f'{_name}.py')
    _mod_name = f'services.integration.lineage.{_name}'
    if _mod_name not in sys.modules:
        _spec = importlib.util.spec_from_file_location(_mod_name, _fp)
        _m = importlib.util.module_from_spec(_spec)
        sys.modules[_mod_name] = _m
        _spec.loader.exec_module(_m)

from services.integration.lineage.lineage_node import (
    LineageNode, NodeType, NODE_TYPE_ORDER,
)


class TestNodeType(unittest.TestCase):
    """Tests for NodeType enum."""

    def test_all_types_exist(self):
        self.assertIn(NodeType.STRATEGY, NodeType)
        self.assertIn(NodeType.SIGNAL, NodeType)
        self.assertIn(NodeType.DECISION, NodeType)
        self.assertIn(NodeType.RISK_DECISION, NodeType)
        self.assertIn(NodeType.GOVERNANCE_DECISION, NodeType)
        self.assertIn(NodeType.AUTHORITY_DECISION, NodeType)
        self.assertIn(NodeType.APPROVAL, NodeType)
        self.assertIn(NodeType.ORDER_INTENT, NodeType)
        self.assertIn(NodeType.ADMISSION, NodeType)
        self.assertIn(NodeType.CERTIFICATE, NodeType)
        self.assertIn(NodeType.ORDER, NodeType)
        self.assertIn(NodeType.EXECUTION, NodeType)
        self.assertIn(NodeType.TRADE, NodeType)
        self.assertIn(NodeType.POSITION, NodeType)
        self.assertIn(NodeType.LEDGER_EVENT, NodeType)

    def test_labels(self):
        self.assertEqual(NodeType.STRATEGY.label, "Strategy")
        self.assertEqual(NodeType.ORDER.label, "Order")
        self.assertEqual(NodeType.TRADE.label, "Trade")

    def test_is_control_node(self):
        self.assertTrue(NodeType.RISK_DECISION.is_control_node)
        self.assertTrue(NodeType.GOVERNANCE_DECISION.is_control_node)
        self.assertTrue(NodeType.AUTHORITY_DECISION.is_control_node)
        self.assertTrue(NodeType.APPROVAL.is_control_node)
        self.assertFalse(NodeType.DECISION.is_control_node)
        self.assertFalse(NodeType.TRADE.is_control_node)

    def test_is_execution_node(self):
        self.assertTrue(NodeType.ORDER.is_execution_node)
        self.assertTrue(NodeType.EXECUTION.is_execution_node)
        self.assertTrue(NodeType.TRADE.is_execution_node)
        self.assertFalse(NodeType.STRATEGY.is_execution_node)
        self.assertFalse(NodeType.DECISION.is_execution_node)

    def test_node_type_order_has_all(self):
        for nt in NodeType:
            self.assertIn(nt, NODE_TYPE_ORDER,
                          f"Missing {nt} in NODE_TYPE_ORDER")


class TestLineageNode(unittest.TestCase):
    """Tests for LineageNode dataclass."""

    def test_default_construction(self):
        node = LineageNode()
        self.assertTrue(node.node_id.startswith("NODE-"))
        self.assertEqual(node.node_type, NodeType.DECISION)
        self.assertGreater(node.timestamp, 0)

    def test_is_control(self):
        risk = LineageNode(node_type=NodeType.RISK_DECISION)
        self.assertTrue(risk.is_control)
        strat = LineageNode(node_type=NodeType.STRATEGY)
        self.assertFalse(strat.is_control)

    def test_is_execution(self):
        order = LineageNode(node_type=NodeType.ORDER)
        self.assertTrue(order.is_execution)
        cert = LineageNode(node_type=NodeType.CERTIFICATE)
        self.assertFalse(cert.is_execution)

    def test_factory_create(self):
        node = LineageNode.create(
            node_type=NodeType.ORDER,
            object_id="ORDER-001",
            lineage_id="LINEAGE-001",
            parent_node_id="NODE-ABC",
            flow_id="FLOW-001",
            metadata={"quantity": 1000},
        )
        self.assertEqual(node.object_id, "ORDER-001")
        self.assertEqual(node.lineage_id, "LINEAGE-001")
        self.assertEqual(node.parent_node_id, "NODE-ABC")
        self.assertEqual(node.flow_id, "FLOW-001")
        self.assertEqual(node.metadata["quantity"], 1000)
        self.assertEqual(node.node_type, NodeType.ORDER)

    def test_to_dict(self):
        node = LineageNode.create(
            node_type=NodeType.CERTIFICATE,
            object_id="CERT-001",
            lineage_id="LINEAGE-X",
        )
        d = node.to_dict()
        self.assertEqual(d["node_type"], "CERTIFICATE")
        self.assertEqual(d["object_id"], "CERT-001")
        self.assertEqual(d["lineage_id"], "LINEAGE-X")

    def test_lineage_id_inheritance(self):
        node = LineageNode(lineage_id="L-001")
        node2 = LineageNode(lineage_id="L-001")
        self.assertEqual(node.lineage_id, node2.lineage_id)


if __name__ == '__main__':
    unittest.main()
