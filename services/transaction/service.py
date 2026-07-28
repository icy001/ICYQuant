from .saga import SagaCoordinator


class TransactionService:

    def __init__(
        self,
        repository
    ):
        self.repository = repository
        self.saga = SagaCoordinator()

    def begin(self, transaction):
        self.repository.save(transaction)

        return self.saga.execute(transaction)
