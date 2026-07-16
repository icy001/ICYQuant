from decimal import Decimal
from uuid import uuid4

from services.trade import Trade, TradeMapper, TradeModel


def test_mapper_to_model():
    trade = Trade(
        order_id=uuid4(),
        account_id="ACC-001",
        symbol="AAPL",
        quantity=Decimal("100"),
        price=Decimal("185.25"),
        execution_id="EX-001",
        commission=Decimal("1.85"),
    )

    model = TradeMapper.to_model(trade)

    assert model.symbol == trade.symbol
    assert model.quantity == trade.quantity
    assert model.price == trade.price
    assert model.execution_id == trade.execution_id
    assert model.commission == trade.commission
    assert model.account_id == trade.account_id


def test_mapper_to_domain():
    from datetime import datetime, timezone

    trade = Trade(
        order_id=uuid4(),
        account_id="ACC-001",
        symbol="MSFT",
        quantity=Decimal("50"),
        price=Decimal("300.50"),
        execution_id="EX-002",
        commission=Decimal("3.00"),
    )

    model = TradeMapper.to_model(trade)
    model.created_at = datetime(2026, 7, 16, 10, 30, 0, tzinfo=timezone.utc)

    domain = TradeMapper.to_domain(model)

    assert domain.symbol == trade.symbol
    assert domain.quantity == trade.quantity
    assert domain.price == trade.price
    assert domain.execution_id == trade.execution_id
    assert domain.commission == trade.commission
    assert domain.executed_at == model.created_at
    assert domain.account_id == trade.account_id