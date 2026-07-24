class OrderManager:

    def __init__(
        self,
        repository,
        state_machine,
    ):
        self.repository = repository
        self.state_machine = state_machine

    def create(
        self,
        order,
    ):
        self.repository.save(
            order
        )
        return order

    def update_status(
        self,
        order,
        status,
    ):
        if self.state_machine.can_transition(
            order.status,
            status
        ):
            order.status = status
            self.repository.save(order)
            return True

        return False