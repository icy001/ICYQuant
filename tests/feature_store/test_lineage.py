"""测试 Feature Lineage — 特征血缘追踪。

覆盖: 节点管理、边管理、上下游遍历、路径查找、子图导出。
"""

import pytest

from services.feature_store.lineage import FeatureLineage, LineageGraph, NodeType


class TestLineageNodeManagement:
    """节点管理测试。"""

    def test_add_node(self):
        """添加节点应成功。"""
        lineage = FeatureLineage()
        node = lineage.add_node("raw_tick", NodeType.SOURCE, "Raw tick data")
        assert node.node_id == "raw_tick"
        assert node.node_type == NodeType.SOURCE
        assert node.description == "Raw tick data"

    def test_add_duplicate_node_fails(self):
        """重复添加节点应抛出异常。"""
        lineage = FeatureLineage()
        lineage.add_node("ema20")
        with pytest.raises(ValueError, match="already exists"):
            lineage.add_node("ema20")

    def test_get_node(self):
        """获取节点应正确。"""
        lineage = FeatureLineage()
        lineage.add_node("ema20", NodeType.FEATURE)
        node = lineage.get_node("ema20")
        assert node.node_type == NodeType.FEATURE

    def test_get_node_not_found(self):
        """获取不存在的节点应抛出异常。"""
        lineage = FeatureLineage()
        with pytest.raises(KeyError):
            lineage.get_node("nonexistent")

    def test_remove_node(self):
        """删除节点应移除节点和边。"""
        lineage = FeatureLineage()
        lineage.add_node("bar")
        lineage.add_node("ema20")
        lineage.add_edge("bar", "ema20")
        lineage.remove_node("ema20")
        with pytest.raises(KeyError):
            lineage.get_node("ema20")
        assert lineage.node_count() == 1

    def test_remove_node_not_found(self):
        """删除不存在的节点应抛出异常。"""
        lineage = FeatureLineage()
        with pytest.raises(KeyError):
            lineage.remove_node("nonexistent")


class TestLineageEdgeManagement:
    """边管理测试。"""

    def test_add_edge(self):
        """添加边应成功。"""
        lineage = FeatureLineage()
        lineage.add_node("bar")
        lineage.add_node("ema20")
        lineage.add_edge("bar", "ema20")
        assert lineage.edge_count() == 1

    def test_add_edge_node_not_found(self):
        """添加边时节点不存在应抛出异常。"""
        lineage = FeatureLineage()
        lineage.add_node("bar")
        with pytest.raises(KeyError):
            lineage.add_edge("bar", "nonexistent")

    def test_add_edge_cycle_detection(self):
        """检测到环应抛出异常。"""
        lineage = FeatureLineage()
        lineage.add_node("a")
        lineage.add_node("b")
        lineage.add_node("c")
        lineage.add_edge("a", "b")
        lineage.add_edge("b", "c")
        with pytest.raises(ValueError, match="cycle"):
            lineage.add_edge("c", "a")

    def test_remove_edge(self):
        """删除边应成功。"""
        lineage = FeatureLineage()
        lineage.add_node("bar")
        lineage.add_node("ema20")
        lineage.add_edge("bar", "ema20")
        lineage.remove_edge("bar", "ema20")
        assert lineage.edge_count() == 0

    def test_self_loop_cycle(self):
        """自环应被检测为环。"""
        lineage = FeatureLineage()
        lineage.add_node("x")
        with pytest.raises(ValueError, match="cycle"):
            lineage.add_edge("x", "x")


class TestLineageTraversal:
    """遍历测试。"""

    def test_get_upstream(self):
        """获取上游节点应正确。"""
        lineage = FeatureLineage()
        lineage.add_node("tick")
        lineage.add_node("bar")
        lineage.add_node("ema20")
        lineage.add_node("momentum")
        lineage.add_edge("tick", "bar")
        lineage.add_edge("bar", "ema20")
        lineage.add_edge("ema20", "momentum")

        upstream = lineage.get_upstream("momentum")
        assert "ema20" in upstream
        assert "bar" in upstream
        assert "tick" in upstream

    def test_get_downstream(self):
        """获取下游节点应正确。"""
        lineage = FeatureLineage()
        lineage.add_node("tick")
        lineage.add_node("bar")
        lineage.add_node("ema20")
        lineage.add_edge("tick", "bar")
        lineage.add_edge("bar", "ema20")

        downstream = lineage.get_downstream("tick")
        assert "bar" in downstream
        assert "ema20" in downstream

    def test_get_upstream_not_found(self):
        """遍历不存在节点应抛出异常。"""
        lineage = FeatureLineage()
        with pytest.raises(KeyError):
            lineage.get_upstream("nonexistent")

    def test_get_upstream_max_depth(self):
        """上游遍历应受深度限制。"""
        lineage = FeatureLineage()
        lineage.add_node("a")
        lineage.add_node("b")
        lineage.add_node("c")
        lineage.add_node("d")
        lineage.add_edge("a", "b")
        lineage.add_edge("b", "c")
        lineage.add_edge("c", "d")

        upstream = lineage.get_upstream("d", max_depth=1)
        assert "c" in upstream
        assert "b" not in upstream  # too deep


