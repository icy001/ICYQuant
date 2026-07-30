"""
Tests for ICYQuant Module Registry and Dependency Graph.
"""

import pytest

from platform.module_registry import ModuleRegistry, ModuleInfo, ModuleState, ModuleType
from platform.dependency_graph import DependencyGraph, DependencyType


class TestModuleRegistry:
    """Test module registration and discovery."""

    def test_register_module(self):
        registry = ModuleRegistry()
        info = registry.register(
            "market_data", ModuleType.DATA, version="1.0.0",
            description="Market Data Service",
        )
        assert info.name == "market_data"
        assert info.module_type == ModuleType.DATA
        assert info.state == ModuleState.REGISTERED

    def test_register_duplicate(self):
        registry = ModuleRegistry()
        registry.register("test", ModuleType.CORE)
        with pytest.raises(ValueError):
            registry.register("test", ModuleType.CORE)

    def test_get_module(self):
        registry = ModuleRegistry()
        registry.register("test", ModuleType.CORE)
        info = registry.get_module("test")
        assert info is not None
        assert info.name == "test"

    def test_get_nonexistent(self):
        registry = ModuleRegistry()
        assert registry.get_module("nonexistent") is None

    def test_set_state(self):
        registry = ModuleRegistry()
        registry.register("test", ModuleType.CORE)
        registry.set_state("test", ModuleState.RUNNING)
        info = registry.get_module("test")
        assert info.state == ModuleState.RUNNING

    def test_get_by_type(self):
        registry = ModuleRegistry()
        registry.register("mod1", ModuleType.DATA)
        registry.register("mod2", ModuleType.DATA)
        registry.register("mod3", ModuleType.RISK)
        data_modules = registry.get_by_type(ModuleType.DATA)
        assert len(data_modules) == 2

    def test_get_by_state(self):
        registry = ModuleRegistry()
        registry.register("mod1", ModuleType.CORE)
        registry.register("mod2", ModuleType.CORE)
        registry.set_state("mod1", ModuleState.RUNNING)
        running = registry.get_by_state(ModuleState.RUNNING)
        assert len(running) == 1

    def test_unregister(self):
        registry = ModuleRegistry()
        registry.register("test", ModuleType.CORE)
        assert registry.unregister("test") is True
        assert registry.get_module("test") is None

    def test_check_health(self):
        registry = ModuleRegistry()
        registry.register("test", ModuleType.CORE, health_check=lambda: True)
        results = registry.check_health()
        assert results["test"] is True

    def test_list_names(self):
        registry = ModuleRegistry()
        registry.register("a", ModuleType.CORE)
        registry.register("b", ModuleType.CORE)
        names = registry.list_names()
        assert "a" in names
        assert "b" in names

    def test_count(self):
        registry = ModuleRegistry()
        registry.register("a", ModuleType.CORE)
        registry.register("b", ModuleType.CORE)
        assert registry.count() == 2

    def test_get_status(self):
        registry = ModuleRegistry()
        registry.register("a", ModuleType.CORE)
        registry.set_state("a", ModuleState.RUNNING)
        status = registry.get_status()
        assert status["total"] == 1
        assert status["healthy"] == 1

    def test_ordered_by_dependencies(self):
        registry = ModuleRegistry()
        registry.register("a", ModuleType.CORE)
        registry.register("b", ModuleType.CORE, dependencies=["a"])
        registry.register("c", ModuleType.CORE, dependencies=["b"])
        order = registry.ordered_by_dependencies()
        names = [m.name for m in order]
        assert names.index("a") < names.index("b")
        assert names.index("b") < names.index("c")

    def test_to_dict(self):
        registry = ModuleRegistry()
        registry.register("test", ModuleType.CORE, description="Test")
        data = registry.to_dict()
        assert "modules" in data
        assert "status" in data


class TestDependencyGraph:
    """Test dependency graph construction and resolution."""

    def test_add_node(self):
        graph = DependencyGraph()
        node = graph.add_node("market_data", "data")
        assert node.name == "market_data"

    def test_add_edge(self):
        graph = DependencyGraph()
        graph.add_node("a", "core")
        graph.add_node("b", "core")
        graph.add_edge("b", "a")
        deps = graph.get_dependencies("b")
        assert "a" in deps

    def test_detect_cycle(self):
        graph = DependencyGraph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_edge("a", "b")
        graph.add_edge("b", "a")
        cycles = graph.detect_cycles()
        assert len(cycles) > 0
        assert graph.has_cycle() is True

    def test_no_cycle(self):
        graph = DependencyGraph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_edge("b", "a")
        graph.add_edge("c", "b")
        assert graph.has_cycle() is False

    def test_resolve_startup_order(self):
        graph = DependencyGraph()
        graph.add_node("lakehouse", "infrastructure")
        graph.add_node("market_data", "data", dependencies=["lakehouse"])
        graph.add_node("risk", "risk", dependencies=["market_data"])
        graph.add_node("oms", "trading", dependencies=["risk"])

        order = graph.resolve_startup_order()
        assert order.index("lakehouse") < order.index("market_data")
        assert order.index("market_data") < order.index("risk")
        assert order.index("risk") < order.index("oms")

    def test_get_startup_levels(self):
        graph = DependencyGraph()
        graph.add_node("a")
        graph.add_node("b", dependencies=["a"])
        graph.add_node("c", dependencies=["b"])
        levels = graph.get_startup_levels()
        assert len(levels) > 0
        assert "a" in levels.get(0, [])

    def test_remove_node(self):
        graph = DependencyGraph()
        graph.add_node("a")
        graph.add_node("b", dependencies=["a"])
        graph.remove_node("a")
        node_a = graph.get_node("a")
        assert node_a is None
        node_b = graph.get_node("b")
        assert "a" not in node_b.dependencies

    def test_to_dict(self):
        graph = DependencyGraph()
        graph.add_node("test")
        data = graph.to_dict()
        assert "nodes" in data
        assert "startupOrder" in data
