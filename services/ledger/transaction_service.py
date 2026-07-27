class LedgerService:
    def __init__(self, manager):
        self.manager = manager

    def post(self, transaction):
        return self.manager.record(transaction)

    def query(self, transaction_id):
        return self.manager.get(transaction_id)