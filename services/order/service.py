class OrderService:

    def __init__(
        self,
        manager,
    ):
        self.manager = manager

    def submit(
        self,
        order,
    ):
        return self.manager.create(
            order
        )

    def change_status(
        self,
        order,
        status,
    ):
        return self.manager.update_status(
            order,
            status
        )