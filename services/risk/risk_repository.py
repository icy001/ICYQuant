"""
Risk repository.
"""


class RiskRepository:

    def __init__(self):

        self.storage = {}

    def save(
        self,
        key,
        value,
    ):

        self.storage[key] = value

    def load(
        self,
        key,
    ):

        return self.storage.get(key)