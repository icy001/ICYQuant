class EventPublisher:
    def __init__(self, bus):
        self.bus = bus

    def publish(self, event):
        self.bus.publish(event)