"""
AI context service.
"""


class AIContextService:

    def __init__(
        self,
        retrieval,
        builder,
    ):

        self.retrieval = retrieval

        self.builder = builder

    def build_context(
        self,
        query,
    ):

        memories = self.retrieval.retrieve(
            query
        )

        return self.builder.build(
            memories
        )