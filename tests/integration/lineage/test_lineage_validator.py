"""Tests for lineage_validator.py — LineageValidator."""

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

from services.integration.lineage.lineage_node import LineageNode, NodeType
from services.integration.lineage.lineage_edge import LineageEdge, EdgeType
from services.integration.lineage.lineage_graph import LineageGraph
from services.integration.lineage.lineage_builder import LineageBuilder
from services.integration.lineage.lineage_validator import (
    LineageValidator, LineageValidationReport,
)


def _node(nt: NodeType, oid: str, lid: str = "L-001", parent: str = ""):
    return LineageNode.create(
        node_type=nt, object_id=oid, lineage_id=lid,
        parent_node_id=parent,
    )


def _edge(fr: str, to: str, et: EdgeType):
    return LineageEdge.create(
        from_node_id=fr, to_node_id=to,
        edge_type=et, lineage_id="L-001",
    )


class TestLineageValidator(unittest.TestCase):

    def setUp(self):
        self.validator = LineageValidator()

    def test_valid_graph_passes(self):
        graph = (LineageBuilder("L-VALID")
                 .start_with_strategy("S")
                 .emit_signal("G")
                 .emit_decision("D")
                 .with_risk_decision(True)
                 .with_governance_decision(True)
                 .with_authority_decision(True)
                 .with_approval(True)
                 .with_order_intent("INT-1")
                 .with_certificate(True)
                 .emit_order("ORDER-1")
                 .build())

        report = self.validator.validate(graph)
        self.assertTrue(report.valid, msg=report.errors)

    def test_cycle_detected(self):
        graph = LineageGraph(lineage_id="L-CYCLE")
        n1 = graph.add_node(_node(NodeType.STRATEGY, "S"))
        n2 = graph.add_node(_node(NodeType.SIGNAL, "G"))
        graph.add_edge(_edge(n1.node_id, n2.node_id, EdgeType.GENERATED))
        graph.add_edge(_edge(n2.node_id, n1.node_id, EdgeType.GENERATED))

        report = self.validator.validate(graph)
        self.assertFalse(report.valid)

    def test_missing_required_nodes(self):
        graph = LineageGraph(lineage_id="L-MISS")
        graph.add_node(_node(NodeType.STRATEGY, "S"))

        report = self.validator.validate(graph)
        self.assertFalse(report.valid)
        # should have error about missing required nodes
        codes = {e.code for e in report.errors}
        self.assertIn("MISSING_REQUIRED_NODE", codes)

    def test_lineage_id_mismatch(self):
        graph = LineageGraph(lineage_id="L-001")
        # Insert directly into nodes dict to bypass add_node's auto-fix
        n = _node(NodeType.STRATEGY, "S", lid="L-002")
        graph.nodes[n.node_id] = n

        report = self.validator.validate(graph)
        codes = {e.code for e in report.errors}
        self.assertIn("LINEAGE_ID_MISMATCH", codes)

    def test_orphan_parent(self):
        graph = LineageGraph(lineage_id="L-ORPH")
        n = graph.add_node(_node(NodeType.ORDER, "O-1",
                                  parent="NONEXISTENT"))

        report = self.validator.validate(graph)
        codes = {e.code for e in report.errors}
        self.assertIn("ORPHAN_PARENT", codes)

    def test_strict_mode_warns_missing_recommended(self):
        validator = LineageValidator(strict=True)
        # Missing admission, execution, trade
        graph = (LineageBuilder("L-NO-EXEC")
                 .start_with_strategy("S")
                 .emit_signal("G")
                 .emit_decision("D")
                 .with_risk_decision(True)
                 .with_governance_decision(True)
                 .with_authority_decision(True)
                 .with_approval(True)
                 .with_order_intent("INT-1")
                 .with_certificate(True)
                 .emit_order("ORDER-1")
                 .build())

        report = validator.validate(graph)
        # May pass or fail depending on required node check
        # But should have warnings about recommended nodes
        warning_codes = {w.code for w in report.warnings}
        self.assertIn("MISSING_RECOMMENDED_NODE", warning_codes)

    def test_missing_parent_edge(self):
        graph = LineageGraph(lineage_id="L-MPE")
        s = graph.add_node(_node(NodeType.STRATEGY, "S"))
        g = graph.add_node(_node(NodeType.SIGNAL, "G", parent=s.node_id))
        # No edge added — should flag missing parent edge
        report = self.validator.validate(graph)
        codes = {e.code for e in report.errors}
        self.assertIn("MISSING_PARENT_EDGE", codes)


if __name__ == '__main__':
    unittest.main()
