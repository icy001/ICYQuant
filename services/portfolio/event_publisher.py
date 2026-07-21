"""
Event publisher.
"""


class EventPublisher:

    def __init__(self):

        self.subscribers = []

    def subscribe(
        self,
        subscriber,
    ):

        self.subscribers.append(
            subscriber
        )

    def publish(
        self,
        event,
    ):

        for subscriber in self.subscribers:

            subscriber.handle(
                event
            )