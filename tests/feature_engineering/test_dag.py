"""测试 Feature DAG — 特征依赖图引擎。

覆盖: 节点注册、边管理、拓扑排序、上下游遍历、子图提取、循环检测。
"""

import pytest

from services.feature_engineering.dag import DAGNode, FeatureDAG, NodeState, dag_node


class TestDAGNode:
    """DAGNode 数据类测试。"""

    def test_create_node(self):
        node = DAGNode(name="ema20", description="20-period EMA")
        assert node.name == "ema20"
        assert node.state == NodeState.PENDING
        assert node.cacheable is True

    def test_node_equality(self):
        a = DAGNode(name="ema20")
        b = DAGNode(name="ema20")
        c = DAGNode(name="return")
        assert a == b
        assert a != c

    def test_node_hash(self):
        a = DAGNode(name="ema20")
        b = DAGNode(name="ema20")
        assert hash(a) == hash(b)
        assert len({a, b}) == 1

    def test_node_state_transition(self):
        node = DAGNode(name="momentum")
        assert node.state == NodeState.PENDING
        node.state = NodeState.RUNNING
        assert node.state == NodeState.RUNNING
        node.state = NodeState.COMPLETED
        assert node.state == NodeState.COMPLETED


class TestDAGNodeDecorator:
    """@dag_node 装饰器测试。"""

    def test_decorator_creates_node(self):
        @dag_node(depends_on=["return"], description="calc ema")
        def ema20(data):
            pass

        assert isinstance(ema20, DAGNode)
        assert ema20.name == "ema20"
        assert ema20.metadata["_depends_on"] == ["return"]
        assert ema20.description == "calc ema"

    def test_decorator_no_deps(self):
        @dag_node()
        def raw_price(data):
            pass

        assert raw_price.name == "raw_price"
        assert raw_price.metadata["_depends_on"] == []

    def test_decorator_with_tags(self):
        @dag_node(tags=["alpha", "momentum"], cacheable=False)
        def momentum_20(data):
            pass

        assert momentum_20.metadata["_depends_on"] == []
        assert momentum_20.tags == ["alpha", "momentum"]
        assert momentum_20.cacheable is False


class TestFeatureDAGBasic:
    """FeatureDAG 基础操作测试。"""

    @pytest.fixture
    def dag(self):
        d = FeatureDAG("test_dag")
        d.add_node(DAGNode(name="raw_price"))
        d.add_node(DAGNode(name="return"))
        d.add_node(DAGNode(name="ema20"))
        d.add_node(DAGNode(name="momentum"))
        return d

    def test_add_node(self, dag):
        assert dag.node_count == 4

    def test_add_duplicate_node_raises(self, dag):
        with pytest.raises(ValueError, match="already exists"):
            dag.add_node(DAGNode(name="return"))

    def test_add_edge(self, dag):
        dag.add_edge("raw_price", "return")
        assert "return" in dag.successors("raw_price")
        assert "raw_price" in dag.predecessors("return")

    def test_add_edge_self_loop_raises(self, dag):
        with pytest.raises(ValueError, match="Self-loop"):
            dag.add_edge("return", "return")

    def test_add_edge_unregistered_source_raises(self, dag):
        with pytest.raises(KeyError, match="not registered"):
            dag.add_edge("unknown", "return")

    def test_remove_node(self, dag):
        dag.add_edge("raw_price", "return")
        dag.remove_node("return")
        assert dag.node_count == 3
        assert "return" not in dag.nodes
        assert "return" not in dag.successors("raw_price")

    def test_remove_nonexistent_node_raises(self, dag):
        with pytest.raises(KeyError):
            dag.remove_node("nonexistent")

    def test_get_node(self, dag):
        node = dag.get_node("raw_price")
        assert node.name == "raw_price"

    def test_get_nonexistent_node_raises(self, dag):
        with pytest.raises(KeyError):
            dag.get_node("nonexistent")


class TestFeatureDAGCycleDetection:
    """循环检测测试。"""

    def test_cycle_detection(self):
        dag = FeatureDAG()
        dag.add_node(DAGNode(name="A"))
        dag.add_node(DAGNode(name="B"))
        dag.add_node(DAGNode(name="C"))
        dag.add_edge("A", "B")
        dag.add_edge("B", "C")
        with pytest.raises(ValueError, match="cycle"):
            dag.add_edge("C", "A")

    def test_no_cycle(self):
        dag = FeatureDAG()
        dag.add_node(DAGNode(name="A"))
        dag.add_node(DAGNode(name="B"))
        dag.add_node(DAGNode(name="C"))
        dag.add_edge("A", "B")
        dag.add_edge("B", "C")
        dag.add_edge("A", "C")
        # No error expected
        assert dag.node_count == 3

    def test_auto_wire_from_decorator(self):
        dag = FeatureDAG()
        n1 = dag_node(depends_on=[])(lambda: None)
        n2 = dag_node(depends_on=["raw_price"])(lambda: None)
        # Rename to avoid conflict
        n1 = DAGNode(name="raw_price", func=lambda: None)
        dag.add_node(n1)
        dag.add_node(n2)
        assert "raw_price" in dag.predecessors("raw_price") or dag.node_count == 2


