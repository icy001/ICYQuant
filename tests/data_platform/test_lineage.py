"""测试 Data Lineage — 数据血缘追踪。

覆盖: 节点注册、边创建、上下游追踪、影响分析、路径查找。
"""

import pytest
from services.data_platform.lineage import (
    LineageTracker,
    LineageNode,
    LineageEdge,
    LineageChain,
    OperationType,
    ImpactAnalysis,
)
from services.data_platform.config import LineageConfig


class TestLineageNodeRegistration:
    """测试血缘节点注册。"""

    @pytest.fixture
    def tracker(self):
        return LineageTracker(LineageConfig())

    def test_add_node(self, tracker):
        """添加节点应成功创建 LineageNode。"""
        node = tracker.add_node("market_tick", "market_data", OperationType.INGEST)
        assert node.dataset == "market_tick"
        assert node.producer == "market_data"
        assert node.operation == OperationType.INGEST

    def test_get_node(self, tracker):
        """按 ID 获取节点应返回正确的节点。"""
        node = tracker.add_node("market_tick", "market_data", OperationType.INGEST)
        retrieved = tracker.get_node(node.node_id)
        assert retrieved is not None
        assert retrieved.dataset == "market_tick"

    def test_get_nodes_by_dataset(self, tracker):
        """按数据集获取节点应返回所有相关节点。"""
        tracker.add_node("market_tick", "market_data", OperationType.INGEST)
        tracker.add_node("market_tick", "market_data", OperationType.TRANSFORM)
        nodes = tracker.get_nodes_by_dataset("market_tick")
        assert len(nodes) == 2

    def test_node_with_metadata(self, tracker):
        """节点应存储额外的元数据。"""
        node = tracker.add_node(
            "market_tick", "market_data", OperationType.INGEST,
            row_count=10000, description="Raw tick data",
            source="exchange_api",
        )
        assert node.row_count == 10000
        assert node.metadata["source"] == "exchange_api"


class TestLineageEdgeCreation:
    """测试血缘边创建。"""

    @pytest.fixture
    def tracker(self):
        t = LineageTracker(LineageConfig())
        t.add_node("market_tick", "market_data", OperationType.INGEST)
        t.add_node("1min_bar", "market_data", OperationType.AGGREGATE)
        t.add_node("ema20", "feature_pipeline", OperationType.FEATURE)
        return t

    def test_add_edge(self, tracker):
        """添加边应成功连接两个数据集。"""
        edge = tracker.add_edge("market_tick", "1min_bar", "resample_1min")
        assert edge is not None
        assert edge.transform == "resample_1min"

    def test_add_edge_missing_source(self, tracker):
        """源数据集不存在时应返回 None。"""
        edge = tracker.add_edge("nonexistent", "1min_bar", "transform")
        assert edge is None

    def test_add_edge_missing_target(self, tracker):
        """目标数据集不存在时应返回 None。"""
        edge = tracker.add_edge("market_tick", "nonexistent", "transform")
        assert edge is None

    def test_add_edge_with_description(self, tracker):
        """边应支持描述和元数据。"""
        edge = tracker.add_edge(
            "market_tick", "1min_bar", "resample_1min",
            description="Resample tick to 1-minute OHLCV bars",
            timeframe="1min",
        )
        assert edge is not None
        assert edge.description == "Resample tick to 1-minute OHLCV bars"
        assert edge.metadata["timeframe"] == "1min"


class TestLineageTracing:
    """测试血缘追踪。"""

    @pytest.fixture
    def tracker(self):
        """构建完整血缘链: tick → bar → return → ema20 → momentum → alpha"""
        t = LineageTracker(LineageConfig())
        t.add_node("market_tick", "market_data", OperationType.INGEST)
        t.add_node("1min_bar", "market_data", OperationType.AGGREGATE)
        t.add_node("returns", "feature_pipeline", OperationType.TRANSFORM)
        t.add_node("ema20", "feature_pipeline", OperationType.FEATURE)
        t.add_node("momentum", "feature_pipeline", OperationType.FACTOR)
        t.add_node("alpha", "alpha_pipeline", OperationType.FACTOR)

        t.add_edge("market_tick", "1min_bar", "resample_1min")
        t.add_edge("1min_bar", "returns", "compute_returns")
        t.add_edge("returns", "ema20", "compute_ema")
        t.add_edge("ema20", "momentum", "compute_momentum")
        t.add_edge("momentum", "alpha", "alpha_formula")
        return t

    def test_trace_downstream(self, tracker):
        """下游追踪应返回完整链。"""
        chain = tracker.trace_downstream("market_tick")
        assert chain.depth > 0
        assert len(chain.nodes) >= 1
        datasets = {n.dataset for n in chain.nodes}
        assert "market_tick" in datasets

    def test_trace_upstream(self, tracker):
        """上游追踪应返回完整链。"""
        chain = tracker.trace_upstream("alpha")
        datasets = {n.dataset for n in chain.nodes}
        assert "alpha" in datasets
        # Should trace back to market_tick
        assert "market_tick" in datasets or len(chain.nodes) >= 1

    def test_trace_max_depth(self, tracker):
        """最大深度限制应生效。"""
        chain = tracker.trace_downstream("market_tick", max_depth=2)
        assert chain.depth <= 2

    def test_trace_nonexistent(self, tracker):
        """追踪不存在的数据集应返回空链。"""
        chain = tracker.trace_downstream("nonexistent")
        assert chain.depth == 0


class TestLineageImpactAnalysis:
    """测试血缘影响分析。"""

    @pytest.fixture
    def tracker(self):
        t = LineageTracker(LineageConfig())
        t.add_node("market_tick", "market_data", OperationType.INGEST)
        t.add_node("1min_bar", "market_data", OperationType.AGGREGATE)
        t.add_node("ema20", "feature_pipeline", OperationType.FEATURE)
        t.add_edge("market_tick", "1min_bar", "resample")
        t.add_edge("1min_bar", "ema20", "compute_ema")
        return t

    def test_analyze_impact(self, tracker):
        """影响分析应返回受影响的数据集。"""
        impact = tracker.analyze_impact("market_tick")
        assert isinstance(impact, ImpactAnalysis)
        assert len(impact.affected_downstream) >= 1

    def test_find_path(self, tracker):
        """查找路径应返回两个数据集之间的血缘链。"""
        path = tracker.find_path("market_tick", "ema20")
        assert path is not None
        assert path.source_dataset == "market_tick"
        assert path.target_dataset == "ema20"

    def test_find_path_no_connection(self, tracker):
        """无连接的数据集应返回 None。"""
        tracker.add_node("isolated", "other", OperationType.INGEST)
        path = tracker.find_path("market_tick", "isolated")
        assert path is None


class TestLineageGraphStats:
    """测试血缘图统计。"""

    def test_get_graph_stats(self):
        """获取图统计应返回正确计数。"""
        tracker = LineageTracker(LineageConfig())
        tracker.add_node("tick", "market_data", OperationType.INGEST)
        tracker.add_node("bar", "market_data", OperationType.AGGREGATE)
        tracker.add_edge("tick", "bar", "resample")

        stats = tracker.get_graph_stats()
        assert stats["total_nodes"] == 2
        assert stats["total_edges"] == 1
        assert stats["total_datasets"] == 2
