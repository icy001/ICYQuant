class SagaCoordinator:

    def execute(self, transaction):

        transaction.status = "CONFIRMED"

        return transaction