class TestLineagePath:
    """路径查找测试。"""

    def test_get_path_exists(self):
        """存在路径时应返回正确路径。"""
        lineage = FeatureLineage()
        lineage.add_node("a")
        lineage.add_node("b")
        lineage.add_node("c")
        lineage.add_edge("a", "b")
        lineage.add_edge("b", "c")

        path = lineage.get_path("a", "c")
        assert path == ["a", "b", "c"]

    def test_get_path_same_node(self):
        """同一节点的路径应返回自身。"""
        lineage = FeatureLineage()
        lineage.add_node("x")
        path = lineage.get_path("x", "x")
        assert path == ["x"]

    def test_get_path_not_exists(self):
        """不存在路径时应返回 None。"""
        lineage = FeatureLineage()
        lineage.add_node("a")
        lineage.add_node("b")
        lineage.add_node("c")
        lineage.add_edge("a", "b")

        path = lineage.get_path("b", "a")
        assert path is None

    def test_get_path_not_found(self):
        """节点不存在时应抛出异常。"""
        lineage = FeatureLineage()
        lineage.add_node("a")
        with pytest.raises(KeyError):
            lineage.get_path("a", "nonexistent")


class TestLineageExport:
    """图导出测试。"""

    def test_export_graph(self):
        """导出图应包含所有节点和边。"""
        lineage = FeatureLineage()
        lineage.add_node("tick", NodeType.SOURCE)
        lineage.add_node("bar", NodeType.TRANSFORM)
        lineage.add_node("ema20", NodeType.FEATURE)
        lineage.add_edge("tick", "bar")
        lineage.add_edge("bar", "ema20")

        graph = lineage.export_graph()
        assert len(graph.nodes) == 3
        assert len(graph.edges) == 2
        assert graph.root_nodes == ["tick"]

    def test_get_subgraph_upstream(self):
        """获取上游子图应正确。"""
        lineage = FeatureLineage()
        lineage.add_node("tick")
        lineage.add_node("bar")
        lineage.add_node("ema20")
        lineage.add_node("rsi14")
        lineage.add_edge("tick", "bar")
        lineage.add_edge("bar", "ema20")
        lineage.add_edge("bar", "rsi14")

        subgraph = lineage.get_subgraph("ema20", "upstream")
        assert len(subgraph.nodes) == 3  # ema20, bar, tick
        assert "rsi14" not in subgraph.nodes

    def test_get_subgraph_downstream(self):
        """获取下游子图应正确。"""
        lineage = FeatureLineage()
        lineage.add_node("tick")
        lineage.add_node("bar")
        lineage.add_node("ema20")
        lineage.add_node("rsi14")
        lineage.add_edge("tick", "bar")
        lineage.add_edge("bar", "ema20")
        lineage.add_edge("bar", "rsi14")

        subgraph = lineage.get_subgraph("bar", "downstream")
        assert "ema20" in subgraph.nodes
        assert "rsi14" in subgraph.nodes
        assert "tick" not in subgraph.nodes


class TestLineageStats:
    """统计信息测试。"""

    def test_node_count(self):
        """node_count 应返回节点数。"""
        lineage = FeatureLineage()
        assert lineage.node_count() == 0
        lineage.add_node("a")
        lineage.add_node("b")
        assert lineage.node_count() == 2

    def test_edge_count(self):
        """edge_count 应返回边数。"""
        lineage = FeatureLineage()
        lineage.add_node("a")
        lineage.add_node("b")
        lineage.add_node("c")
        lineage.add_edge("a", "b")
        lineage.add_edge("b", "c")
        assert lineage.edge_count() == 2


class TestComplexLineage:
    """复杂血缘场景测试。"""

    def test_full_feature_chain(self):
        """模拟完整特征血缘链：tick -> bar -> return -> ema20 -> momentum -> alpha。"""
        lineage = FeatureLineage()
        nodes = ["tick", "bar", "return", "ema20", "momentum", "alpha"]
        types = [
            NodeType.SOURCE, NodeType.TRANSFORM, NodeType.TRANSFORM,
            NodeType.FEATURE, NodeType.FACTOR, NodeType.FACTOR,
        ]
        for nid, ntype in zip(nodes, types):
            lineage.add_node(nid, ntype)
        for i in range(len(nodes) - 1):
            lineage.add_edge(nodes[i], nodes[i + 1])

        # Check full upstream from alpha
        upstream = lineage.get_upstream("alpha")
        assert "momentum" in upstream
        assert "ema20" in upstream
        assert "return" in upstream
        assert "bar" in upstream
        assert "tick" in upstream

        # Check full downstream from tick
        downstream = lineage.get_downstream("tick")
        assert all(n in downstream for n in ["bar", "return", "ema20", "momentum", "alpha"])

        # Path check
        path = lineage.get_path("tick", "alpha")
        assert path == nodes

    def test_branching_lineage(self):
        """测试分支血缘：bar -> ema20 + bar -> rsi14。"""
        lineage = FeatureLineage()
        lineage.add_node("tick")
        lineage.add_node("bar")
        lineage.add_node("ema20")
        lineage.add_node("rsi14")
        lineage.add_edge("tick", "bar")
        lineage.add_edge("bar", "ema20")
        lineage.add_edge("bar", "rsi14")

        downstream = lineage.get_downstream("bar")
        assert "ema20" in downstream
        assert "rsi14" in downstream
        assert "tick" not in downstream

        # ema20 的上游不应包含 rsi14
        upstream_ema = lineage.get_upstream("ema20")
        assert "bar" in upstream_ema
        assert "tick" in upstream_ema
        assert "rsi14" not in upstream_ema