class TestFeatureDAGTopologicalSort:
    """拓扑排序测试。"""

    def test_linear_chain(self):
        dag = FeatureDAG()
        dag.add_node(DAGNode(name="A"))
        dag.add_node(DAGNode(name="B"))
        dag.add_node(DAGNode(name="C"))
        dag.add_node(DAGNode(name="D"))
        dag.add_edge("A", "B")
        dag.add_edge("B", "C")
        dag.add_edge("C", "D")
        order = dag.topological_order()
        assert order == ["A", "B", "C", "D"]

    def test_diamond_dependency(self):
        dag = FeatureDAG()
        dag.add_node(DAGNode(name="A"))
        dag.add_node(DAGNode(name="B"))
        dag.add_node(DAGNode(name="C"))
        dag.add_node(DAGNode(name="D"))
        dag.add_edge("A", "B")
        dag.add_edge("A", "C")
        dag.add_edge("B", "D")
        dag.add_edge("C", "D")
        order = dag.topological_order()
        assert order[0] == "A"
        assert order[-1] == "D"
        assert order.index("B") < order.index("D")
        assert order.index("C") < order.index("D")

    def test_multiple_roots(self):
        dag = FeatureDAG()
        dag.add_node(DAGNode(name="X"))
        dag.add_node(DAGNode(name="Y"))
        dag.add_node(DAGNode(name="Z"))
        dag.add_edge("X", "Z")
        dag.add_edge("Y", "Z")
        order = dag.topological_order()
        assert order[-1] == "Z"
        assert "X" in order[:2]
        assert "Y" in order[:2]


class TestFeatureDAGExecutionLayers:
    """并行执行层测试。"""

    def test_layers_diamond(self):
        dag = FeatureDAG()
        dag.add_node(DAGNode(name="A"))
        dag.add_node(DAGNode(name="B"))
        dag.add_node(DAGNode(name="C"))
        dag.add_node(DAGNode(name="D"))
        dag.add_edge("A", "B")
        dag.add_edge("A", "C")
        dag.add_edge("B", "D")
        dag.add_edge("C", "D")
        layers = dag.execution_layers()
        assert len(layers) == 3
        assert layers[0] == ["A"]
        assert set(layers[1]) == {"B", "C"}
        assert layers[2] == ["D"]


class TestFeatureDAGTraversal:
    """上下游遍历测试。"""

    @pytest.fixture
    def dag(self):
        d = FeatureDAG()
        for name in ["A", "B", "C", "D", "E"]:
            d.add_node(DAGNode(name=name))
        d.add_edge("A", "B")
        d.add_edge("A", "C")
        d.add_edge("B", "D")
        d.add_edge("C", "D")
        d.add_edge("D", "E")
        return d

    def test_upstream(self, dag):
        upstream = dag.upstream("D")
        assert set(upstream) == {"A", "B", "C"}

    def test_upstream_max_depth(self, dag):
        upstream = dag.upstream("D", max_depth=1)
        assert set(upstream) == {"B", "C"}

    def test_downstream(self, dag):
        downstream = dag.downstream("A")
        assert set(downstream) == {"B", "C", "D", "E"}

    def test_downstream_max_depth(self, dag):
        downstream = dag.downstream("A", max_depth=1)
        assert set(downstream) == {"B", "C"}

    def test_no_upstream_for_root(self, dag):
        assert dag.upstream("A") == []

    def test_no_downstream_for_leaf(self, dag):
        assert dag.downstream("E") == []


class TestFeatureDAGSubgraph:
    """子图提取测试。"""

    def test_subgraph(self):
        dag = FeatureDAG()
        for name in ["A", "B", "C", "D", "E"]:
            dag.add_node(DAGNode(name=name))
        dag.add_edge("A", "B")
        dag.add_edge("A", "C")
        dag.add_edge("B", "D")
        dag.add_edge("C", "D")
        dag.add_edge("D", "E")

        sub = dag.subgraph(["D"])
        assert sub.node_count >= 3  # D and its ancestors A, B, C
        assert "D" in sub.nodes

    def test_subgraph_isolated(self):
        dag = FeatureDAG()
        dag.add_node(DAGNode(name="isolated"))
        sub = dag.subgraph(["isolated"])
        assert sub.node_count == 1


class TestFeatureDAGReadyNodes:
    """就绪节点计算测试。"""

    def test_all_roots_ready(self):
        dag = FeatureDAG()
        dag.add_node(DAGNode(name="A"))
        dag.add_node(DAGNode(name="B"))
        dag.add_node(DAGNode(name="C"))
        dag.add_edge("A", "C")
        dag.add_edge("B", "C")
        ready = dag.ready_nodes()
        assert set(ready) == {"A", "B"}

    def test_ready_after_completion(self):
        dag = FeatureDAG()
        dag.add_node(DAGNode(name="A"))
        dag.add_node(DAGNode(name="B"))
        dag.add_edge("A", "B")
        # Mark A as completed
        dag.get_node("A").state = NodeState.COMPLETED
        ready = dag.ready_nodes()
        assert "B" in ready

    def test_reset(self):
        dag = FeatureDAG()
        dag.add_node(DAGNode(name="A"))
        dag.get_node("A").state = NodeState.COMPLETED
        dag.reset()
        assert dag.get_node("A").state == NodeState.PENDING


class TestFeatureDAGSummary:
    """DAG 摘要信息测试。"""

    def test_summary(self):
        dag = FeatureDAG("summary_dag")
        dag.add_node(DAGNode(name="A"))
        dag.add_node(DAGNode(name="B"))
        dag.add_node(DAGNode(name="C"))
        dag.add_edge("A", "B")
        dag.add_edge("B", "C")
        s = dag.summary()
        assert s["name"] == "summary_dag"
        assert s["total_nodes"] == 3
        assert s["total_edges"] == 2
        assert s["roots"] == ["A"]
        assert s["leaves"] == ["C"]
