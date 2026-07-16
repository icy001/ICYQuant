from services.order import (
    OrderModel,
    OrderRepository,
)


def test_repository_model():

    repo = OrderRepository(
        session=None,
    )

    assert repo.model is OrderModel