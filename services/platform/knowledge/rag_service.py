"""
Retrieval augmented generation service.
"""


class RAGService:

    def __init__(
        self,
        retriever,
        ai_service,
    ):

        self.retriever = retriever

        self.ai_service = ai_service

    def answer(
        self,
        question,
        semantic_memory,
        vector_index,
    ):

        context = self.retriever.search(
            question,
            semantic_memory,
            vector_index,
        )

        return self.ai_service.execute(
            str(context)
        )