"""Tests for Institutional Knowledge Graph Engine."""

from datetime import date

import pytest

from services.assessment.calculator import DateDeltaCalculator, TemporalBiasConfig
from services.knowledge_graph import (
    CausalGraphEngine,
    Entity,
    EntityRegistry,
    EntityType,
    EventPropagationEngine,
    FactorGraph,
    GraphBuilder,
    GraphMemory,
    GraphQueryEngine,
    KnowledgeGraphService,
    PortfolioGraph,
    RelationshipManager,
    RelationType,
)


# ---------------------------------------------------------------------------
# Entity & Registry
# ---------------------------------------------------------------------------

class TestEntity:
    def test_create(self):
        e = Entity(id="NVDA", name="NVIDIA Corp", entity_type=EntityType.STOCK)
        assert e.id == "NVDA"
        assert e.name == "NVIDIA Corp"
        assert e.entity_type == EntityType.STOCK

    def test_is_financial_instrument(self):
        stock = Entity("NVDA", "NVIDIA", EntityType.STOCK)
        etf = Entity("SPY", "SPY ETF", EntityType.ETF)
        sector = Entity("SEMI", "Semiconductor", EntityType.SECTOR)
        assert stock.is_financial_instrument is True
        assert etf.is_financial_instrument is True
        assert sector.is_financial_instrument is False

    def test_is_market_indicator(self):
        idx = Entity("SPX", "S&P 500", EntityType.INDEX)
        factor = Entity("MOM", "Momentum", EntityType.FACTOR)
        stock = Entity("NVDA", "NVIDIA", EntityType.STOCK)
        assert idx.is_market_indicator is True
        assert factor.is_market_indicator is True
        assert stock.is_market_indicator is False

    def test_to_dict(self):
        e = Entity("NVDA", "NVIDIA", EntityType.STOCK, ticker="NVDA", sector="Tech")
        d = e.to_dict()
        assert d["id"] == "NVDA"
        assert d["ticker"] == "NVDA"
        assert d["sector"] == "Tech"

    def test_optional_fields_none(self):
        e = Entity("TEST", "Test", EntityType.STOCK)
        assert e.ticker is None
        assert e.sector is None


class TestEntityRegistry:
    def test_register_and_get(self):
        reg = EntityRegistry()
        e = Entity("NVDA", "NVIDIA", EntityType.STOCK)
        reg.register(e)
        assert reg.get("NVDA") is e
        assert reg.exists("NVDA") is True

    def test_unregister(self):
        reg = EntityRegistry()
        e = Entity("NVDA", "NVIDIA", EntityType.STOCK)
        reg.register(e)
        reg.unregister("NVDA")
        assert reg.exists("NVDA") is False

    def test_get_by_type(self):
        reg = EntityRegistry()
        reg.register(Entity("NVDA", "NVIDIA", EntityType.STOCK))
        reg.register(Entity("AAPL", "Apple", EntityType.STOCK))
        reg.register(Entity("SPY", "SPY", EntityType.ETF))
        assert len(reg.get_by_type(EntityType.STOCK)) == 2
        assert len(reg.get_by_type(EntityType.ETF)) == 1

    def test_search(self):
        reg = EntityRegistry()
        reg.register(Entity("NVDA", "NVIDIA Corp", EntityType.STOCK))
        reg.register(Entity("AAPL", "Apple Inc", EntityType.STOCK))
        results = reg.search("nvidia")
        assert len(results) == 1
        assert results[0].id == "NVDA"

    def test_entity_count(self):
        reg = EntityRegistry()
        assert reg.entity_count == 0
        reg.register(Entity("A", "A", EntityType.STOCK))
        reg.register(Entity("B", "B", EntityType.STOCK))
        assert reg.entity_count == 2


# ---------------------------------------------------------------------------
# Graph Builder
# ---------------------------------------------------------------------------

