from services.backtest import (
    StrategyRegistry,
    StrategyRegistration,
    StrategyRunner,
    MultiStrategyCoordinator,
)


class DemoStrategy:

    def on_tick(
        self,
        tick,
    ):

        return tick.symbol


def test_multi_strategy():

    registry = StrategyRegistry()

    registry.register(
        StrategyRegistration(
            "S1",
            "Demo",
            "1.0",
        ),
        StrategyRunner(
            DemoStrategy(),
        ),
    )


    result = MultiStrategyCoordinator(
        registry,
    ).execute(
        type(
            "Tick",
            (),
            {
                "symbol": "AAPL",
            },
        )()
    )


    assert result["S1"] == "AAPL"