class LedgerManager:
    def __init__(self, repository):
        self.repository = repository

    def record(self, transaction):
        self.repository.save(transaction)
        return transaction

    def get(self, transaction_id):
        return self.repository.find(transaction_id)