class TestGraphBuilder:
    def test_add_node(self):
        gb = GraphBuilder()
        e = Entity("NVDA", "NVIDIA", EntityType.STOCK)
        gb.add_node(e)
        assert "NVDA" in gb.nodes
        assert gb.node_count == 1

    def test_add_edge(self):
        gb = GraphBuilder()
        gb.add_node(Entity("A", "A", EntityType.STOCK))
        gb.add_node(Entity("B", "B", EntityType.STOCK))
        gb.add_edge("A", "B", "supplier", 0.8)
        assert gb.edge_count == 1

    def test_add_bidirectional_edge(self):
        gb = GraphBuilder()
        gb.add_node(Entity("A", "A", EntityType.STOCK))
        gb.add_node(Entity("B", "B", EntityType.STOCK))
        edges = gb.add_bidirectional_edge("A", "B", "correlates_with")
        assert gb.edge_count == 2

    def test_get_neighbors(self):
        gb = GraphBuilder()
        for eid in ["A", "B", "C"]:
            gb.add_node(Entity(eid, eid, EntityType.STOCK))
        gb.add_edge("A", "B", "supplier")
        gb.add_edge("A", "C", "customer")
        neighbors = gb.get_neighbors("A")
        assert len(neighbors) == 2
        assert ("B", "supplier", 1.0) in neighbors

    def test_get_incoming(self):
        gb = GraphBuilder()
        for eid in ["A", "B"]:
            gb.add_node(Entity(eid, eid, EntityType.STOCK))
        gb.add_edge("A", "B", "supplier")
        incoming = gb.get_incoming("B")
        assert len(incoming) == 1
        assert incoming[0][0] == "A"

    def test_get_all_relations(self):
        gb = GraphBuilder()
        for eid in ["A", "B", "C"]:
            gb.add_node(Entity(eid, eid, EntityType.STOCK))
        gb.add_edge("A", "B", "supplier")
        gb.add_edge("C", "A", "customer")
        all_rel = gb.get_all_relations("A")
        assert len(all_rel) == 2

    def test_remove_node(self):
        gb = GraphBuilder()
        gb.add_node(Entity("A", "A", EntityType.STOCK))
        gb.add_node(Entity("B", "B", EntityType.STOCK))
        gb.add_edge("A", "B", "supplier")
        gb.remove_node("A")
        assert gb.node_count == 1
        assert gb.edge_count == 0

    def test_remove_edge(self):
        gb = GraphBuilder()
        for eid in ["A", "B"]:
            gb.add_node(Entity(eid, eid, EntityType.STOCK))
        gb.add_edge("A", "B", "supplier")
        assert gb.remove_edge("A", "B", "supplier") is True
        assert gb.edge_count == 0

    def test_adjacency_list(self):
        gb = GraphBuilder()
        for eid in ["A", "B"]:
            gb.add_node(Entity(eid, eid, EntityType.STOCK))
        gb.add_edge("A", "B", "supplier")
        adj = gb.adjacency_list()
        assert "A" in adj
        assert "B" not in adj  # no outgoing edges

    def test_to_dict(self):
        gb = GraphBuilder()
        gb.add_node(Entity("A", "Alpha", EntityType.STOCK))
        gb.add_edge("A", "A", "related_to")  # self-loop
        d = gb.to_dict()
        assert d["node_count"] == 1
        assert d["edge_count"] == 1
        assert "nodes" in d

    def test_subgraph(self):
        gb = GraphBuilder()
        for eid in ["A", "B", "C"]:
            gb.add_node(Entity(eid, eid, EntityType.STOCK))
        gb.add_edge("A", "B", "supplier")
        gb.add_edge("B", "C", "customer")
        sub = gb.subgraph({"A", "B"})
        assert sub.node_count == 2
        assert sub.edge_count == 1  # A→B included, B→C excluded


# ---------------------------------------------------------------------------
# Relationship Manager
# ---------------------------------------------------------------------------

