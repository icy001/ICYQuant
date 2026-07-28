class EventStream:
    def __init__(self, aggregate_id):
        self.aggregate_id = aggregate_id
        self.events = []

    def add(self, event):
        self.events.append(event)
