class CompensationManager:

    def compensate(self, transaction):

        transaction.status = "CANCELLED"

        return transaction
