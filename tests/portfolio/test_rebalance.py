from decimal import Decimal

from services.portfolio import (
    Allocation,
    RebalancePlanner,
    RebalanceService,
)


def test_rebalance():
    allocation = Allocation(
        symbol="AAPL",
        target_weight=Decimal("0.40"),
        current_weight=Decimal("0.55"),
    )

    service = RebalanceService()
    assert service.needs_rebalance(
        allocation,
        Decimal("0.10"),
    )

    planner = RebalancePlanner()
    delta = planner.trade_delta(
        allocation,
        Decimal("100000"),
    )

    assert delta == Decimal("-15000")


def test_no_rebalance_needed():
    allocation = Allocation(
        symbol="MSFT",
        target_weight=Decimal("0.30"),
        current_weight=Decimal("0.32"),
    )

    service = RebalanceService()
    assert not service.needs_rebalance(
        allocation,
        Decimal("0.10"),
    )


def test_rebalance_buy_signal():
    allocation = Allocation(
        symbol="GOOG",
        target_weight=Decimal("0.25"),
        current_weight=Decimal("0.15"),
    )

    planner = RebalancePlanner()
    delta = planner.trade_delta(
        allocation,
        Decimal("100000"),
    )

    assert delta == Decimal("10000")