class TestRelationshipManager:
    def test_create(self):
        rm = RelationshipManager()
        r = rm.create("A", "B", "supplier", 0.9)
        assert r["source"] == "A"
        assert r["target"] == "B"
        assert r["relation"] == "supplier"
        assert r["weight"] == 0.9

    def test_validate_relation(self):
        rm = RelationshipManager()
        assert rm.validate_relation("supplier") is True
        assert rm.validate_relation("invalid_type") is False

    def test_is_transitive(self):
        rm = RelationshipManager()
        assert rm.is_transitive("supplier") is True
        assert rm.is_transitive("correlates_with") is True
        assert rm.is_transitive("competitor") is False

    def test_build_supply_chain(self):
        rm = RelationshipManager()
        relations = rm.build_supply_chain("AAPL", ["TSMC", "FOXCONN"], ["BESTBUY"])
        assert len(relations) == 3

    def test_build_index_membership(self):
        rm = RelationshipManager()
        relations = rm.build_index_membership("SPX", ["AAPL", "MSFT", "NVDA"])
        assert len(relations) == 3

    def test_build_factor_exposure(self):
        rm = RelationshipManager()
        relations = rm.build_factor_exposure("NVDA", {"momentum": 0.7, "volatility": 0.3})
        assert len(relations) == 2

    def test_build_causal_chain(self):
        rm = RelationshipManager()
        relations = rm.build_causal_chain(["Oil", "Inflation", "Rate", "Growth"])
        assert len(relations) == 3


# ---------------------------------------------------------------------------
# Graph Query Engine
# ---------------------------------------------------------------------------

class TestGraphQueryEngine:
    @pytest.fixture
    def graph(self):
        gb = GraphBuilder()
        for eid in ["A", "B", "C", "D", "E"]:
            gb.add_node(Entity(eid, eid, EntityType.STOCK))
        gb.add_edge("A", "B", "supplier")
        gb.add_edge("A", "C", "customer")
        gb.add_edge("B", "D", "supplier")
        gb.add_edge("C", "D", "competitor")
        gb.add_edge("D", "E", "supplier")
        return gb

    def test_neighbors(self, graph):
        qe = GraphQueryEngine()
        nbrs = qe.neighbors(graph, "A")
        assert len(nbrs) == 2
        assert "B" in nbrs
        assert "C" in nbrs

    def test_neighbors_with_relations(self, graph):
        qe = GraphQueryEngine()
        nbrs = qe.neighbors_with_relations(graph, "A")
        assert len(nbrs) == 2

    def test_all_neighbors(self, graph):
        qe = GraphQueryEngine()
        nbrs = qe.all_neighbors(graph, "B")
        assert "A" in nbrs  # incoming
        assert "D" in nbrs  # outgoing

    def test_shortest_path(self, graph):
        qe = GraphQueryEngine()
        path = qe.shortest_path(graph, "A", "E")
        assert path == ["A", "B", "D", "E"]

    def test_shortest_path_same_node(self, graph):
        qe = GraphQueryEngine()
        path = qe.shortest_path(graph, "A", "A")
        assert path == ["A"]

    def test_shortest_path_no_path(self, graph):
        qe = GraphQueryEngine()
        # E has no outgoing edges
        path = qe.shortest_path(graph, "E", "A")
        assert path is None

    def test_find_paths_by_relation(self, graph):
        qe = GraphQueryEngine()
        paths = qe.find_paths_by_relation(graph, "A", "supplier")
        assert len(paths) >= 1  # A→B

    def test_subgraph_around(self, graph):
        qe = GraphQueryEngine()
        sub = qe.subgraph_around(graph, "A", depth=1)
        assert sub.node_count >= 2  # A + B + C

    def test_degree_centrality(self, graph):
        qe = GraphQueryEngine()
        centrality = qe.degree_centrality(graph)
        assert centrality["A"] == 2  # A→B, A→C
        assert centrality["D"] == 3  # B→D, C→D, D→E

    def test_top_central_nodes(self, graph):
        qe = GraphQueryEngine()
        top = qe.top_central_nodes(graph, n=2)
        assert len(top) == 2
        assert top[0][1] >= top[1][1]

    def test_find_by_relation(self, graph):
        qe = GraphQueryEngine()
        suppliers = qe.find_by_relation(graph, "A", "supplier")
        assert "B" in suppliers


