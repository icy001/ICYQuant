from decimal import Decimal
from uuid import uuid4

from services.trade import Trade


def test_trade_model():
    trade = Trade(
        order_id=uuid4(),
        symbol="AAPL",
        quantity=Decimal("100"),
        price=Decimal("185.25"),
    )

    assert trade.symbol == "AAPL"
    assert trade.quantity == Decimal("100")
    assert trade.price == Decimal("185.25")