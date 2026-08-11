"""Tests for lineage_resolver.py — LineageResolver."""

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

from services.integration.lineage.lineage_builder import LineageBuilder
from services.integration.lineage.lineage_resolver import LineageResolver
from services.integration.lineage.lineage_errors import LineageNodeNotFoundError


def _build_full_lineage(lid: str):
    return (LineageBuilder(lid)
            .start_with_strategy("STRAT-001")
            .emit_signal("SIG-001")
            .emit_decision("DEC-001")
            .with_risk_decision(True, risk_exposure=12.0, risk_limit=15.0)
            .with_governance_decision(True, state="NORMAL")
            .with_authority_decision(True, limit=20_000_000,
                                     requested=12_000_000)
            .with_approval(True, approval_id="APR-001")
            .with_order_intent("INTENT-001", symbol="NVDA", side="BUY")
            .with_admission(True)
            .with_certificate(True, certificate_id="CERT-001")
            .emit_order("ORDER-001")
            .emit_execution("EXEC-001")
            .emit_trade("TRADE-001")
            .build())


class TestLineageResolver(unittest.TestCase):

    def setUp(self):
        self.resolver = LineageResolver()
        self.graph = _build_full_lineage("LINEAGE-001")
        self.resolver.register(self.graph)

    # ── Resolution by order ───────────────────────────────────────

    def test_resolve_by_order(self):
        resolution = self.resolver.resolve_by_order("ORDER-001")
        self.assertEqual(resolution.direction, "backward")
        self.assertGreater(resolution.node_count, 1)

        # The first node should be Strategy
        strategy = resolution.nodes[0]
        self.assertEqual(strategy.object_id, "STRAT-001")

    def test_resolve_by_order_not_found(self):
        with self.assertRaises(LineageNodeNotFoundError):
            self.resolver.resolve_by_order("NONEXISTENT")

    # ── Resolution by trade ───────────────────────────────────────

    def test_resolve_by_trade(self):
        resolution = self.resolver.resolve_by_trade("TRADE-001")
        self.assertEqual(resolution.direction, "backward")
        self.assertGreater(resolution.node_count, 1)
        self.assertEqual(resolution.nodes[0].object_id, "STRAT-001")

    # ── Resolution by certificate ─────────────────────────────────

    def test_resolve_by_certificate(self):
        resolution = self.resolver.resolve_by_certificate("CERT-001")
        self.assertEqual(resolution.direction, "bidirectional")
        self.assertGreater(resolution.node_count, 1)

        obj_ids = {n.object_id for n in resolution.nodes}
        self.assertIn("STRAT-001", obj_ids)
        self.assertIn("CERT-001", obj_ids)
        self.assertIn("TRADE-001", obj_ids)

    # ── Resolution by decision ────────────────────────────────────

    def test_resolve_by_decision(self):
        resolution = self.resolver.resolve_by_decision("DEC-001")
        self.assertGreater(resolution.node_count, 0)

        obj_ids = {n.object_id for n in resolution.nodes}
        self.assertIn("STRAT-001", obj_ids)
        self.assertIn("DEC-001", obj_ids)
        self.assertIn("TRADE-001", obj_ids)

    # ── Resolution by lineage_id ──────────────────────────────────

    def test_resolve_lineage(self):
        resolution = self.resolver.resolve_lineage("LINEAGE-001")
        self.assertEqual(resolution.direction, "forward")
        self.assertGreater(resolution.node_count, 0)

    def test_resolve_lineage_not_found(self):
        with self.assertRaises(LineageNodeNotFoundError):
            self.resolver.resolve_lineage("NONEXISTENT")

    # ── Resolution by flow ────────────────────────────────────────

    def test_resolve_by_flow_empty(self):
        results = self.resolver.resolve_by_flow("FLOW-NONEXISTENT")
        self.assertEqual(len(results), 0)

    # ── Display ───────────────────────────────────────────────────

    def test_display(self):
        resolution = self.resolver.resolve_by_order("ORDER-001")
        display = resolution.display()
        self.assertIn("Strategy", display)
        self.assertIn("STRAT-001", display)
        # backward from Order shows ancestors only (not Execution/Trade)

    # ── Multiple graphs ───────────────────────────────────────────

    def test_multiple_graphs(self):
        g2 = _build_full_lineage("LINEAGE-002")
        self.resolver.register(g2)

        r1 = self.resolver.resolve_by_order("ORDER-001")
        self.assertEqual(r1.lineage_id, "LINEAGE-001")

    def test_register_many(self):
        g2 = _build_full_lineage("LINEAGE-002")
        self.resolver.register_many([g2])
        self.assertEqual(len(self.resolver._graphs), 2)

    # ── Display for empty ─────────────────────────────────────────

    def test_display_empty(self):
        from services.integration.lineage.lineage_resolver import (
            LineageResolution,
        )
        res = LineageResolution(lineage_id="X", direction="forward")
        self.assertIn("empty lineage", res.display())

    # ── to_dict ───────────────────────────────────────────────────

    def test_resolution_to_dict(self):
        resolution = self.resolver.resolve_by_trade("TRADE-001")
        d = resolution.to_dict()
        self.assertEqual(d["direction"], "backward")
        self.assertIsInstance(d["nodes"], list)


if __name__ == '__main__':
    unittest.main()
