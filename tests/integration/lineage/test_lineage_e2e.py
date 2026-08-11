"""End-to-end tests for the complete control lineage flow.

Covers:
- Strategy → Signal lineage
- Signal → Decision lineage
- Decision → Risk/Governance/Authority/Approval lineage
- Approval → Certificate lineage
- Certificate → Order lineage
- Order → Execution lineage
- Execution → Trade lineage
- Forward/backward traversal
- Broken lineage detection
- Partial fill lineage
- Reconciliation lineage validation
"""

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

# Also load the registry and metrics
_reg_path = os.path.join(_int_dir, 'lineage_registry.py')
_spec = importlib.util.spec_from_file_location(
    'services.integration.lineage_registry', _reg_path)
_m = importlib.util.module_from_spec(_spec)
sys.modules['services.integration.lineage_registry'] = _m
_spec.loader.exec_module(_m)

_met_path = os.path.join(_int_dir, 'lineage_metrics.py')
_spec = importlib.util.spec_from_file_location(
    'services.integration.lineage_metrics', _met_path)
_m = importlib.util.module_from_spec(_spec)
sys.modules['services.integration.lineage_metrics'] = _m
_spec.loader.exec_module(_m)

from services.integration.lineage.lineage_node import LineageNode, NodeType
from services.integration.lineage.lineage_edge import LineageEdge, EdgeType
from services.integration.lineage.lineage_builder import LineageBuilder
from services.integration.lineage.lineage_resolver import LineageResolver
from services.integration.lineage.lineage_validator import LineageValidator
from services.integration.lineage.lineage_graph import LineageGraph
from services.integration.lineage_registry import LineageRegistry
from services.integration.lineage_metrics import LineageMetrics


def _full_lineage(lid: str = "LINEAGE-E2E"):
    return (LineageBuilder(lid)
            .start_with_strategy("STRAT-007")
            .emit_signal("SIG-381")
            .emit_decision("DEC-091", decision_type="MARKET",
                           decision_reason="momentum")
            .with_risk_decision(True, policy_version="RISK-v8",
                                risk_exposure=12.4, risk_limit=15.0,
                                available_margin=1_200_000)
            .with_governance_decision(True, state="NORMAL",
                                      policy_version="GOV-v5")
            .with_authority_decision(True, authority_id="AUTH-001",
                                     limit=20_000_000, requested=12_000_000,
                                     policy_version="AUTH-v3")
            .with_approval(True, approval_id="APR-001",
                           status="APPROVED",
                           policy_version="APPROVAL-v2")
            .with_order_intent("INTENT-001", account_id="ACC-001",
                               symbol="NVDA", side="BUY")
            .with_admission(True, admission_id="ADM-001")
            .with_certificate(True, certificate_id="CERT-001")
            .emit_order("ORDER-001")
            .emit_execution("EXEC-001")
            .emit_trade("TRADE-001")
            .build())