# ---------------------------------------------------------------------------
# Event Propagation Engine
# ---------------------------------------------------------------------------

class TestEventPropagation:
    def test_propagate_basic(self):
        engine = EventPropagationEngine()
        result = engine.propagate("Fed Rate Cut")
        assert result["event"] == "Fed Rate Cut"
        assert result["status"] == "PROPAGATED"

    def test_propagate_through_graph(self):
        gb = GraphBuilder()
        for eid in ["Oil", "Inflation", "Growth"]:
            gb.add_node(Entity(eid, eid, EntityType.MACRO_EVENT))
        gb.add_edge("Oil", "Inflation", "causes", 1.0)
        gb.add_edge("Inflation", "Growth", "causes", 0.8)

        engine = EventPropagationEngine(max_depth=3, decay_factor=0.7)
        result = engine.propagate_through_graph(gb, "Oil", 1.0)
        assert result["status"] == "PROPAGATED"
        assert result["affected_count"] >= 1

    def test_propagate_unknown_source(self):
        gb = GraphBuilder()
        engine = EventPropagationEngine()
        result = engine.propagate_through_graph(gb, "Unknown", 1.0)
        assert result["status"] == "UNKNOWN_SOURCE"

    def test_find_influence_path(self):
        gb = GraphBuilder()
        for eid in ["A", "B", "C"]:
            gb.add_node(Entity(eid, eid, EntityType.MACRO_EVENT))
        gb.add_edge("A", "B", "causes")
        gb.add_edge("B", "C", "affects")
        engine = EventPropagationEngine()
        path = engine.find_influence_path(gb, "A", "C")
        assert path == ["A", "B", "C"]

    def test_find_influence_path_filtered(self):
        gb = GraphBuilder()
        for eid in ["A", "B", "C"]:
            gb.add_node(Entity(eid, eid, EntityType.MACRO_EVENT))
        gb.add_edge("A", "B", "causes")
        gb.add_edge("B", "C", "affects")
        engine = EventPropagationEngine()
        path = engine.find_influence_path(gb, "A", "C", relation_filter="causes")
        assert path is None  # B→C is "affects", not "causes"


# ---------------------------------------------------------------------------
# Causal Graph Engine
# ---------------------------------------------------------------------------

class TestCausalGraph:
    def test_infer_basic(self):
        engine = CausalGraphEngine()
        result = engine.infer("Oil Shock")
        assert result["cause"] == "Oil Shock"
        assert result["effect"] == "UNKNOWN"

    def test_add_causal_link(self):
        engine = CausalGraphEngine()
        engine.add_causal_link("Oil", "Inflation", 0.9)
        effects = engine.get_effects("Oil")
        assert len(effects) == 1
        assert effects[0] == ("Inflation", 0.9)

    def test_add_causal_chain(self):
        engine = CausalGraphEngine()
        engine.add_causal_chain(["Oil", "Inflation", "Rate", "Growth"], 0.8)
        assert engine.link_count == 3

    def test_get_causes(self):
        engine = CausalGraphEngine()
        engine.add_causal_link("Oil", "Inflation", 0.9)
        engine.add_causal_link("War", "Oil", 0.7)
        causes = engine.get_causes("Oil")
        assert len(causes) == 1
        assert causes[0][0] == "War"

    def test_downstream_effects(self):
        engine = CausalGraphEngine()
        engine.add_causal_chain(["Oil", "Inflation", "Rate"], 0.8)
        effects = engine.downstream_effects("Oil", max_depth=3)
        assert len(effects) == 2  # Inflation, Rate
        assert effects[0]["entity"] == "Inflation"
        assert effects[1]["entity"] == "Rate"

    def test_upstream_causes(self):
        engine = CausalGraphEngine()
        engine.add_causal_chain(["Oil", "Inflation", "Rate"], 0.8)
        causes = engine.upstream_causes("Rate", max_depth=3)
        assert len(causes) == 2  # Inflation, Oil

    def test_causal_chain_confidence(self):
        engine = CausalGraphEngine()
        engine.add_causal_chain(["Oil", "Inflation", "Rate"], 0.9)
        conf = engine.causal_chain(["Oil", "Inflation", "Rate"])
        assert conf == pytest.approx(0.9 * 0.9)

    def test_causal_chain_broken(self):
        engine = CausalGraphEngine()
        engine.add_causal_link("Oil", "Inflation")
        conf = engine.causal_chain(["Oil", "Unknown"])
        assert conf == 0.0

    def test_clear(self):
        engine = CausalGraphEngine()
        engine.add_causal_link("Oil", "Inflation")
        engine.clear()
        assert engine.link_count == 0


