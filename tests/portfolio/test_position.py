from decimal import Decimal

from services.portfolio import (
    Position,
    PositionAggregator,
    ExposureCalculator,
    PositionService,
)


def test_position_aggregation():
    aggregator = PositionAggregator()

    positions = [
        Position(
            symbol="AAPL",
            quantity=Decimal("10"),
            average_price=Decimal("100"),
        ),
        Position(
            symbol="AAPL",
            quantity=Decimal("20"),
            average_price=Decimal("120"),
        ),
    ]

    result = aggregator.aggregate(
        positions,
        {
            "AAPL": Decimal("150")
        }
    )

    assert result[0].quantity == Decimal("30")
    assert result[0].market_value == Decimal("4500")


def test_position_model():
    position = Position(
        symbol="MSFT",
        quantity=Decimal("50"),
        average_price=Decimal("250"),
    )

    assert position.symbol == "MSFT"
    assert position.quantity == Decimal("50")
    assert position.average_price == Decimal("250")


def test_exposure_calculator():
    calculator = ExposureCalculator()

    class FakeSnapshot:
        market_value = Decimal("10000")

    result = calculator.calculate([FakeSnapshot(), FakeSnapshot()])

    assert result == Decimal("20000")


def test_position_service():
    aggregator = PositionAggregator()
    service = PositionService(aggregator)

    positions = [
        Position(
            symbol="GOOG",
            quantity=Decimal("10"),
            average_price=Decimal("100"),
        ),
    ]

    result = service.snapshot(positions, {"GOOG": Decimal("150")})

    assert len(result) == 1
    assert result[0].symbol == "GOOG"


def test_multiple_symbols():
    aggregator = PositionAggregator()

    positions = [
        Position(symbol="AAPL", quantity=Decimal("10"), average_price=Decimal("100")),
        Position(symbol="MSFT", quantity=Decimal("20"), average_price=Decimal("200")),
        Position(symbol="AAPL", quantity=Decimal("10"), average_price=Decimal("120")),
    ]

    result = aggregator.aggregate(
        positions,
        {"AAPL": Decimal("150"), "MSFT": Decimal("250")}
    )

    symbols = {s.symbol for s in result}
    assert symbols == {"AAPL", "MSFT"}

    aapl = next(s for s in result if s.symbol == "AAPL")
    assert aapl.quantity == Decimal("20")

    msft = next(s for s in result if s.symbol == "MSFT")
    assert msft.market_value == Decimal("5000")