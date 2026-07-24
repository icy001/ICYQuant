class OrderRepository:

    def __init__(self):
        self.orders = {}

    def save(
        self,
        order,
    ):
        self.orders[
            order.order_id
        ] = order

    def find(
        self,
        order_id,
    ):
        return self.orders.get(
            order_id
        )