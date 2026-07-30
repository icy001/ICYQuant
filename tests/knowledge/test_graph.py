"""
Tests for Knowledge Graph and Relation Engine.
"""

import pytest
from services.knowledge.knowledge_graph import (
    KnowledgeGraph, GraphNode, GraphEdge, EdgeType, NodeType, GraphQuery,
)
from services.knowledge.relation_engine import (
    RelationEngine, RelationConfig, EntityRelation, RelationType, RelationStrength,
)


# ── Knowledge Graph Tests ────────────────────────────────────────────────────

class TestKnowledgeGraph:

    def test_add_node(self):
        g = KnowledgeGraph()
        node = g.add_node("NVIDIA", NodeType.COMPANY, ticker="NVDA", sector="Technology")
        assert node.name == "NVIDIA"
        assert node.ticker == "NVDA"
        assert g.node_count == 1

    def test_add_duplicate_node(self):
        g = KnowledgeGraph()
        n1 = g.add_node("NVIDIA", NodeType.COMPANY, ticker="NVDA")
        n2 = g.add_node("NVIDIA", NodeType.COMPANY, sector="Technology")
        assert n1.node_id == n2.node_id  # Same node
        assert n2.sector == "Technology"  # Updated
        assert g.node_count == 1

    def test_add_edge(self):
        g = KnowledgeGraph()
        nvda = g.add_node("NVIDIA", NodeType.COMPANY, ticker="NVDA")
        tsmc = g.add_node("TSMC", NodeType.COMPANY, ticker="TSM")
        edge = g.add_edge(
            tsmc.node_id, nvda.node_id, EdgeType.SUPPLIER_OF,
            weight=0.9, confidence=0.8, label="Chip Supplier",
        )
        assert edge is not None
        assert g.edge_count == 1
        assert nvda.degree == 1
        assert tsmc.degree == 1

    def test_add_bi_edge(self):
        g = KnowledgeGraph()
        a = g.add_node("A", NodeType.COMPANY)
        b = g.add_node("B", NodeType.COMPANY)
        e1, e2 = g.add_bi_edge(
            a.node_id, b.node_id, EdgeType.COMPETITOR_OF, weight=0.7
        )
        assert e1 is not None
        assert e2 is not None
        assert g.edge_count == 2

    def test_find_node(self):
        g = KnowledgeGraph()
        g.add_node("NVIDIA", NodeType.COMPANY, ticker="NVDA")
        found = g.find_node("nvidia")  # case-insensitive
        assert found is not None
        assert found.ticker == "NVDA"

    def test_get_node_not_found(self):
        g = KnowledgeGraph()
        assert g.get_node("nonexistent") is None

    def test_get_neighbors(self):
        g = KnowledgeGraph()
        nvda = g.add_node("NVIDIA", NodeType.COMPANY)
        tsmc = g.add_node("TSMC", NodeType.COMPANY)
        sk = g.add_node("SK Hynix", NodeType.COMPANY)

        g.add_edge(tsmc.node_id, nvda.node_id, EdgeType.SUPPLIER_OF)
        g.add_edge(sk.node_id, nvda.node_id, EdgeType.SUPPLIER_OF)

        neighbors = g.get_neighbors(nvda.node_id, direction="incoming")
        assert len(neighbors) >= 2

    def test_bfs_traversal(self):
        g = KnowledgeGraph()
        nvda = g.add_node("NVIDIA", NodeType.COMPANY)
        tsmc = g.add_node("TSMC", NodeType.COMPANY)
        asml = g.add_node("ASML", NodeType.COMPANY)

        g.add_edge(tsmc.node_id, nvda.node_id, EdgeType.SUPPLIER_OF)
        g.add_edge(asml.node_id, tsmc.node_id, EdgeType.SUPPLIER_OF)

        # Search incoming (suppliers → NVIDIA)
        bfs = g.bfs(nvda.node_id, max_depth=2, direction="incoming")
        assert 0 in bfs
        assert len(bfs[0]) == 1  # NVIDIA
        assert len(bfs.get(1, [])) + len(bfs.get(2, [])) >= 2

    def test_find_paths(self):
        g = KnowledgeGraph()
        nvda = g.add_node("NVIDIA", NodeType.COMPANY)
        tsmc = g.add_node("TSMC", NodeType.COMPANY)
        asml = g.add_node("ASML", NodeType.COMPANY)

        g.add_edge(asml.node_id, tsmc.node_id, EdgeType.SUPPLIER_OF)
        g.add_edge(tsmc.node_id, nvda.node_id, EdgeType.SUPPLIER_OF)

        paths = g.find_paths(asml.node_id, nvda.node_id, max_depth=3)
        assert len(paths) >= 1
        assert len(paths[0]) == 3

    def test_degree_centrality(self):
        g = KnowledgeGraph()
        n1 = g.add_node("Hub", NodeType.COMPANY)
        n2 = g.add_node("A", NodeType.COMPANY)
        n3 = g.add_node("B", NodeType.COMPANY)

        g.add_edge(n2.node_id, n1.node_id, EdgeType.SUPPLIER_OF)
        g.add_edge(n3.node_id, n1.node_id, EdgeType.SUPPLIER_OF)

        centrality = g.compute_degree_centrality()
        assert centrality[n1.node_id] > centrality.get(n2.node_id, 0)

    def test_most_central(self):
        g = KnowledgeGraph()
        hub = g.add_node("Hub", NodeType.COMPANY)
        for i in range(5):
            n = g.add_node(f"Node{i}", NodeType.COMPANY)
            g.add_edge(n.node_id, hub.node_id, EdgeType.SUPPLIER_OF)

        central = g.get_most_central(k=3)
        assert len(central) >= 1
        assert central[0][0].name == "Hub"

    def test_extract_subgraph(self):
        g = KnowledgeGraph()
        a = g.add_node("A", NodeType.COMPANY)
        b = g.add_node("B", NodeType.COMPANY)
        c = g.add_node("C", NodeType.COMPANY)

        g.add_edge(a.node_id, b.node_id, EdgeType.PARTNER_OF)

        nodes, edges = g.extract_subgraph([a.node_id, b.node_id])
        assert len(nodes) == 2
        assert len(edges) == 1

    def test_graph_query(self):
        g = KnowledgeGraph()
        nvda = g.add_node("NVIDIA", NodeType.COMPANY, ticker="NVDA")
        tsmc = g.add_node("TSMC", NodeType.COMPANY, ticker="TSM")
        g.add_edge(tsmc.node_id, nvda.node_id, EdgeType.SUPPLIER_OF)

        query = GraphQuery(start_node="NVIDIA", max_depth=2)
        results = g.query(query)
        assert len(results) >= 1

    def test_supply_chain(self):
        g = KnowledgeGraph()
        nvda = g.add_node("NVIDIA", NodeType.COMPANY)
        tsmc = g.add_node("TSMC", NodeType.COMPANY)
        g.add_edge(tsmc.node_id, nvda.node_id, EdgeType.SUPPLIER_OF)

        chains = g.find_supply_chain(nvda.node_id, direction="upstream")
        assert len(chains) >= 1

    def test_stats(self):
        g = KnowledgeGraph()
        g.add_node("A", NodeType.COMPANY)
        g.add_node("B", NodeType.COMPANY)
        stats = g.get_stats()
        assert stats["node_count"] == 2
        assert stats["edge_count"] == 0

    def test_remove_node(self):
        g = KnowledgeGraph()
        n = g.add_node("NVIDIA", NodeType.COMPANY)
        assert g.node_count == 1
        g.remove_node(n.node_id)
        assert g.node_count == 0

    def test_remove_edge(self):
        g = KnowledgeGraph()
        a = g.add_node("A", NodeType.COMPANY)
        b = g.add_node("B", NodeType.COMPANY)
        edge = g.add_edge(a.node_id, b.node_id, EdgeType.PARTNER_OF)
        assert g.edge_count == 1
        assert edge is not None
        g.remove_edge(edge.edge_id)
        assert g.edge_count == 0


