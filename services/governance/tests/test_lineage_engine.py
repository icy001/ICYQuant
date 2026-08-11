"""
Test LineageEngine — node/edge recording and resolution.
"""

import pytest

from services.governance.lineage_node import LineageNode, LineageNodeType
from services.governance.lineage_edge import LineageEdge, LineageEdgeType
from services.governance.lineage_graph import LineageGraph
from services.governance.lineage_resolver import LineageResolver
from services.governance.lineage_engine import LineageEngine


class TestLineageNode:
    """Test lineage node creation."""

    def test_create_node(self):
        node = LineageNode.create(
            node_type=LineageNodeType.DECISION,
            entity_type="DECISION",
            entity_id="DEC-001",
            correlation_id="CORR-001",
        )
        assert node.node_id.startswith("NODE-")
        assert node.node_type == LineageNodeType.DECISION
        assert node.entity_id == "DEC-001"
        assert node.correlation_id == "CORR-001"

    def test_node_to_from_dict(self):
        node = LineageNode.create(
            node_type=LineageNodeType.POLICY,
            entity_type="POLICY",
            entity_id="POL-001",
            state={"version": "v3", "verdict": "ALLOW"},
            correlation_id="CORR-002",
        )
        d = node.to_dict()
        restored = LineageNode.from_dict(d)
        assert restored.node_id == node.node_id
        assert restored.node_type == LineageNodeType.POLICY
        assert restored.state["version"] == "v3"

    def test_node_type_properties(self):
        assert LineageNodeType.MARKET.is_source is True
        assert LineageNodeType.HUMAN_OVERRIDE.is_source is True
        assert LineageNodeType.LEDGER.is_sink is True
        assert LineageNodeType.POSITION.is_sink is True
        assert LineageNodeType.DECISION.is_source is False
        assert LineageNodeType.DECISION.is_sink is False


class TestLineageEdge:
    """Test lineage edge creation."""

    def test_create_edge(self):
        edge = LineageEdge.create(
            edge_type=LineageEdgeType.GENERATED,
            source_node_id="NODE-A",
            target_node_id="NODE-B",
        )
        assert edge.edge_id.startswith("EDGE-")
        assert edge.edge_type == LineageEdgeType.GENERATED
        assert edge.source_node_id == "NODE-A"
        assert edge.target_node_id == "NODE-B"

    def test_edge_type_properties(self):
        assert LineageEdgeType.GENERATED.is_causal is True
        assert LineageEdgeType.CAUSED.is_causal is True
        assert LineageEdgeType.AUTHORIZED_BY.is_authority is True
        assert LineageEdgeType.APPROVED_BY.is_authority is True
        assert LineageEdgeType.USED.is_causal is False


class TestLineageGraph:
    """Test lineage graph operations."""

    def test_add_nodes(self):
        graph = LineageGraph()
        n1 = LineageNode.create(LineageNodeType.SIGNAL, "SIGNAL", "SIG-001")
        n2 = LineageNode.create(LineageNodeType.DECISION, "DECISION", "DEC-001")
        graph.add_node(n1)
        graph.add_node(n2)
        assert graph.node_count == 2

    def test_connect_nodes(self):
        graph = LineageGraph()
        n1 = graph.add_node(LineageNode.create(LineageNodeType.DECISION, "DECISION", "DEC-001"))
        n2 = graph.add_node(LineageNode.create(LineageNodeType.POLICY, "POLICY", "POL-001"))
        edge = graph.connect(n1.node_id, n2.node_id, LineageEdgeType.EVALUATED_BY)
        assert graph.edge_count == 1
        assert edge.edge_type == LineageEdgeType.EVALUATED_BY

    def test_upstream_downstream(self):
        graph = LineageGraph()
        market = graph.add_node(LineageNode.create(LineageNodeType.MARKET, "MARKET", "NVDA"))
        signal = graph.add_node(LineageNode.create(LineageNodeType.SIGNAL, "SIGNAL", "SIG-001"))
        decision = graph.add_node(LineageNode.create(LineageNodeType.DECISION, "DECISION", "DEC-001"))

        graph.connect(market.node_id, signal.node_id, LineageEdgeType.GENERATED)
        graph.connect(signal.node_id, decision.node_id, LineageEdgeType.GENERATED)

        upstream = graph.get_upstream(decision.node_id)
        assert len(upstream) == 2

        downstream = graph.get_downstream(market.node_id)
        assert len(downstream) == 2

    def test_find_orphans(self):
        graph = LineageGraph()
        n1 = graph.add_node(LineageNode.create(LineageNodeType.DECISION, "DECISION", "DEC-001"))
        graph.add_node(LineageNode.create(LineageNodeType.POLICY, "POLICY", "POL-001"))
        # POL is orphan (not connected, not source)
        orphans = graph.find_orphans()
        assert len(orphans) >= 1


class TestLineageEngine:
    """Test lineage engine recording and resolution."""

    def test_record_chain(self):
        engine = LineageEngine()

        nodes_data = [
            {"node_type": LineageNodeType.MARKET, "entity_type": "MARKET", "entity_id": "NVDA"},
            {"node_type": LineageNodeType.SIGNAL, "entity_type": "SIGNAL", "entity_id": "SIG-001",
             "edge_type": LineageEdgeType.GENERATED},
            {"node_type": LineageNodeType.DECISION, "entity_type": "DECISION", "entity_id": "DEC-001",
             "edge_type": LineageEdgeType.GENERATED},
        ]
        nodes = engine.record_chain(nodes_data, correlation_id="CORR-001")
        assert len(nodes) == 3
        assert engine.node_count == 3
        assert engine.edge_count == 2

    def test_resolve_backward(self):
        engine = LineageEngine()
        nodes_data = [
            {"node_type": LineageNodeType.MARKET, "entity_type": "MARKET", "entity_id": "NVDA"},
            {"node_type": LineageNodeType.SIGNAL, "entity_type": "SIGNAL", "entity_id": "SIG-001",
             "edge_type": LineageEdgeType.GENERATED},
            {"node_type": LineageNodeType.DECISION, "entity_type": "DECISION", "entity_id": "DEC-001",
             "edge_type": LineageEdgeType.GENERATED},
        ]
        nodes = engine.record_chain(nodes_data, "CORR-001")
        decision_node_id = nodes[-1].node_id

        result = engine.resolve_backward(decision_node_id)
        assert result["direction"] == "BACKWARD"
        assert len(result["chain"]) == 2  # Market, Signal

    def test_check_completeness(self):
        engine = LineageEngine()
        nodes_data = [
            {"node_type": LineageNodeType.DECISION, "entity_type": "DECISION", "entity_id": "DEC-001",
             "edge_type": LineageEdgeType.GENERATED},
            {"node_type": LineageNodeType.POLICY, "entity_type": "POLICY", "entity_id": "POL-001",
             "edge_type": LineageEdgeType.EVALUATED_BY},
            {"node_type": LineageNodeType.AUTHORITY, "entity_type": "AUTHORITY", "entity_id": "AUTH-001",
             "edge_type": LineageEdgeType.AUTHORIZED_BY},
        ]
        engine.record_chain(nodes_data, "CORR-001")

        result = engine.check_completeness("CORR-001")
        assert result["complete"] is True

    def test_detect_orphans(self):
        engine = LineageEngine()
        engine.record_node(LineageNodeType.POLICY, "POLICY", "POL-001")
        engine.record_node(LineageNodeType.DECISION, "DECISION", "DEC-001")

        result = engine.detect_orphans()
        assert "orphan_count" in result
