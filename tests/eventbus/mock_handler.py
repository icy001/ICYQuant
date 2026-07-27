from services.eventbus import EventHandler


class MockHandler(EventHandler):
    def __init__(self):
        self.received = None

    def handle(self, event):
        self.received = event