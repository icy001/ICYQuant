"""
Conversation memory.
"""


class ConversationMemory:

    def __init__(
        self,
        store,
    ):

        self.store = store

    def remember(
        self,
        record,
    ):

        self.store.save(
            record
        )

    def history(self):

        return self.store.all()