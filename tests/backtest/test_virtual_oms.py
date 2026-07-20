from services.backtest import (
    VirtualOMS,
    VirtualOrder,
    VirtualOrderRepository,
    VirtualOrderStatus,
    VirtualOrderRouter,
    OMSService,
)


def test_submit_virtual_order():
    repository = VirtualOrderRepository()

    oms = VirtualOMS(repository)

    order = VirtualOrder(
        id="order-001",
        symbol="AAPL",
        side="BUY",
        quantity=100,
    )

    oms.submit(order)

    assert repository.get("order-001") == order


def test_virtual_order():
    order = VirtualOrder(
        id="order-002",
        symbol="MSFT",
        side="SELL",
        quantity=50,
    )

    assert order.symbol == "MSFT"
    assert order.side == "SELL"


def test_virtual_order_repository():
    repository = VirtualOrderRepository()

    order1 = VirtualOrder(
        id="order-003",
        symbol="GOOGL",
        side="BUY",
        quantity=200,
    )

    order2 = VirtualOrder(
        id="order-004",
        symbol="AMZN",
        side="SELL",
        quantity=150,
    )

    repository.save(order1)
    repository.save(order2)

    assert repository.get("order-003") == order1
    assert repository.get("order-004") == order2
    assert repository.get("order-nonexistent") is None


def test_virtual_order_status_enum():
    assert VirtualOrderStatus.CREATED == "CREATED"
    assert VirtualOrderStatus.SUBMITTED == "SUBMITTED"
    assert VirtualOrderStatus.PARTIALLY_FILLED == "PARTIALLY_FILLED"
    assert VirtualOrderStatus.FILLED == "FILLED"
    assert VirtualOrderStatus.CANCELLED == "CANCELLED"
    assert VirtualOrderStatus.REJECTED == "REJECTED"


def test_oms_service():
    repository = VirtualOrderRepository()
    oms = VirtualOMS(repository)
    service = OMSService(oms)

    order = VirtualOrder(
        id="order-005",
        symbol="TSLA",
        side="BUY",
        quantity=100,
    )

    result = service.submit(order)

    assert result == order
    assert repository.get("order-005") == order