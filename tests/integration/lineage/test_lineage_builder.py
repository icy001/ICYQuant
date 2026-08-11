"""Tests for lineage_builder.py — LineageBuilder."""

import os
import sys
import types
import importlib.util
import unittest

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

from services.integration.lineage.lineage_node import NodeType
from services.integration.lineage.lineage_edge import EdgeType
from services.integration.lineage.lineage_builder import LineageBuilder
from services.integration.lineage.lineage_errors import LineageIntegrityError


class TestLineageBuilder(unittest.TestCase):

    def test_lineage_id_autogen(self):
        b = LineageBuilder()
        self.assertTrue(b._lineage_id.startswith("LINEAGE-"))

    def test_lineage_id_custom(self):
        b = LineageBuilder("MY-LINEAGE")
        self.assertEqual(b._lineage_id, "MY-LINEAGE")

    def test_build_empty_graph(self):
        graph = LineageBuilder("L-1").build()
        self.assertEqual(graph.lineage_id, "L-1")
        self.assertEqual(graph.node_count, 0)

    def test_strategy_to_signal_to_decision(self):
        graph = (LineageBuilder("L-1")
                 .start_with_strategy("STRAT-007")
                 .emit_signal("SIG-381")
                 .emit_decision("DEC-091")
                 .build())

        self.assertEqual(graph.node_count, 3)
        self.assertEqual(graph.edge_count, 2)
        self.assertTrue(graph.get_node_by_object_id("STRAT-007"))
        self.assertTrue(graph.get_node_by_object_id("SIG-381"))
        self.assertTrue(graph.get_node_by_object_id("DEC-091"))

    def test_full_control_chain(self):
        graph = (LineageBuilder("L-FULL")
                 .start_with_strategy("STRAT-001")
                 .emit_signal("SIG-001")
                 .emit_decision("DEC-001")
                 .with_risk_decision(True, policy_version="RISK-v8",
                                     risk_exposure=12.4, risk_limit=15.0)
                 .with_governance_decision(True, state="NORMAL",
                                           policy_version="GOV-v5")
                 .with_authority_decision(True, limit=20_000_000,
                                          requested=12_000_000,
                                          policy_version="AUTH-v3")
                 .with_approval(True, approval_id="APR-001",
                                policy_version="APPROVAL-v2")
                 .with_order_intent("INTENT-001", account_id="ACC-001",
                                    symbol="NVDA", side="BUY")
                 .with_admission(True, admission_id="ADM-001")
                 .with_certificate(True, certificate_id="CERT-001")
                 .emit_order("ORDER-001")
                 .emit_execution("EXEC-001")
                 .emit_trade("TRADE-001")
                 .build())

        self.assertEqual(graph.node_count, 13)
        self.assertEqual(graph.edge_count, 12)

        # Check all node types present
        node_types = {n.node_type for n in graph.nodes.values()}
        for nt in [NodeType.STRATEGY, NodeType.SIGNAL, NodeType.DECISION,
                    NodeType.RISK_DECISION, NodeType.GOVERNANCE_DECISION,
                    NodeType.AUTHORITY_DECISION, NodeType.APPROVAL,
                    NodeType.ORDER_INTENT, NodeType.ADMISSION,
                    NodeType.CERTIFICATE, NodeType.ORDER,
                    NodeType.EXECUTION, NodeType.TRADE]:
            self.assertIn(nt, node_types, f"Missing node type: {nt}")

        # No cycle
        self.assertFalse(graph.has_cycle())

    def test_risk_failure_raises(self):
        b = (LineageBuilder("L-FAIL")
             .start_with_strategy("S")
             .emit_signal("G")
             .emit_decision("D"))
        with self.assertRaises(LineageIntegrityError):
            b.with_risk_decision(False)

    def test_governance_failure_raises(self):
        b = (LineageBuilder("L-FAIL")
             .start_with_strategy("S")
             .emit_signal("G")
             .emit_decision("D")
             .with_risk_decision(True))
        with self.assertRaises(LineageIntegrityError):
            b.with_governance_decision(False)

    def test_authority_failure_raises(self):
        b = (LineageBuilder("L-FAIL")
             .start_with_strategy("S")
             .emit_signal("G")
             .emit_decision("D")
             .with_risk_decision(True)
             .with_governance_decision(True))
        with self.assertRaises(LineageIntegrityError):
            b.with_authority_decision(False)

    def test_approval_failure_raises(self):
        b = (LineageBuilder("L-FAIL")
             .start_with_strategy("S")
             .emit_signal("G")
             .emit_decision("D")
             .with_risk_decision(True)
             .with_governance_decision(True)
             .with_authority_decision(True))
        with self.assertRaises(LineageIntegrityError):
            b.with_approval(False)

    def test_snapshots_created(self):
        b = (LineageBuilder("L-SNAP")
             .start_with_strategy("S")
             .emit_signal("G")
             .emit_decision("D", decision_type="MARKET",
                            decision_reason="momentum")
             .with_risk_decision(True, risk_exposure=12.0, risk_limit=15.0)
             .with_governance_decision(True, state="NORMAL")
             .with_authority_decision(True, limit=1_000_000, requested=500_000)
             .with_approval(True, approval_id="APR-X"))

        snaps = b.get_snapshots()
        self.assertEqual(len(snaps), 1)
        for snap in snaps.values():
            self.assertEqual(snap.risk_exposure, 12.0)
            self.assertEqual(snap.risk_limit, 15.0)
            self.assertEqual(snap.governance_state, "NORMAL")
            self.assertEqual(snap.authority_limit, 1_000_000)
            self.assertEqual(snap.authority_requested, 500_000)
            self.assertEqual(snap.approval_id, "APR-X")

    def test_custom_lineage_id(self):
        b = LineageBuilder()
        self.assertEqual(b.lineage_id, b._lineage_id)

    def test_parent_references_set(self):
        graph = (LineageBuilder("L-PAR")
                 .start_with_strategy("S")
                 .emit_signal("G")
                 .emit_decision("D")
                 .build())

        decision = graph.get_node_by_object_id("D")
        signal = graph.get_node_by_object_id("G")
        self.assertEqual(decision.parent_node_id, signal.node_id)

    def test_add_custom_node(self):
        graph = (LineageBuilder("L-CUST")
                 .start_with_strategy("S")
                 .emit_signal("G")
                 .emit_decision("D")
                 .with_risk_decision(True)
                 .with_governance_decision(True)
                 .with_authority_decision(True)
                 .with_approval(True)
                 .with_order_intent("I-1")
                 .add_custom_node(NodeType.POSITION, "POS-001",
                                  EdgeType.UPDATED)
                 .build())

        pos = graph.get_node_by_object_id("POS-001")
        self.assertIsNotNone(pos)
        self.assertEqual(pos.node_type, NodeType.POSITION)


if __name__ == '__main__':
    unittest.main()