# ---------------------------------------------------------------------------
# Factor Graph
# ---------------------------------------------------------------------------

class TestFactorGraph:
    def test_link(self):
        fg = FactorGraph()
        result = fg.link("momentum", "volatility")
        assert result == ("momentum", "volatility")

    def test_add_correlation(self):
        fg = FactorGraph()
        fg.add_correlation("momentum", "volatility", 0.5)
        fg.add_correlation("momentum", "value", -0.3)
        correlated = fg.get_correlated("momentum", min_abs_corr=0.3)
        assert len(correlated) == 2

    def test_get_correlated_filtered(self):
        fg = FactorGraph()
        fg.add_correlation("momentum", "volatility", 0.1)
        fg.add_correlation("momentum", "value", 0.5)
        correlated = fg.get_correlated("momentum", min_abs_corr=0.3)
        assert len(correlated) == 1

    def test_define_factor(self):
        fg = FactorGraph()
        fg.define_factor("MOM", "Momentum", "style", "12-1 month momentum")
        assert fg.factor_count() == 1

    def test_add_complement(self):
        fg = FactorGraph()
        fg.add_complement("quality", "value")
        related = fg.get_related("quality")
        assert len(related) == 1
        assert related[0] == ("value", "complements")

    def test_add_substitute(self):
        fg = FactorGraph()
        fg.add_substitute("growth_small", "growth_large")
        related = fg.get_related("growth_small")
        assert related[0] == ("growth_large", "substitutes")

    def test_get_all_correlations(self):
        fg = FactorGraph()
        fg.add_correlation("A", "B", 0.5)
        fg.add_correlation("B", "C", -0.3)
        all_corr = fg.get_all_correlations()
        assert len(all_corr) == 2

    def test_clear(self):
        fg = FactorGraph()
        fg.define_factor("MOM", "Momentum")
        fg.add_correlation("MOM", "VOL", 0.5)
        fg.clear()
        assert fg.factor_count() == 0
        assert fg.edge_count() == 0


# ---------------------------------------------------------------------------
# Portfolio Graph
# ---------------------------------------------------------------------------

