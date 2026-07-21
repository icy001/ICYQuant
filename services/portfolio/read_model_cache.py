"""
Read model cache engine.
"""


class ReadModelCache:

    def __init__(
        self,
        repository,
    ):

        self.repository = repository

    def load(
        self,
        key,
    ):

        return self.repository.get(
            key,
        )

    def save(
        self,
        key,
        value,
    ):

        self.repository.put(
            key,
            value,
        )

        return value