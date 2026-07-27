class TransactionRepository:
    def __init__(self):
        self.transactions = {}

    def save(self, transaction):
        self.transactions[transaction.transaction_id] = transaction

    def find(self, transaction_id):
        return self.transactions.get(transaction_id)