from decimal import Decimal

from services.ledger import (
    PostingEngine,
)


class Trade:
    quantity = Decimal("100")
    price = Decimal("10")
    commission = Decimal("5")


def test_post_trade():
    engine = PostingEngine()

    journal = engine.post_trade(
        Trade()
    )

    assert journal.is_balanced()
    assert len(journal.entries) == 4