class TestPortfolioGraph:
    def test_connect(self):
        pg = PortfolioGraph()
        result = pg.connect("P1", "NVDA")
        assert result["portfolio"] == "P1"
        assert result["asset"] == "NVDA"

    def test_add_position_and_get_holdings(self):
        pg = PortfolioGraph()
        pg.add_position("P1", "NVDA", quantity=100, weight=0.3)
        pg.add_position("P1", "AAPL", quantity=200, weight=0.5)
        holdings = pg.get_holdings("P1")
        assert len(holdings) == 2

    def test_get_connected_assets(self):
        pg = PortfolioGraph()
        pg.add_position("P1", "NVDA", weight=0.3)
        pg.add_position("P1", "AAPL", weight=0.5)
        assets = pg.get_connected_assets("P1")
        assert "NVDA" in assets
        assert "AAPL" in assets

    def test_add_risk_exposure_and_get_risks(self):
        pg = PortfolioGraph()
        pg.add_position("P1", "NVDA", weight=0.3)
        pg.add_risk_exposure("NVDA", "tech_risk", 0.4)
        pg.add_risk_exposure("NVDA", "market_risk", 0.6)
        risks = pg.get_risks("NVDA")
        assert len(risks) == 2

    def test_add_factor_exposure_and_get_factors(self):
        pg = PortfolioGraph()
        pg.add_position("P1", "NVDA", weight=0.3)
        pg.add_factor_exposure("NVDA", "momentum", 0.7)
        pg.add_factor_exposure("NVDA", "volatility", 0.3)
        factors = pg.get_factors("NVDA")
        assert len(factors) == 2

    def test_aggregate_portfolio_risk(self):
        pg = PortfolioGraph()
        pg.add_position("P1", "NVDA", weight=0.3)
        pg.add_position("P1", "AAPL", weight=0.5)
        pg.add_risk_exposure("NVDA", "market_risk", 0.4)
        pg.add_risk_exposure("AAPL", "market_risk", 0.6)
        agg = pg.aggregate_portfolio_risk("P1")
        assert "market_risk" in agg
        assert agg["market_risk"] == pytest.approx(0.4 * 0.3 + 0.6 * 0.5)

    def test_aggregate_portfolio_factors(self):
        pg = PortfolioGraph()
        pg.add_position("P1", "NVDA", weight=0.3)
        pg.add_factor_exposure("NVDA", "momentum", 0.7)
        agg = pg.aggregate_portfolio_factors("P1")
        assert "momentum" in agg
        assert agg["momentum"] == pytest.approx(0.7 * 0.3)

    def test_clear(self):
        pg = PortfolioGraph()
        pg.add_position("P1", "NVDA")
        pg.clear()
        assert len(pg.get_holdings("P1")) == 0


# ---------------------------------------------------------------------------
# Graph Memory
# ---------------------------------------------------------------------------

class TestGraphMemory:
    def test_save(self):
        gm = GraphMemory()
        version_id = gm.save({"nodes": 10, "edges": 20})
        assert version_id == "v1"
        assert gm.version_count == 1

    def test_save_snapshot(self):
        gm = GraphMemory()
        version_id = gm.save_snapshot(node_count=100, edge_count=200)
        assert version_id == "v1"
        latest = gm.get_latest_version()
        assert latest["data"]["node_count"] == 100

    def test_record_entity(self):
        gm = GraphMemory()
        gm.record_entity("create", "NVDA")
        assert gm.entity_history_count == 1
        history = gm.get_entity_history("NVDA")
        assert len(history) == 1

    def test_record_relation(self):
        gm = GraphMemory()
        gm.record_relation("create", "A", "B", "supplier")
        assert gm.relation_history_count == 1

    def test_record_event(self):
        gm = GraphMemory()
        gm.record_event("propagation", {"source": "Oil"})
        assert gm.event_history_count == 1

    def test_get_versions(self):
        gm = GraphMemory()
        gm.save_snapshot(10, 20)
        gm.save_snapshot(15, 25)
        assert len(gm.get_versions(10)) == 2

    def test_get_relation_history_filtered(self):
        gm = GraphMemory()
        gm.record_relation("create", "A", "B", "supplier")
        gm.record_relation("create", "C", "D", "customer")
        history = gm.get_relation_history("supplier")
        assert len(history) == 1

    def test_clear(self):
        gm = GraphMemory()
        gm.save_snapshot(10, 20)
        gm.record_entity("create", "X")
        gm.clear()
        assert gm.version_count == 0
        assert gm.entity_history_count == 0


# ---------------------------------------------------------------------------
# Knowledge Graph Service (integration)
# ---------------------------------------------------------------------------

