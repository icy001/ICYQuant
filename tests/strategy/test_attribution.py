from decimal import Decimal

from services.strategy.attribution import (
    PnLCalculator,
    StrategyAttribution,
    FactorAttribution,
    RiskAttribution,
    AttributionEngine,
)


def test_pnl():
    calc = PnLCalculator()

    pnl = calc.calculate(
        Decimal("100"),
        Decimal("120"),
        Decimal("10"),
    )

    assert pnl == Decimal("200")


def test_pnl_loss():
    calc = PnLCalculator()

    pnl = calc.calculate(
        Decimal("100"),
        Decimal("90"),
        Decimal("10"),
    )

    assert pnl == Decimal("-100")


def test_strategy_attribution():
    class Trade:
        def __init__(self, strategy_id, pnl):
            self.strategy_id = strategy_id
            self.pnl = pnl

    attribution = StrategyAttribution()

    result = attribution.calculate([
        Trade("Momentum", Decimal("5000")),
        Trade("MeanReversion", Decimal("-1000")),
        Trade("Momentum", Decimal("2000")),
    ])

    assert result["Momentum"] == Decimal("7000")
    assert result["MeanReversion"] == Decimal("-1000")


def test_factor_attribution():
    attribution = FactorAttribution()

    exposure = {
        "AI_SEMICONDUCTOR": Decimal("100000"),
        "TECH": Decimal("50000"),
    }

    returns = {
        "AI_SEMICONDUCTOR": Decimal("0.05"),
        "TECH": Decimal("0.03"),
    }

    result = attribution.calculate(exposure, returns)

    assert result["AI_SEMICONDUCTOR"] == Decimal("5000")
    assert result["TECH"] == Decimal("1500")


def test_risk_attribution():
    attribution = RiskAttribution()

    positions = {
        "NVDA": 40,
        "AMD": 35,
        "TSM": 25,
    }

    result = attribution.calculate(positions)

    assert result["NVDA"] == 40
    assert result["AMD"] == 35


def test_attribution_engine():
    class Trade:
        def __init__(self, strategy_id, pnl):
            self.strategy_id = strategy_id
            self.pnl = pnl

    engine = AttributionEngine(
        strategy=StrategyAttribution(),
        factor=FactorAttribution(),
        risk=RiskAttribution(),
    )

    result = engine.analyze(
        trades=[Trade("StrategyA", Decimal("1000"))],
        exposure={"Factor1": Decimal("10000")},
        positions={"AAPL": 50},
    )

    assert result.pnl_by_strategy["StrategyA"] == Decimal("1000")