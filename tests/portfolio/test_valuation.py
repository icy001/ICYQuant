from decimal import Decimal

from services.portfolio import (
    PnLCalculator,
    NAVCalculator,
    ValuationEngine,
    ValuationService,
    EquitySnapshot,
    Position,
)


def test_unrealized_pnl():
    calculator = PnLCalculator()

    pnl = calculator.unrealized(
        Decimal("10"),
        Decimal("100"),
        Decimal("120"),
    )

    assert pnl == Decimal("200")


def test_unrealized_pnl_loss():
    calculator = PnLCalculator()

    pnl = calculator.unrealized(
        Decimal("10"),
        Decimal("100"),
        Decimal("90"),
    )

    assert pnl == Decimal("-100")


def test_nav_calculator():
    calculator = NAVCalculator()

    class FakeValuation:
        market_value = Decimal("10000")

    nav = calculator.calculate([FakeValuation(), FakeValuation()], Decimal("5000"))

    assert nav == Decimal("25000")


def test_valuation_engine():
    pnl = PnLCalculator()
    nav = NAVCalculator()
    engine = ValuationEngine(pnl, nav)

    positions = [
        Position(symbol="AAPL", quantity=Decimal("10"), average_price=Decimal("100")),
        Position(symbol="MSFT", quantity=Decimal("20"), average_price=Decimal("200")),
    ]

    result = engine.calculate(
        positions,
        {"AAPL": Decimal("120"), "MSFT": Decimal("250")},
        Decimal("1000"),
    )

    assert "positions" in result
    assert "nav" in result
    assert len(result["positions"]) == 2


def test_valuation_service():
    pnl = PnLCalculator()
    nav = NAVCalculator()
    engine = ValuationEngine(pnl, nav)
    service = ValuationService(engine)

    positions = [
        Position(symbol="GOOG", quantity=Decimal("10"), average_price=Decimal("100")),
    ]

    result = service.value(positions, {"GOOG": Decimal("150")}, Decimal("500"))

    assert "nav" in result


def test_equity_snapshot():
    snapshot = EquitySnapshot(timestamp="2024-01-01", nav=Decimal("100000"))

    assert snapshot.timestamp == "2024-01-01"
    assert snapshot.nav == Decimal("100000")