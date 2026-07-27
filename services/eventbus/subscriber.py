class EventSubscriber:
    def __init__(self):
        self.handlers = []

    def register(self, handler):
        self.handlers.append(handler)