from decimal import Decimal

from services.position import (
    Position,
    PositionMapper,
)


def test_mapper():
    position = Position(
        account_id="ACC-001",
        symbol="AAPL",
        quantity=Decimal("100"),
    )

    model = PositionMapper.to_model(position)

    domain = PositionMapper.to_domain(model)

    assert domain.account_id == position.account_id
    assert domain.symbol == position.symbol
    assert domain.quantity == position.quantity