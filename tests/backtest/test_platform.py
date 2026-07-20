from services.backtest import (
    BacktestPlatform,
    BacktestComponentRegistry,
    BacktestBootstrap,
    BacktestHealthCheck,
)


def test_platform():
    platform = BacktestPlatform({})

    assert platform.start() is True


def test_component_registry():
    registry = BacktestComponentRegistry()

    registry.register("exchange", {"name": "virtual"})

    assert registry.get("exchange") == {"name": "virtual"}


def test_bootstrap():
    registry = BacktestComponentRegistry()
    bootstrap = BacktestBootstrap()

    result = bootstrap.initialize(registry)

    assert result == registry


def test_health_check():
    health = BacktestHealthCheck()

    result = health.check()

    assert result["status"] == "UP"