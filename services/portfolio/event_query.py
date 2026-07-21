"""
Portfolio event query.
"""


class EventQuery:

    def __init__(
        self,
        store,
    ):

        self.store = store

    def events(self):

        return self.store.all_events()