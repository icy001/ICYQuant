"""
Tests for ICYQuant Platform Bootstrap.
"""

import pytest

from platform.bootstrap import PlatformBootstrap
from platform.module_registry import ModuleRegistry, ModuleType


class TestPlatformBootstrap:
    """Test platform bootstrap sequence."""

    def test_bootstrap_creation(self):
        bootstrap = PlatformBootstrap()
        assert bootstrap._config_dir == "configs/platform"
        status = bootstrap.get_bootstrap_status()
        assert "phase" in status

    def test_bootstrap_with_registry(self):
        registry = ModuleRegistry()
        registry.register("test_module", ModuleType.CORE)
        bootstrap = PlatformBootstrap(registry=registry)
        assert bootstrap._registry is registry

    def test_load_config(self):
        bootstrap = PlatformBootstrap(config_dir="nonexistent")
        bootstrap._load_config()
        status = bootstrap.get_bootstrap_status()
        assert "steps" in status

    def test_full_bootstrap(self):
        registry = ModuleRegistry()
        runtime = __import__('platform.runtime', fromlist=['RuntimeManager']).RuntimeManager()
        lifecycle = __import__('platform.lifecycle', fromlist=['LifecycleManager']).LifecycleManager()

        registry.register("lakehouse", ModuleType.INFRASTRUCTURE)
        registry.register("market_data", ModuleType.DATA, dependencies=["lakehouse"])
        registry.register("risk", ModuleType.RISK, dependencies=["market_data"])

        bootstrap = PlatformBootstrap(
            config_dir="nonexistent",
            registry=registry,
            runtime=runtime,
            lifecycle=lifecycle,
        )
        result = bootstrap.bootstrap()
        assert result is True
        status = bootstrap.get_bootstrap_status()
        assert status["phase"] == "ready"
        assert status["progress"] == 100

    def test_get_status(self):
        bootstrap = PlatformBootstrap()
        status = bootstrap.get_status()
        assert "phase" in status
        assert "progress" in status
