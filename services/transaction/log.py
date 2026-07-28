class TransactionLog:

    def __init__(self):
        self.logs = []

    def append(self, record):
        self.logs.append(record)
