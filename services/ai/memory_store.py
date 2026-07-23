"""
Memory storage.
"""


class MemoryStore:

    def __init__(self):

        self._records = {}

    def save(
        self,
        record,
    ):

        self._records[
            record.memory_id
        ] = record

    def get(
        self,
        memory_id,
    ):

        return self._records.get(
            memory_id,
        )

    def all(self):

        return list(
            self._records.values()
        )