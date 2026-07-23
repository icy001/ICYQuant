"""
Memory retrieval engine.
"""


class MemoryRetrievalEngine:

    def __init__(
        self,
        memories,
    ):

        self.memories = memories

    def retrieve(
        self,
        query,
    ):

        results = []

        for memory in self.memories:

            results.extend(
                memory.search(
                    query
                )
            )

        return results