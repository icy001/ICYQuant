from datetime import datetime

from services.data.governance import (
    LineageGraph,
    LineageNode,
    QualityRule,
    QualityEngine,
    AuditRecord,
    ImpactAnalyzer,
    GovernanceService,
)


def test_lineage():
    graph = LineageGraph()

    graph.add_edge("dataset", "feature")

    assert graph.downstream("dataset") == ["feature"]


def test_lineage_multi():
    graph = LineageGraph()

    graph.add_edge("dataset", "feature_a")
    graph.add_edge("dataset", "feature_b")
    graph.add_edge("feature_a", "factor")

    downstream = graph.downstream("dataset")

    assert "feature_a" in downstream
    assert "feature_b" in downstream


def test_lineage_node():
    node = LineageNode(name="NVDA_PRICE", node_type="DATASET")

    assert node.name == "NVDA_PRICE"
    assert node.node_type == "DATASET"


def test_quality_rule():
    rule = QualityRule(name="price_not_null", description="Price cannot be null")

    assert rule.name == "price_not_null"


def test_quality_engine():
    engine = QualityEngine()
    rule = QualityRule(name="test_rule", description="test")

    result = engine.validate({}, rule)

    assert result is True


def test_audit_record():
    record = AuditRecord(
        action="UPDATE_DATASET",
        timestamp=datetime(2026, 7, 17, 10, 0, 0),
    )

    assert record.action == "UPDATE_DATASET"
    assert record.timestamp.hour == 10


def test_impact_analyzer():
    graph = LineageGraph()
    analyzer = ImpactAnalyzer(graph)

    graph.add_edge("NASDAQ", "Momentum")
    graph.add_edge("Momentum", "Alpha")
    graph.add_edge("Alpha", "StrategyA")

    impact = analyzer.analyze("NASDAQ")

    assert "Momentum" in impact


def test_governance_service():
    lineage = LineageGraph()
    quality = QualityEngine()
    service = GovernanceService(lineage, quality)

    assert service.lineage == lineage
    assert service.quality == quality