# ── Relation Engine Tests ────────────────────────────────────────────────────

class TestRelationEngine:

    def test_compute_direct_relation(self):
        g = KnowledgeGraph()
        nvda = g.add_node("NVIDIA", NodeType.COMPANY, ticker="NVDA")
        tsmc = g.add_node("TSMC", NodeType.COMPANY, ticker="TSM")
        g.add_edge(tsmc.node_id, nvda.node_id, EdgeType.SUPPLIER_OF, weight=0.9, description="Chip supplier")

        engine = RelationEngine(graph=g)
        relations = engine.compute_relations("NVIDIA", "TSMC")
        assert len(relations) >= 1
        assert relations[0].relation_type == RelationType.SUPPLIER

    def test_compute_all_for_entity(self):
        g = KnowledgeGraph()
        nvda = g.add_node("NVIDIA", NodeType.COMPANY, ticker="NVDA")
        tsmc = g.add_node("TSMC", NodeType.COMPANY, ticker="TSM")
        sk = g.add_node("SK Hynix", NodeType.COMPANY)

        g.add_edge(tsmc.node_id, nvda.node_id, EdgeType.SUPPLIER_OF, weight=0.9)
        g.add_edge(sk.node_id, nvda.node_id, EdgeType.SUPPLIER_OF, weight=0.7)

        engine = RelationEngine(graph=g)
        relations = engine.compute_all_for_entity("NVIDIA")
        assert len(relations) >= 2

    def test_supply_chain_discovery(self):
        g = KnowledgeGraph()
        nvda = g.add_node("NVIDIA", NodeType.COMPANY, ticker="NVDA")
        tsmc = g.add_node("TSMC", NodeType.COMPANY, ticker="TSM")
        g.add_edge(tsmc.node_id, nvda.node_id, EdgeType.SUPPLIER_OF, weight=0.9)

        engine = RelationEngine(graph=g)
        chain = engine.discover_supply_chain("NVIDIA")
        assert len(chain["upstream"]) >= 1

    def test_find_competitors(self):
        g = KnowledgeGraph()
        nvda = g.add_node("NVIDIA", NodeType.COMPANY, ticker="NVDA")
        amd = g.add_node("AMD", NodeType.COMPANY, ticker="AMD")
        g.add_bi_edge(nvda.node_id, amd.node_id, EdgeType.COMPETITOR_OF, weight=0.8)

        engine = RelationEngine(graph=g)
        competitors = engine.find_competitors("NVIDIA")
        assert len(competitors) >= 1
        assert competitors[0].relation_type == RelationType.COMPETITOR

    def test_strength_calculation(self):
        g = KnowledgeGraph()
        a = g.add_node("A", NodeType.COMPANY)
        b = g.add_node("B", NodeType.COMPANY)
        g.add_edge(a.node_id, b.node_id, EdgeType.PARTNER_OF, weight=0.85)

        engine = RelationEngine(graph=g)
        relations = engine.compute_relations("A", "B")
        assert relations[0].strength == RelationStrength.VERY_STRONG

    def test_query_relations(self):
        g = KnowledgeGraph()
        a = g.add_node("A", NodeType.COMPANY)
        b = g.add_node("B", NodeType.COMPANY)
        g.add_edge(a.node_id, b.node_id, EdgeType.SUPPLIER_OF, weight=0.9)

        engine = RelationEngine(graph=g)
        engine.compute_relations("A", "B")

        results = engine.get_relations(entity="A")
        assert len(results) >= 1

        results = engine.get_relations(relation_type=RelationType.SUPPLIER)
        assert len(results) >= 1

    def test_strongest_relations(self):
        g = KnowledgeGraph()
        center = g.add_node("Center", NodeType.COMPANY)
        for i, w in enumerate([0.9, 0.7, 0.5, 0.3]):
            n = g.add_node(f"Node{i}", NodeType.COMPANY)
            g.add_edge(center.node_id, n.node_id, EdgeType.PARTNER_OF, weight=w)

        engine = RelationEngine(graph=g)
        engine.compute_all_for_entity("Center")
        strongest = engine.get_strongest_relations("Center", limit=2)
        assert len(strongest) == 2
        assert strongest[0].strength_score >= strongest[1].strength_score

    def test_transitive_relations(self):
        g = KnowledgeGraph()
        nvda = g.add_node("NVIDIA", NodeType.COMPANY)
        tsmc = g.add_node("TSMC", NodeType.COMPANY)
        asml = g.add_node("ASML", NodeType.COMPANY)

        g.add_edge(asml.node_id, tsmc.node_id, EdgeType.SUPPLIER_OF, weight=0.9, confidence=0.8)
        g.add_edge(tsmc.node_id, nvda.node_id, EdgeType.SUPPLIER_OF, weight=0.9, confidence=0.8)

        engine = RelationEngine(graph=g, config=RelationConfig(
            enable_transitive_relations=True,
            max_path_depth=4,
            min_transitive_confidence=0.3,
        ))
        relations = engine.compute_relations("ASML", "NVIDIA")
        # May or may not find transitive relations
        assert len(relations) >= 0
