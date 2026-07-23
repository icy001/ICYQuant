"""
Research knowledge memory.
"""


class ResearchMemory:

    def __init__(
        self,
    ):

        self._knowledge = []

    def add(
        self,
        knowledge,
    ):

        self._knowledge.append(
            knowledge
        )

    def search(
        self,
        keyword,
    ):

        return [
            item
            for item in self._knowledge
            if keyword in item
        ]