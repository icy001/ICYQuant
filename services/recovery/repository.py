class EventRepository:
    def __init__(self):
        self.events = []

    def append(self, event):
        self.events.append(event)

    def query(self, start, end):
        return [
            event
            for event in self.events
            if start <= event.timestamp <= end
        ]