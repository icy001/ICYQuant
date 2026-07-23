"""
Event sourcing bridge.
"""


class EventSourcingBridge:

    def __init__(
        self,
        event_store,
    ):

        self.store = event_store

    def publish(
        self,
        event,
    ):

        self.store.save(event)