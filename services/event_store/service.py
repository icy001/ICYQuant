class EventSourcingService:
    def __init__(self, store):
        self.store = store

    def publish(self, event):
        self.store.append(event)

    def replay(self):
        return self.store.all()