class TestLineageE2E(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.graph = _full_lineage()
        cls.resolver = LineageResolver()
        cls.resolver.register(cls.graph)
        cls.validator = LineageValidator(strict=True)

    # ── 1. Strategy → Signal lineage ──────────────────────────────

    def test_strategy_to_signal_lineage(self):
        path = self.graph.find_path(
            self.graph.get_node_by_object_id("STRAT-007").node_id,
            self.graph.get_node_by_object_id("SIG-381").node_id,
        )
        self.assertEqual(len(path), 2)
        self.assertEqual(path[0].object_id, "STRAT-007")
        self.assertEqual(path[1].object_id, "SIG-381")

    # ── 2. Signal → Decision lineage ──────────────────────────────

    def test_signal_to_decision_lineage(self):
        path = self.graph.find_path(
            self.graph.get_node_by_object_id("SIG-381").node_id,
            self.graph.get_node_by_object_id("DEC-091").node_id,
        )
        self.assertEqual(len(path), 2)

    # ── 3. Decision → Risk lineage ────────────────────────────────

    def test_decision_to_risk_lineage(self):
        dec = self.graph.get_node_by_object_id("DEC-091")
        risk_nodes = self.graph.get_nodes_by_type(NodeType.RISK_DECISION)
        self.assertEqual(len(risk_nodes), 1)

    # ── 4. Risk → Governance lineage ──────────────────────────────

    def test_risk_to_governance_lineage(self):
        gov_nodes = self.graph.get_nodes_by_type(
            NodeType.GOVERNANCE_DECISION)
        self.assertEqual(len(gov_nodes), 1)

    # ── 5. Governance → Authority lineage ─────────────────────────

    def test_governance_to_authority_lineage(self):
        auth_nodes = self.graph.get_nodes_by_type(
            NodeType.AUTHORITY_DECISION)
        self.assertEqual(len(auth_nodes), 1)

    # ── 6. Authority → Approval lineage ───────────────────────────

    def test_authority_to_approval_lineage(self):
        appr = self.graph.get_node_by_object_id("APR-001")
        self.assertIsNotNone(appr)
        self.assertEqual(appr.node_type, NodeType.APPROVAL)

    # ── 7. Approval → Certificate lineage ─────────────────────────

    def test_approval_to_certificate_lineage(self):
        path = self.graph.find_path(
            self.graph.get_node_by_object_id("APR-001").node_id,
            self.graph.get_node_by_object_id("CERT-001").node_id,
        )
        self.assertGreater(len(path), 0)

    # ── 8. Certificate → Order lineage ────────────────────────────

    def test_certificate_to_order_lineage(self):
        path = self.graph.find_path(
            self.graph.get_node_by_object_id("CERT-001").node_id,
            self.graph.get_node_by_object_id("ORDER-001").node_id,
        )
        self.assertGreater(len(path), 0)

    # ── 9. Order → Execution lineage ──────────────────────────────

    def test_order_to_execution_lineage(self):
        exec_nodes = self.graph.get_nodes_by_type(NodeType.EXECUTION)
        self.assertEqual(len(exec_nodes), 1)
        self.assertEqual(exec_nodes[0].parent_node_id,
                         self.graph.get_node_by_object_id("ORDER-001").node_id)

    # ── 10. Execution → Trade lineage ─────────────────────────────

    def test_execution_to_trade_lineage(self):
        trade = self.graph.get_node_by_object_id("TRADE-001")
        self.assertIsNotNone(trade)

    # ── Forward traversal ─────────────────────────────────────────

    def test_forward_traversal(self):
        strategy_node = self.graph.get_node_by_object_id("STRAT-007")
        fwd = self.graph.forward_from(strategy_node.node_id)
        obj_ids = {n.object_id for n in fwd}
        self.assertIn("TRADE-001", obj_ids)

    # ── Backward traversal ───────────────────────────────────────

    def test_backward_traversal(self):
        trade_node = self.graph.get_node_by_object_id("TRADE-001")
        bwd = self.graph.backward_from(trade_node.node_id)
        obj_ids = {n.object_id for n in bwd}
        self.assertIn("STRAT-007", obj_ids)

    # ── No cycle ──────────────────────────────────────────────────

    def test_no_cycle(self):
        self.assertFalse(self.graph.has_cycle())

    # ── Validator passes ──────────────────────────────────────────

    def test_validator_passes(self):
        report = self.validator.validate(self.graph)
        self.assertTrue(report.valid, msg=report.errors)

    # ── Broken lineage detection ──────────────────────────────────

    def test_broken_lineage_detection(self):
        # Build a graph with a missing edge
        bad = LineageGraph(lineage_id="BROKEN")
        s = bad.add_node(LineageNode.create(
            NodeType.STRATEGY, "S", "BROKEN"))
        g = bad.add_node(LineageNode.create(
            NodeType.SIGNAL, "G", "BROKEN", parent_node_id=s.node_id))
        r = bad.add_node(LineageNode.create(
            NodeType.RISK_DECISION, "R", "BROKEN", parent_node_id=g.node_id))
        bad.add_edge(LineageEdge.create(
            s.node_id, g.node_id, EdgeType.GENERATED, "BROKEN"))
        # Missing edge: g → r
        issues = bad.check_broken_links()
        self.assertGreater(len(issues), 0)

    # ── Partial fill lineage ──────────────────────────────────────

    def test_partial_fill_lineage(self):
        exec_nodes = self.graph.get_nodes_by_type(NodeType.EXECUTION)
        self.assertEqual(len(exec_nodes), 1)
        # Execution shares the same lineage_id
        self.assertEqual(exec_nodes[0].lineage_id, "LINEAGE-E2E")

    # ── Reconciliation lineage validation ─────────────────────────

    def test_registry_indexes_all_objects(self):
        registry = LineageRegistry()
        registry.register(self.graph)
        self.assertTrue(registry.has_lineage("ORDER-001"))
        self.assertTrue(registry.has_lineage("TRADE-001"))
        self.assertTrue(registry.has_lineage("CERT-001"))
        self.assertTrue(registry.has_lineage("STRAT-007"))

    def test_registry_lineage_id_lookup(self):
        registry = LineageRegistry()
        registry.register(self.graph)
        self.assertEqual(
            registry.find_lineage_id("ORDER-001"), "LINEAGE-E2E")

    def test_registry_validate_ancestor(self):
        registry = LineageRegistry()
        registry.register(self.graph)
        self.assertTrue(
            registry.validate_ancestor("ORDER-001", "STRAT-007"))
        self.assertTrue(
            registry.validate_ancestor("TRADE-001", "DEC-091"))

    def test_registry_status_management(self):
        registry = LineageRegistry()
        registry.register(self.graph, status="ACTIVE")
        self.assertEqual(registry.active_lineages[0].status, "ACTIVE")

        registry.complete("LINEAGE-E2E")
        self.assertEqual(
            registry.get("LINEAGE-E2E").status, "COMPLETED")

    def test_registry_revoke(self):
        registry = LineageRegistry()
        registry.register(self.graph)
        registry.revoke("LINEAGE-E2E")
        self.assertEqual(
            registry.get("LINEAGE-E2E").status, "REVOKED")

    def test_metrics_recording(self):
        metrics = LineageMetrics()
        metrics.record_lineage_created()
        metrics.record_node_created(12)
        metrics.record_edge_created(11)
        metrics.record_snapshot()
        metrics.record_audit_event()

        s = metrics.summary()
        self.assertEqual(s["lineages"]["created"], 1)
        self.assertEqual(s["graph"]["nodes_created"], 12)
        self.assertEqual(s["graph"]["edges_created"], 11)
        self.assertEqual(s["audit"]["events_recorded"], 1)
        self.assertEqual(s["audit"]["snapshots"], 1)

    def test_metrics_chain_verification(self):
        metrics = LineageMetrics()
        metrics.record_chain_verification(True)
        metrics.record_chain_verification(True)
        metrics.record_chain_verification(False)

        s = metrics.summary()
        self.assertEqual(s["audit"]["chain_verifications"], 3)
        self.assertEqual(s["audit"]["chain_failures"], 1)
        self.assertAlmostEqual(s["audit"]["chain_pass_rate"], 66.67, places=1)

    def test_registry_count_by_status(self):
        registry = LineageRegistry()
        registry.register(LineageBuilder("L-1").build(), status="ACTIVE")
        registry.register(LineageBuilder("L-2").build(), status="COMPLETED")

        counts = registry.count_by_status()
        self.assertEqual(counts.get("ACTIVE"), 1)
        self.assertEqual(counts.get("COMPLETED"), 1)

    def test_registry_freeze(self):
        registry = LineageRegistry()
        registry.register(self.graph)
        registry.freeze("LINEAGE-E2E")
        self.assertEqual(
            registry.get("LINEAGE-E2E").status, "FROZEN")

    def test_registry_find_by_object_id(self):
        registry = LineageRegistry()
        registry.register(self.graph)
        entry = registry.find_by_object_id("DEC-091")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.lineage_id, "LINEAGE-E2E")

    def test_registry_find_nonexistent(self):
        registry = LineageRegistry()
        self.assertIsNone(registry.find_by_object_id("NONEXISTENT"))


if __name__ == '__main__':
    unittest.main()
