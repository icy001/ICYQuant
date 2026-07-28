class AuditRepository:
    def __init__(self, store):
        self.store = store

    def save(self, event):
        self.store.append(event)

    def query(self):
        return self.store.all()
