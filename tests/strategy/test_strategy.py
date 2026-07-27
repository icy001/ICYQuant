from services.strategy.simple_model import SimpleStrategy
from services.strategy.registry import StrategyRegistry
from services.strategy.simple_generator import SimpleSignalGenerator
from services.strategy.manager import StrategyRuntimeManager
from services.strategy.service import StrategyService


class MarketData:
    symbol = "NVDA"


def test_strategy_runtime():
    registry = StrategyRegistry()

    strategy = SimpleStrategy(
        "S001",
        "Momentum",
        "1.0",
        "Momentum Strategy"
    )

    registry.register(strategy)

    service = StrategyService(
        StrategyRuntimeManager(
            registry,
            SimpleSignalGenerator()
        )
    )

    signal = service.run(
        "S001",
        MarketData()
    )

    assert signal.action == "BUY"