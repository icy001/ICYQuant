"""
Agent memory adapter.
"""


class AgentMemoryAdapter:

    def __init__(
        self,
        context_service,
    ):

        self.context_service = context_service

    def context(
        self,
        query,
    ):

        return self.context_service.build_context(
            query
        )