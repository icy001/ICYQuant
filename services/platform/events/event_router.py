"""
Agent Event Router.
"""


class EventRouter:

    def __init__(self):

        self.routes = {}

    def register(
        self,
        event_type,
        handler,
    ):

        self.routes.setdefault(
            event_type,
            []
        ).append(handler)

    def dispatch(
        self,
        event,
    ):

        for handler in self.routes.get(
            event.event_type,
            [],
        ):

            handler(event)