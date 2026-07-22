"""
Backtest event bus.
"""


class BacktestEventBus:

    def __init__(self):

        self._subscribers = {}


    def subscribe(
        self,
        event_type,
        handler,
    ):

        self._subscribers.setdefault(
            event_type,
            [],
        ).append(handler)


    def publish(
        self,
        event,
    ):

        for handler in self._subscribers.get(
            event.event_type,
            [],
        ):

            handler(event)