class TestKnowledgeGraphService:
    def test_entity_register(self):
        builder = GraphBuilder()
        service = KnowledgeGraphService(builder)
        entity = Entity(id="NVDA", name="NVIDIA", entity_type=EntityType.STOCK)
        service.register(entity)
        assert "NVDA" in builder.nodes
        assert service.registry.exists("NVDA")

    def test_add_relation(self):
        builder = GraphBuilder()
        service = KnowledgeGraphService(builder)
        service.register(Entity("A", "A", EntityType.STOCK))
        service.register(Entity("B", "B", EntityType.STOCK))
        service.add_relation("A", "B", "supplier", 0.9)
        assert builder.edge_count == 1

    def test_add_supply_chain(self):
        builder = GraphBuilder()
        service = KnowledgeGraphService(builder)
        service.register(Entity("AAPL", "Apple", EntityType.STOCK))
        service.register(Entity("TSMC", "TSMC", EntityType.STOCK))
        service.register(Entity("FOXCONN", "Foxconn", EntityType.STOCK))
        relations = service.add_supply_chain("AAPL", ["TSMC", "FOXCONN"], [])
        assert len(relations) == 2

    def test_query_neighbors(self):
        builder = GraphBuilder()
        service = KnowledgeGraphService(builder)
        for eid in ["A", "B", "C"]:
            service.register(Entity(eid, eid, EntityType.STOCK))
        service.add_relation("A", "B", "supplier")
        service.add_relation("A", "C", "customer")
        nbrs = service.query_neighbors("A")
        assert len(nbrs) == 2

    def test_query_shortest_path(self):
        builder = GraphBuilder()
        service = KnowledgeGraphService(builder)
        for eid in ["A", "B", "C"]:
            service.register(Entity(eid, eid, EntityType.STOCK))
        service.add_relation("A", "B", "supplier")
        service.add_relation("B", "C", "supplier")
        path = service.query_shortest_path("A", "C")
        assert path == ["A", "B", "C"]

    def test_propagate_event(self):
        builder = GraphBuilder()
        service = KnowledgeGraphService(builder)
        service.register(Entity("Oil", "Crude Oil", EntityType.MACRO_EVENT))
        service.register(Entity("Inflation", "Inflation", EntityType.MACRO_EVENT))
        service.add_relation("Oil", "Inflation", "causes", 1.0)
        result = service.propagate_event("Oil", 1.0)
        assert result["status"] == "PROPAGATED"

    def test_causal_analysis(self):
        builder = GraphBuilder()
        service = KnowledgeGraphService(builder)
        service.causal.add_causal_chain(["Oil", "Inflation", "Rate"])
        result = service.causal_analysis("Oil")
        assert result["cause"] == "Oil"
        assert result["effect_count"] == 2

    def test_save_snapshot(self):
        builder = GraphBuilder()
        service = KnowledgeGraphService(builder)
        service.register(Entity("A", "A", EntityType.STOCK))
        vid = service.save_snapshot()
        assert vid == "v1"
        assert service.memory.version_count == 1

    def test_to_dict(self):
        builder = GraphBuilder()
        service = KnowledgeGraphService(builder)
        service.register(Entity("A", "Alpha", EntityType.STOCK))
        d = service.to_dict()
        assert d["node_count"] == 1


# ---------------------------------------------------------------------------
# Original minimal test from spec
# ---------------------------------------------------------------------------

def test_entity_register():
    builder = GraphBuilder()
    service = KnowledgeGraphService(builder)
    entity = Entity(id="NVDA", name="NVIDIA", entity_type=EntityType.STOCK)
    service.register(entity)
    assert "NVDA" in builder.nodes


# ---------------------------------------------------------------------------
# DateDeltaCalculator (temporal bias)
# ---------------------------------------------------------------------------

def test_compute_temporal_bias():
    calc = DateDeltaCalculator()
    config = TemporalBiasConfig()

    # Late completion → positive bias
    bias = calc.compute_temporal_bias(
        completion_date=date(2025, 6, 15),
        due_date=date(2025, 6, 1),
        config=config,
    )
    assert bias > 0

    # Early completion → negative bias
    bias = calc.compute_temporal_bias(
        completion_date=date(2025, 5, 15),
        due_date=date(2025, 6, 1),
        config=config,
    )
    assert bias < 0

    # On-time → zero bias
    bias = calc.compute_temporal_bias(
        completion_date=date(2025, 6, 1),
        due_date=date(2025, 6, 1),
        config=config,
    )
    assert bias == 0.0
