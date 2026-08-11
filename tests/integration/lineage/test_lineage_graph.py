"""Tests for lineage_graph.py — LineageGraph."""

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
from services.integration.lineage.lineage_errors import LineageNodeNotFoundError


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


class TestLineageGraph(unittest.TestCase):

    def setUp(self):
        self.graph = LineageGraph(lineage_id="L-001")

    def test_add_node(self):
        n = _node(NodeType.STRATEGY, "STRAT-1")
        self.graph.add_node(n)
        self.assertEqual(self.graph.node_count, 1)
        self.assertEqual(n.lineage_id, "L-001")

    def test_add_edge_requires_nodes(self):
        n1 = _node(NodeType.STRATEGY, "S")
        n2 = _node(NodeType.SIGNAL, "G")
        self.graph.add_node(n1)
        self.graph.add_node(n2)
        e = _edge(n1.node_id, n2.node_id, EdgeType.GENERATED)
        self.graph.add_edge(e)
        self.assertEqual(self.graph.edge_count, 1)

    def test_add_edge_missing_node_raises(self):
        n1 = _node(NodeType.STRATEGY, "S")
        self.graph.add_node(n1)
        e = _edge(n1.node_id, "NONEXISTENT", EdgeType.GENERATED)
        with self.assertRaises(LineageNodeNotFoundError):
            self.graph.add_edge(e)

    def test_get_node(self):
        n = _node(NodeType.TRADE, "T-001")
        self.graph.add_node(n)
        found = self.graph.get_node(n.node_id)
        self.assertEqual(found.object_id, "T-001")

    def test_get_node_missing_raises(self):
        with self.assertRaises(LineageNodeNotFoundError):
            self.graph.get_node("NONEXISTENT")

    def test_get_nodes_by_type(self):
        for i in range(3):
            self.graph.add_node(_node(NodeType.TRADE, f"T-{i}"))
        self.graph.add_node(_node(NodeType.ORDER, "O-001"))
        trades = self.graph.get_nodes_by_type(NodeType.TRADE)
        self.assertEqual(len(trades), 3)

    def test_get_node_by_object_id(self):
        self.graph.add_node(_node(NodeType.ORDER, "ORDER-001"))
        found = self.graph.get_node_by_object_id("ORDER-001")
        self.assertIsNotNone(found)
        self.assertEqual(found.object_id, "ORDER-001")

        missing = self.graph.get_node_by_object_id("MISSING")
        self.assertIsNone(missing)

    def test_forward_traversal(self):
        s = self.graph.add_node(_node(NodeType.STRATEGY, "S-1"))
        g = self.graph.add_node(_node(NodeType.SIGNAL, "G-1", parent=s.node_id))
        d = self.graph.add_node(_node(NodeType.DECISION, "D-1", parent=g.node_id))

        self.graph.add_edge(_edge(s.node_id, g.node_id, EdgeType.GENERATED))
        self.graph.add_edge(_edge(g.node_id, d.node_id, EdgeType.CAUSED))

        fwd = self.graph.forward_from(s.node_id)
        self.assertGreaterEqual(len(fwd), 1)
        obj_ids = {n.object_id for n in fwd}
        self.assertIn("S-1", obj_ids)
        self.assertIn("G-1", obj_ids)
        self.assertIn("D-1", obj_ids)

    def test_backward_traversal(self):
        s = self.graph.add_node(_node(NodeType.STRATEGY, "S-1"))
        g = self.graph.add_node(_node(NodeType.SIGNAL, "G-1", parent=s.node_id))
        d = self.graph.add_node(_node(NodeType.DECISION, "D-1", parent=g.node_id))

        self.graph.add_edge(_edge(s.node_id, g.node_id, EdgeType.GENERATED))
        self.graph.add_edge(_edge(g.node_id, d.node_id, EdgeType.CAUSED))

        bwd = self.graph.backward_from(d.node_id)
        obj_ids = {n.object_id for n in bwd}
        self.assertIn("S-1", obj_ids)
        self.assertIn("G-1", obj_ids)
        self.assertIn("D-1", obj_ids)
        # ancestors should come first
        self.assertEqual(bwd[0].object_id, "S-1")

    def test_has_cycle_empty(self):
        self.assertFalse(self.graph.has_cycle())

    def test_has_cycle_no_cycle(self):
        n1 = self.graph.add_node(_node(NodeType.STRATEGY, "S"))
        n2 = self.graph.add_node(_node(NodeType.SIGNAL, "G"))
        self.graph.add_edge(_edge(n1.node_id, n2.node_id, EdgeType.GENERATED))
        self.assertFalse(self.graph.has_cycle())

    def test_has_cycle_detected(self):
        n1 = self.graph.add_node(_node(NodeType.STRATEGY, "S"))
        n2 = self.graph.add_node(_node(NodeType.SIGNAL, "G"))
        self.graph.add_edge(_edge(n1.node_id, n2.node_id, EdgeType.GENERATED))
        self.graph.add_edge(_edge(n2.node_id, n1.node_id, EdgeType.GENERATED))
        self.assertTrue(self.graph.has_cycle())

    def test_root_nodes(self):
        s = self.graph.add_node(_node(NodeType.STRATEGY, "S"))
        g = self.graph.add_node(_node(NodeType.SIGNAL, "G"))
        self.graph.add_edge(_edge(s.node_id, g.node_id, EdgeType.GENERATED))
        roots = self.graph.root_nodes
        self.assertIn(s.node_id, roots)
        self.assertNotIn(g.node_id, roots)

    def test_leaf_nodes(self):
        s = self.graph.add_node(_node(NodeType.STRATEGY, "S"))
        g = self.graph.add_node(_node(NodeType.SIGNAL, "G"))
        self.graph.add_edge(_edge(s.node_id, g.node_id, EdgeType.GENERATED))
        leaves = self.graph.leaf_nodes
        self.assertIn(g.node_id, leaves)
        self.assertNotIn(s.node_id, leaves)

    def test_find_path(self):
        s = self.graph.add_node(_node(NodeType.STRATEGY, "S"))
        g = self.graph.add_node(_node(NodeType.SIGNAL, "G"))
        d = self.graph.add_node(_node(NodeType.DECISION, "D"))
        self.graph.add_edge(_edge(s.node_id, g.node_id, EdgeType.GENERATED))
        self.graph.add_edge(_edge(g.node_id, d.node_id, EdgeType.CAUSED))

        path = self.graph.find_path(s.node_id, d.node_id)
        self.assertEqual(len(path), 3)
        self.assertEqual(path[0].object_id, "S")
        self.assertEqual(path[-1].object_id, "D")

    def test_check_broken_links(self):
        s = self.graph.add_node(_node(NodeType.STRATEGY, "S"))
        g = self.graph.add_node(
            _node(NodeType.SIGNAL, "G", parent=s.node_id))
        # No edge from S → G
        issues = self.graph.check_broken_links()
        self.assertGreater(len(issues), 0)

    def test_to_dict(self):
        self.graph.add_node(_node(NodeType.ORDER, "O-1"))
        d = self.graph.to_dict()
        self.assertEqual(d["lineage_id"], "L-001")
        self.assertIn("nodes", d)
        self.assertIn("edges", d)


if __name__ == '__main__':
    unittest.main()
