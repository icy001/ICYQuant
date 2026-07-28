class AdministratorMemory:
    def __init__(self):
        self.records = []

    def save(self, record):
        self.records.append(record)
