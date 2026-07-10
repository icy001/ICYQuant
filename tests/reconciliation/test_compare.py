from decimal import Decimal

from services.projection import (
    PortfolioState,
    PositionState,
)

from services.reconciliation import (
    PositionComparator,
)


def test_position_difference():
    state = PortfolioState()

    state.positions["NVDA"] = (
        PositionState(
            symbol="NVDA",
            quantity=Decimal("100")
        )
    )

    comparator = PositionComparator()

    result = comparator.compare(
        state,
        {
            "NVDA":
                Decimal("80")
        }
    )

    assert len(result) == 1

    assert result[0].delta == Decimal("-20")