"""Tests for lineage_edge.py — LineageEdge, EdgeType."""

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

from services.integration.lineage.lineage_edge import (
    LineageEdge, EdgeType, EXPECTED_EDGE_SEQUENCE,
)


class TestEdgeType(unittest.TestCase):

    def test_all_types_exist(self):
        self.assertIn(EdgeType.GENERATED, EdgeType)
        self.assertIn(EdgeType.CAUSED, EdgeType)
        self.assertIn(EdgeType.EVALUATED_BY, EdgeType)
        self.assertIn(EdgeType.CONSTRAINED_BY, EdgeType)
        self.assertIn(EdgeType.AUTHORIZED_BY, EdgeType)
        self.assertIn(EdgeType.APPROVED_BY, EdgeType)
        self.assertIn(EdgeType.CERTIFIED_BY, EdgeType)
        self.assertIn(EdgeType.CREATED, EdgeType)
        self.assertIn(EdgeType.EXECUTED_AS, EdgeType)
        self.assertIn(EdgeType.RESULTED_IN, EdgeType)

    def test_labels(self):
        self.assertEqual(EdgeType.GENERATED.label, "generated")
        self.assertEqual(EdgeType.CREATED.label, "created")
        self.assertEqual(EdgeType.RESULTED_IN.label, "resulted in")

    def test_expected_sequence(self):
        self.assertIn(EdgeType.GENERATED, EXPECTED_EDGE_SEQUENCE)
        self.assertIn(EdgeType.RESULTED_IN, EXPECTED_EDGE_SEQUENCE)
        # GENERATED should come before RESULTED_IN in the chain
        gen_idx = EXPECTED_EDGE_SEQUENCE.index(EdgeType.GENERATED)
        res_idx = EXPECTED_EDGE_SEQUENCE.index(EdgeType.RESULTED_IN)
        self.assertLess(gen_idx, res_idx)


class TestLineageEdge(unittest.TestCase):

    def test_default_construction(self):
        edge = LineageEdge()
        self.assertTrue(edge.edge_id.startswith("EDGE-"))
        self.assertEqual(edge.edge_type, EdgeType.CAUSED)
        self.assertGreater(edge.timestamp, 0)

    def test_key(self):
        edge = LineageEdge(
            from_node_id="NODE-A",
            to_node_id="NODE-B",
            edge_type=EdgeType.GENERATED,
        )
        self.assertEqual(edge.key, "NODE-A|GENERATED|NODE-B")

    def test_factory_create(self):
        edge = LineageEdge.create(
            from_node_id="NODE-1",
            to_node_id="NODE-2",
            edge_type=EdgeType.CAUSED,
            lineage_id="LINEAGE-001",
            metadata={"reason": "signal received"},
        )
        self.assertEqual(edge.from_node_id, "NODE-1")
        self.assertEqual(edge.to_node_id, "NODE-2")
        self.assertEqual(edge.edge_type, EdgeType.CAUSED)
        self.assertEqual(edge.lineage_id, "LINEAGE-001")
        self.assertEqual(edge.metadata["reason"], "signal received")

    def test_to_dict(self):
        edge = LineageEdge.create(
            from_node_id="NODE-X", to_node_id="NODE-Y",
            edge_type=EdgeType.CREATED, lineage_id="L-1",
        )
        d = edge.to_dict()
        self.assertEqual(d["from_node_id"], "NODE-X")
        self.assertEqual(d["to_node_id"], "NODE-Y")
        self.assertEqual(d["edge_type"], "CREATED")

    def test_label_property(self):
        edge = LineageEdge(edge_type=EdgeType.RESULTED_IN)
        self.assertEqual(edge.label, "resulted in")


if __name__ == '__main__':
    unittest.main()
