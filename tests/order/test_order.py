from services.order import *


def test_order_state_machine():

    repository = OrderRepository()

    manager = OrderManager(
        repository,
        OrderStateMachine()
    )

    service = OrderService(
        manager
    )

    order = Order(
        "ORD001",
        "ACC001",
        "PF001",
        "NVDA",
        10,
        150,
        OrderSide.BUY,
        OrderType.LIMIT
    )

    service.submit(order)

    result = service.change_status(
        order,
        OrderStatus.SUBMITTED
    )

    assert result is True